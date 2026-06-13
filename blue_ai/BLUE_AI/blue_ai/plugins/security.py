"""
BLUE_AI Security — Güvenlik izleme.

Port tarama, şüpheli süreç tespiti, dosya bütünlüğü, USB izleme.
"""

import asyncio
import hashlib
import socket
from pathlib import Path
from typing import Any

import psutil

from blue_ai.plugins.base import BasePlugin
from blue_ai.core.event_bus import Event


class SecurityPlugin(BasePlugin):
    name = "security"
    description = "Güvenlik izleme ve tehdit tespiti"
    version = "1.0.0"

    def __init__(self, event_bus: Any, config: dict[str, Any]) -> None:
        super().__init__(event_bus, config)
        self._interval = config.get("polling", {}).get("security_scan_interval", 60.0)
        self._sec_config = config.get("security", {})
        self._whitelist = set(self._sec_config.get("whitelist", []))
        self._known_ports: set[int] = set()
        self._file_hashes: dict[str, str] = {}
        self._alerts: list[dict[str, Any]] = []
        self._usb_devices: set[str] = set()

    def get_interval(self) -> float:
        return self._interval

    async def on_start(self) -> None:
        # İlk port taraması
        if self._sec_config.get("scan_open_ports", True):
            ports = await asyncio.get_event_loop().run_in_executor(None, self._scan_ports)
            self._known_ports = {p["port"] for p in ports}
            self.logger.info(self.name, f"Bilinen açık port sayısı: {len(self._known_ports)}")

        # Kritik dosya hash'lerini al
        if self._sec_config.get("check_file_integrity", True):
            await asyncio.get_event_loop().run_in_executor(None, self._init_file_hashes)

    async def on_stop(self) -> None:
        pass

    async def tick(self) -> None:
        tasks = []

        if self._sec_config.get("scan_open_ports", True):
            tasks.append(self._check_ports())

        if self._sec_config.get("suspicious_process_detection", True):
            tasks.append(self._check_suspicious_processes())

        if self._sec_config.get("check_file_integrity", True):
            tasks.append(self._check_file_integrity())

        if self._sec_config.get("monitor_usb", True):
            tasks.append(self._check_usb_devices())

        if tasks:
            await asyncio.gather(*tasks)

    async def _check_ports(self) -> None:
        """Yeni açılan portları kontrol et."""
        current_ports = await asyncio.get_event_loop().run_in_executor(None, self._scan_ports)
        current_set = {p["port"] for p in current_ports}
        new_ports = current_set - self._known_ports

        if new_ports:
            for port_info in current_ports:
                if port_info["port"] in new_ports:
                    alert = {
                        "type": "new_port",
                        "port": port_info["port"],
                        "pid": port_info["pid"],
                        "process": port_info["process"],
                    }
                    self._alerts.append(alert)
                    self.logger.warning(
                        self.name,
                        f"🔓 Yeni açık port: {port_info['port']} ({port_info['process']})",
                    )

        self._known_ports = current_set

    def _scan_ports(self) -> list[dict[str, Any]]:
        """Dinleme modundaki portları tara."""
        ports = []
        try:
            connections = psutil.net_connections(kind="inet")
            for conn in connections:
                if conn.status == "LISTEN":
                    try:
                        proc = psutil.Process(conn.pid) if conn.pid else None
                        ports.append({
                            "port": conn.laddr.port,
                            "address": conn.laddr.ip,
                            "pid": conn.pid or 0,
                            "process": proc.name() if proc else "unknown",
                        })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        ports.append({
                            "port": conn.laddr.port,
                            "address": conn.laddr.ip,
                            "pid": conn.pid or 0,
                            "process": "unknown",
                        })
        except (psutil.AccessDenied, Exception):
            pass
        return ports

    async def _check_suspicious_processes(self) -> None:
        """Şüpheli süreçleri kontrol et."""
        suspicious = await asyncio.get_event_loop().run_in_executor(
            None, self._find_suspicious
        )
        for proc in suspicious:
            alert = {"type": "suspicious_process", **proc}
            self._alerts.append(alert)
            self.logger.warning(
                self.name,
                f"🔍 Şüpheli süreç: {proc['name']} (PID: {proc['pid']}) — {proc['reason']}",
            )

    def _find_suspicious(self) -> list[dict[str, Any]]:
        """Şüpheli süreç tespiti."""
        suspicious = []
        for proc in psutil.process_iter(["pid", "name", "exe", "cmdline", "username"]):
            try:
                info = proc.info
                name = info["name"] or ""

                # Beyaz listedekiler atlanır
                if name.lower() in {w.lower() for w in self._whitelist}:
                    continue

                reasons = []

                # Geçici dizinden çalışan süreçler
                exe = info.get("exe") or ""
                if exe and ("\\temp\\" in exe.lower() or "\\tmp\\" in exe.lower()):
                    reasons.append("Geçici dizinden çalışıyor")

                # Çok uzun komut satırı (olası injection)
                cmdline = info.get("cmdline") or []
                cmd_str = " ".join(cmdline)
                if len(cmd_str) > 2000:
                    reasons.append("Çok uzun komut satırı")

                # PowerShell -enc (encoded command)
                if cmd_str and ("-encodedcommand" in cmd_str.lower() or "-enc " in cmd_str.lower()):
                    reasons.append("Encoded PowerShell komutu")

                if reasons:
                    suspicious.append({
                        "pid": info["pid"],
                        "name": name,
                        "exe": exe,
                        "reason": "; ".join(reasons),
                    })

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return suspicious

    def _init_file_hashes(self) -> None:
        """Kritik sistem dosyalarının hash'lerini al."""
        critical_files = [
            Path(r"C:\Windows\System32\cmd.exe"),
            Path(r"C:\Windows\System32\powershell.exe"),
            Path(r"C:\Windows\System32\taskmgr.exe"),
            Path(r"C:\Windows\System32\notepad.exe"),
        ]
        for f in critical_files:
            try:
                if f.exists():
                    h = hashlib.md5(f.read_bytes()).hexdigest()
                    self._file_hashes[str(f)] = h
            except Exception:
                continue

    async def _check_file_integrity(self) -> None:
        """Dosya bütünlüğü kontrolü."""
        def _check() -> list[str]:
            changed = []
            for path_str, original_hash in self._file_hashes.items():
                try:
                    f = Path(path_str)
                    if f.exists():
                        current_hash = hashlib.md5(f.read_bytes()).hexdigest()
                        if current_hash != original_hash:
                            changed.append(path_str)
                except Exception:
                    continue
            return changed

        changed = await asyncio.get_event_loop().run_in_executor(None, _check)
        for f in changed:
            self.logger.critical(self.name, f"⚠️ Dosya bütünlüğü değişti: {f}")
            self._alerts.append({"type": "file_integrity", "file": f})

    async def _check_usb_devices(self) -> None:
        """USB cihaz izleme."""
        def _get_usb() -> set[str]:
            devices = set()
            try:
                import wmi
                w = wmi.WMI()
                for disk in w.Win32_DiskDrive():
                    if "USB" in (disk.InterfaceType or ""):
                        devices.add(f"{disk.Caption}|{disk.SerialNumber}")
            except Exception:
                pass
            return devices

        current = await asyncio.get_event_loop().run_in_executor(None, _get_usb)
        new_devices = current - self._usb_devices
        if new_devices:
            for device in new_devices:
                self.logger.warning(self.name, f"🔌 Yeni USB cihazı algılandı: {device.split('|')[0]}")
                self._alerts.append({"type": "usb_device", "device": device})
        self._usb_devices = current

    # --- Public API ---

    def get_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        """Güvenlik uyarılarını döndür."""
        return self._alerts[-limit:]

    def get_open_ports(self) -> list[dict[str, Any]]:
        """Açık portları döndür."""
        return self._scan_ports()

    def get_status(self) -> dict[str, Any]:
        base = super().get_status()
        base["alert_count"] = len(self._alerts)
        base["known_ports"] = len(self._known_ports)
        base["monitored_files"] = len(self._file_hashes)
        return base
