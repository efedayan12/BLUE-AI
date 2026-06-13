"""
BLUE_AI Network — Ağ yönetimi.

Bağlantı izleme, bandwidth takibi, DNS cache, ping/latency, ağ sorun giderme.
"""

import asyncio
import socket
import subprocess
import time
from collections import defaultdict
from typing import Any

import psutil

from blue_ai.plugins.base import BasePlugin
from blue_ai.core.event_bus import Event
from blue_ai.utils.helpers import bytes_to_human


class NetworkPlugin(BasePlugin):
    name = "network"
    description = "Ağ yönetimi ve izleme"
    version = "1.0.0"

    def __init__(self, event_bus: Any, config: dict[str, Any]) -> None:
        super().__init__(event_bus, config)
        self._interval = config.get("polling", {}).get("network_check_interval", 3.0)
        self._net_config = config.get("network", {})
        self._ping_targets = self._net_config.get("ping_targets", ["8.8.8.8", "1.1.1.1"])
        self._prev_bytes_sent = 0
        self._prev_bytes_recv = 0
        self._prev_time = time.time()
        self._current_speeds: dict[str, float] = {}
        self._ping_results: dict[str, float] = {}
        self._bandwidth_by_process: list[dict[str, Any]] = []

    def get_interval(self) -> float:
        return self._interval

    async def on_start(self) -> None:
        self.event_bus.subscribe("action.investigate_network", self._handle_investigate)
        # İlk değerleri al
        try:
            counters = psutil.net_io_counters()
            self._prev_bytes_sent = counters.bytes_sent
            self._prev_bytes_recv = counters.bytes_recv
        except Exception:
            pass

    async def on_stop(self) -> None:
        pass

    async def tick(self) -> None:
        # Hız hesapla
        await asyncio.get_event_loop().run_in_executor(None, self._calc_speeds)

        # Her 10 tick'te bir ping yap
        if hasattr(self, "_tick_count"):
            self._tick_count += 1
        else:
            self._tick_count = 0

        if self._tick_count % 10 == 0:
            await self._run_ping()

        # Bandwidth bilgisini metrics'e yayınla
        total_mbps = (
            self._current_speeds.get("upload_mbps", 0) +
            self._current_speeds.get("download_mbps", 0)
        )
        await self.emit("metrics_update", {"network_mbps": total_mbps})

    def _calc_speeds(self) -> None:
        """Upload/download hızlarını hesapla."""
        try:
            counters = psutil.net_io_counters()
            now = time.time()
            elapsed = now - self._prev_time

            if elapsed > 0:
                upload_speed = (counters.bytes_sent - self._prev_bytes_sent) / elapsed
                download_speed = (counters.bytes_recv - self._prev_bytes_recv) / elapsed

                self._current_speeds = {
                    "upload_bps": upload_speed,
                    "download_bps": download_speed,
                    "upload_mbps": upload_speed / 1024 / 1024,
                    "download_mbps": download_speed / 1024 / 1024,
                    "upload_human": bytes_to_human(upload_speed) + "/s",
                    "download_human": bytes_to_human(download_speed) + "/s",
                }

            self._prev_bytes_sent = counters.bytes_sent
            self._prev_bytes_recv = counters.bytes_recv
            self._prev_time = now
        except Exception:
            pass

    async def _run_ping(self) -> None:
        """Ping testleri."""
        for target in self._ping_targets:
            latency = await asyncio.get_event_loop().run_in_executor(
                None, self._ping, target
            )
            self._ping_results[target] = latency

    def _ping(self, host: str, timeout: int = 3) -> float:
        """Ping yap ve latency döndür (ms). Başarısız olursa -1."""
        try:
            result = subprocess.run(
                ["ping", "-n", "1", "-w", str(timeout * 1000), host],
                capture_output=True,
                text=True,
                timeout=timeout + 2,
            )
            output = result.stdout
            # "time=XXms" veya "süre=XXms" formatını bul
            for line in output.split("\n"):
                for marker in ("time=", "time<", "süre=", "süre<"):
                    if marker in line.lower():
                        part = line.lower().split(marker)[1]
                        ms = "".join(c for c in part.split("ms")[0] if c.isdigit() or c == ".")
                        if ms:
                            return float(ms)
            return -1
        except Exception:
            return -1

    async def _handle_investigate(self, event: Event) -> None:
        """Ağ soruşturması — en çok bandwidth kullanan bağlantıları bul."""
        connections = await asyncio.get_event_loop().run_in_executor(
            None, self._get_connections_by_process
        )
        self._bandwidth_by_process = connections

        top_5 = connections[:5]
        if top_5:
            details = "\n".join(
                f"  {c['process']:20s} Bağlantı: {c['connection_count']}"
                for c in top_5
            )
            self.logger.info(self.name, f"En çok bağlantı kuran 5 süreç:\n{details}")

    def _get_connections_by_process(self) -> list[dict[str, Any]]:
        """Süreç bazlı bağlantı istatistikleri."""
        proc_connections: dict[str, int] = defaultdict(int)
        try:
            connections = psutil.net_connections(kind="inet")
            for conn in connections:
                if conn.pid:
                    try:
                        proc = psutil.Process(conn.pid)
                        proc_connections[proc.name()] += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        proc_connections["unknown"] += 1
        except (psutil.AccessDenied, Exception):
            pass

        result = [
            {"process": name, "connection_count": count}
            for name, count in proc_connections.items()
        ]
        result.sort(key=lambda x: x["connection_count"], reverse=True)
        return result

    # --- Public API ---

    def get_speeds(self) -> dict[str, Any]:
        """Güncel hız bilgilerini döndür."""
        return dict(self._current_speeds)

    def get_ping_results(self) -> dict[str, float]:
        """Ping sonuçlarını döndür."""
        return dict(self._ping_results)

    def get_connections(self) -> list[dict[str, Any]]:
        """Aktif bağlantıları döndür."""
        return self._get_connections_by_process()

    async def flush_dns(self) -> bool:
        """DNS cache temizle."""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    ["ipconfig", "/flushdns"],
                    capture_output=True,
                    text=True,
                ),
            )
            success = result.returncode == 0
            if success:
                self.logger.action(self.name, "DNS cache temizlendi")
            return success
        except Exception:
            return False

    async def diagnose(self) -> dict[str, Any]:
        """Ağ tanılama raporu."""
        speeds = self.get_speeds()
        pings = self.get_ping_results()
        connections = self._get_connections_by_process()

        # İnternet erişimi kontrolü
        internet_ok = any(v > 0 for v in pings.values())

        return {
            "internet_connected": internet_ok,
            "speeds": speeds,
            "ping": pings,
            "total_connections": sum(c["connection_count"] for c in connections),
            "top_processes": connections[:5],
        }

    def get_status(self) -> dict[str, Any]:
        base = super().get_status()
        base["speeds"] = self._current_speeds
        base["ping"] = self._ping_results
        return base
