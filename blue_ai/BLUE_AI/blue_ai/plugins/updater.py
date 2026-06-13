"""
BLUE_AI Updater — Yazılım güncelleme takibi.

Yüklü yazılımlar ve güncellemeleri izler.
"""

import asyncio
import winreg
from typing import Any

from blue_ai.plugins.base import BasePlugin


class UpdaterPlugin(BasePlugin):
    name = "updater"
    description = "Yazılım güncelleme takibi"
    version = "1.0.0"

    def __init__(self, event_bus: Any, config: dict[str, Any]) -> None:
        super().__init__(event_bus, config)
        self._interval = 3600.0  # Saatte bir kontrol
        self._installed_software: list[dict[str, Any]] = []

    def get_interval(self) -> float:
        return self._interval

    async def on_start(self) -> None:
        software = await asyncio.get_event_loop().run_in_executor(
            None, self._scan_installed_software
        )
        self._installed_software = software
        self.logger.info(self.name, f"Yüklü yazılım: {len(software)} uygulama bulundu")

    async def on_stop(self) -> None:
        pass

    async def tick(self) -> None:
        # Periyodik olarak yazılım listesini güncelle
        software = await asyncio.get_event_loop().run_in_executor(
            None, self._scan_installed_software
        )

        # Yeni yüklenen yazılımları tespit et
        old_names = {s["name"] for s in self._installed_software}
        new_names = {s["name"] for s in software}
        newly_installed = new_names - old_names
        removed = old_names - new_names

        for name in newly_installed:
            self.logger.info(self.name, f"📦 Yeni yazılım yüklendi: {name}")

        for name in removed:
            self.logger.info(self.name, f"🗑️ Yazılım kaldırıldı: {name}")

        self._installed_software = software

    def _scan_installed_software(self) -> list[dict[str, Any]]:
        """Yüklü yazılımları Registry'den tara."""
        software = []

        keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        for hive, key_path in keys:
            try:
                key = winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ)
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(key, subkey_name, 0, winreg.KEY_READ)

                        try:
                            name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        except OSError:
                            winreg.CloseKey(subkey)
                            i += 1
                            continue

                        version = ""
                        publisher = ""
                        install_date = ""

                        try:
                            version = winreg.QueryValueEx(subkey, "DisplayVersion")[0]
                        except OSError:
                            pass
                        try:
                            publisher = winreg.QueryValueEx(subkey, "Publisher")[0]
                        except OSError:
                            pass
                        try:
                            install_date = winreg.QueryValueEx(subkey, "InstallDate")[0]
                        except OSError:
                            pass

                        software.append({
                            "name": name,
                            "version": version,
                            "publisher": publisher,
                            "install_date": install_date,
                        })

                        winreg.CloseKey(subkey)
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except OSError:
                continue

        # İsme göre sırala ve tekrarları kaldır
        seen = set()
        unique = []
        for s in software:
            if s["name"] not in seen:
                seen.add(s["name"])
                unique.append(s)

        unique.sort(key=lambda x: x["name"].lower())
        return unique

    # --- Public API ---

    def get_installed_software(self) -> list[dict[str, Any]]:
        """Yüklü yazılım listesini döndür."""
        return list(self._installed_software)

    def search_software(self, query: str) -> list[dict[str, Any]]:
        """Yazılım ara."""
        query_lower = query.lower()
        return [
            s for s in self._installed_software
            if query_lower in s["name"].lower()
        ]

    def get_status(self) -> dict[str, Any]:
        base = super().get_status()
        base["installed_count"] = len(self._installed_software)
        return base
