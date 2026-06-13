"""
BLUE_AI System Monitor — CPU, RAM, Disk, GPU, Sıcaklık, Ağ metrikleri.

Anlık sistem durumunu izler ve metrikleri Event Bus üzerinden yayınlar.
"""

import asyncio
from typing import Any

import psutil

from blue_ai.plugins.base import BasePlugin
from blue_ai.core.event_bus import Event


class SystemMonitorPlugin(BasePlugin):
    name = "system_monitor"
    description = "Sistem kaynaklarını izler (CPU, RAM, Disk, GPU, Sıcaklık)"
    version = "1.0.0"

    def __init__(self, event_bus: Any, config: dict[str, Any]) -> None:
        super().__init__(event_bus, config)
        self._interval = config.get("polling", {}).get("system_monitor_interval", 2.0)
        self._metrics: dict[str, Any] = {}
        self._cpu_history: list[float] = []
        self._max_history = 300  # 5 dakikalık geçmiş (2sn aralıkla)

    def get_interval(self) -> float:
        return self._interval

    async def on_start(self) -> None:
        # İlk CPU okumayı başlat (non-blocking)
        psutil.cpu_percent(interval=None)

    async def on_stop(self) -> None:
        pass

    async def tick(self) -> None:
        metrics = await asyncio.get_event_loop().run_in_executor(None, self._collect_metrics)
        self._metrics = metrics

        # Metrikleri event bus'a yayınla
        await self.emit("metrics_update", {
            "cpu_percent": metrics["cpu"]["percent"],
            "ram_percent": metrics["ram"]["percent"],
            "disk_percent": metrics["disk"]["percent"],
            "cpu_temp": metrics.get("temperature", {}).get("cpu", 0),
            "gpu_temp": metrics.get("temperature", {}).get("gpu", 0),
            "network_mbps": metrics["network"]["total_mbps"],
        })

        # Log metrikleri kaydet
        self.logger.log_metric("cpu_percent", metrics["cpu"]["percent"], self.name)
        self.logger.log_metric("ram_percent", metrics["ram"]["percent"], self.name)
        self.logger.log_metric("disk_percent", metrics["disk"]["percent"], self.name)

    def _collect_metrics(self) -> dict[str, Any]:
        """Tüm sistem metriklerini topla (senkron, executor'da çalışır)."""
        metrics: dict[str, Any] = {}

        # CPU
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
        cpu_freq = psutil.cpu_freq()
        self._cpu_history.append(cpu_percent)
        if len(self._cpu_history) > self._max_history:
            self._cpu_history = self._cpu_history[-self._max_history:]

        metrics["cpu"] = {
            "percent": cpu_percent,
            "per_core": cpu_per_core,
            "freq_current": cpu_freq.current if cpu_freq else 0,
            "freq_max": cpu_freq.max if cpu_freq else 0,
            "core_count": psutil.cpu_count(),
            "logical_count": psutil.cpu_count(logical=True),
            "avg_1min": sum(self._cpu_history[-30:]) / max(len(self._cpu_history[-30:]), 1),
        }

        # RAM
        ram = psutil.virtual_memory()
        swap = psutil.swap_memory()
        metrics["ram"] = {
            "percent": ram.percent,
            "total": ram.total,
            "available": ram.available,
            "used": ram.used,
            "swap_percent": swap.percent,
            "swap_total": swap.total,
            "swap_used": swap.used,
        }

        # Disk
        partitions = psutil.disk_partitions()
        disks = []
        main_percent = 0.0
        for part in partitions:
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disk_info = {
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent,
                }
                disks.append(disk_info)
                if part.mountpoint == "C:\\":
                    main_percent = usage.percent
            except (PermissionError, OSError):
                continue

        # Disk I/O
        try:
            disk_io = psutil.disk_io_counters()
            io_data = {
                "read_bytes": disk_io.read_bytes if disk_io else 0,
                "write_bytes": disk_io.write_bytes if disk_io else 0,
            }
        except Exception:
            io_data = {"read_bytes": 0, "write_bytes": 0}

        metrics["disk"] = {
            "percent": main_percent or (disks[0]["percent"] if disks else 0),
            "partitions": disks,
            "io": io_data,
        }

        # Ağ
        try:
            net_io = psutil.net_io_counters()
            metrics["network"] = {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
                "total_mbps": (net_io.bytes_sent + net_io.bytes_recv) / 1024 / 1024,
            }
        except Exception:
            metrics["network"] = {"bytes_sent": 0, "bytes_recv": 0, "total_mbps": 0}

        # Sıcaklık
        temps: dict[str, float] = {}
        try:
            sensor_temps = psutil.sensors_temperatures()
            if sensor_temps:
                for name, entries in sensor_temps.items():
                    if entries:
                        temps[name] = entries[0].current
        except (AttributeError, Exception):
            pass

        # GPU sıcaklığı (WMI ile deneme)
        try:
            self._try_gpu_temp(temps)
        except Exception:
            pass

        metrics["temperature"] = {
            "cpu": temps.get("coretemp", temps.get("k10temp", 0)),
            "gpu": temps.get("gpu", 0),
            "all": temps,
        }

        # Boot süresi
        metrics["boot_time"] = psutil.boot_time()

        return metrics

    def _try_gpu_temp(self, temps: dict[str, float]) -> None:
        """GPU sıcaklığını almaya çalış."""
        try:
            import wmi
            w = wmi.WMI(namespace="root\\OpenHardwareMonitor")
            sensors = w.Sensor()
            for sensor in sensors:
                if sensor.SensorType == "Temperature" and "GPU" in sensor.Name:
                    temps["gpu"] = float(sensor.Value)
                    break
        except Exception:
            pass

    def get_status(self) -> dict[str, Any]:
        base = super().get_status()
        base["metrics"] = self._metrics
        return base

    def get_metrics(self) -> dict[str, Any]:
        """Güncel metrikleri döndür."""
        return dict(self._metrics)
