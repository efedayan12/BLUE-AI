"""
BLUE_AI Startup — Başlangıç yönetimi.

Boot süresi ölçümü, başlangıç uygulamaları listesi ve optimizasyonu.
"""

import asyncio
import subprocess
import winreg
from typing import Any

import psutil

from blue_ai.plugins.base import BasePlugin
from blue_ai.utils.helpers import seconds_to_human


class StartupPlugin(BasePlugin):
    name = "startup"
    description = "Başlangıç uygulamaları ve boot optimizasyonu"
    version = "1.0.0"

    def __init__(self, event_bus: Any, config: dict[str, Any]) -> None:
        super().__init__(event_bus, config)
        self._interval = 300.0  # 5 dakikada bir kontrol
        self._startup_items: list[dict[str, Any]] = []
        self._boot_time_seconds = 0.0

    def get_interval(self) -> float:
        return self._interval

    async def on_start(self) -> None:
        # Boot süresini hesapla
        import time
        self._boot_time_seconds = time.time() - psutil.boot_time()

        # Başlangıç uygulamalarını tara
        items = await asyncio.get_event_loop().run_in_executor(None, self._scan_startup_items)
        self._startup_items = items

        self.logger.info(
            self.name,
            f"Boot süresi: {seconds_to_human(self._boot_time_seconds)}, "
            f"Başlangıç uygulamaları: {len(items)}",
        )

    async def on_stop(self) -> None:
        pass

    async def tick(self) -> None:
        # Periyodik olarak başlangıç listesini güncelle
        items = await asyncio.get_event_loop().run_in_executor(None, self._scan_startup_items)
        self._startup_items = items

    def _scan_startup_items(self) -> list[dict[str, Any]]:
        """Başlangıç uygulamalarını tara (Registry + Task Scheduler)."""
        items = []

        # Registry — HKCU\Software\Microsoft\Windows\CurrentVersion\Run
        registry_keys = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        ]

        for hive, key_path in registry_keys:
            try:
                key = winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ)
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        hive_name = "HKCU" if hive == winreg.HKEY_CURRENT_USER else "HKLM"
                        items.append({
                            "name": name,
                            "command": value,
                            "source": f"Registry ({hive_name})",
                            "location": f"{hive_name}\\{key_path}",
                            "enabled": True,
                        })
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except OSError:
                continue

        # Startup klasörü
        from pathlib import Path
        import os

        startup_folders = [
            Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup",
            Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Startup"),
        ]

        for folder in startup_folders:
            try:
                if folder.exists():
                    for f in folder.iterdir():
                        if f.is_file() and f.suffix.lower() in (".lnk", ".exe", ".bat", ".cmd"):
                            items.append({
                                "name": f.stem,
                                "command": str(f),
                                "source": "Startup Folder",
                                "location": str(folder),
                                "enabled": True,
                            })
            except (PermissionError, OSError):
                continue

        return items

    # --- Public API ---

    def get_startup_items(self) -> list[dict[str, Any]]:
        """Başlangıç uygulamalarını döndür."""
        return list(self._startup_items)

    def get_boot_time(self) -> dict[str, Any]:
        """Boot süresi bilgisini döndür."""
        return {
            "boot_time_seconds": self._boot_time_seconds,
            "boot_time_human": seconds_to_human(self._boot_time_seconds),
            "boot_timestamp": psutil.boot_time(),
        }

    async def disable_startup_item(self, name: str) -> bool:
        """Başlangıç uygulamasını devre dışı bırak (Registry)."""
        registry_keys = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        ]

        for hive, key_path in registry_keys:
            try:
                key = winreg.OpenKey(hive, key_path, 0, winreg.KEY_SET_VALUE)
                try:
                    winreg.DeleteValue(key, name)
                    winreg.CloseKey(key)
                    self.logger.action(self.name, f"Başlangıç devre dışı: {name}")
                    return True
                except OSError:
                    winreg.CloseKey(key)
            except OSError:
                continue

        return False

    def get_optimization_suggestions(self) -> list[dict[str, str]]:
        """Başlangıç optimizasyon önerileri."""
        suggestions = []
        # Gereksiz olabilecek başlangıç uygulamaları
        unnecessary_keywords = [
            "update", "helper", "assistant", "tray", "notif",
            "sync", "cloud", "telemetry",
        ]

        for item in self._startup_items:
            name_lower = item["name"].lower()
            for keyword in unnecessary_keywords:
                if keyword in name_lower:
                    suggestions.append({
                        "name": item["name"],
                        "command": item["command"],
                        "reason": f"'{keyword}' içeriyor — gereksiz olabilir",
                    })
                    break

        return suggestions

    def get_status(self) -> dict[str, Any]:
        base = super().get_status()
        base["startup_items"] = len(self._startup_items)
        base["boot_time"] = seconds_to_human(self._boot_time_seconds)
        return base
