"""
BLUE_AI Performance — Performans optimizasyonu.

Anomali tespiti, RAM temizleme, servis optimizasyonu, profil yönetimi.
"""

import asyncio
from typing import Any

import psutil

from blue_ai.plugins.base import BasePlugin
from blue_ai.core.event_bus import Event
from blue_ai.utils.win_api import empty_working_set, set_process_priority


class PerformancePlugin(BasePlugin):
    name = "performance"
    description = "Performans optimizasyonu ve anomali tespiti"
    version = "1.0.0"

    def __init__(self, event_bus: Any, config: dict[str, Any]) -> None:
        super().__init__(event_bus, config)
        self._interval = 10.0
        self._anomaly_detector = None
        self._metrics_buffer: list[list[float]] = []
        self._optimization_count = 0

    def get_interval(self) -> float:
        return self._interval

    async def on_start(self) -> None:
        self.event_bus.subscribe("action.cleanup_ram", self._handle_cleanup_ram)
        self.event_bus.subscribe("action.emergency_throttle", self._handle_emergency_throttle)
        self.event_bus.subscribe("profile_changed", self._handle_profile_change)

        # Anomali tespiti modelini başlat
        try:
            await asyncio.get_event_loop().run_in_executor(None, self._init_anomaly_detector)
        except Exception as e:
            self.logger.warning(self.name, f"Anomali tespit modeli yüklenemedi: {e}")

    async def on_stop(self) -> None:
        pass

    def _init_anomaly_detector(self) -> None:
        """Lightweight IsolationForest anomali tespit modeli."""
        try:
            from sklearn.ensemble import IsolationForest
            self._anomaly_detector = IsolationForest(
                n_estimators=50,
                contamination=0.1,
                random_state=42,
            )
        except ImportError:
            self._anomaly_detector = None

    async def tick(self) -> None:
        metrics = await asyncio.get_event_loop().run_in_executor(None, self._collect_perf_data)

        # Anomali buffer'ına ekle
        self._metrics_buffer.append([
            metrics["cpu"], metrics["ram"], metrics["disk_io"],
        ])

        # Yeterli veri biriktiğinde anomali tespiti yap
        if len(self._metrics_buffer) >= 50 and self._anomaly_detector is not None:
            await self._detect_anomalies()

        # Buffer'ı sınırla
        if len(self._metrics_buffer) > 500:
            self._metrics_buffer = self._metrics_buffer[-500:]

    def _collect_perf_data(self) -> dict[str, float]:
        """Performans verilerini topla."""
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        try:
            io_counters = psutil.disk_io_counters()
            disk_io = (io_counters.read_bytes + io_counters.write_bytes) / 1024 / 1024 if io_counters else 0
        except Exception:
            disk_io = 0
        return {"cpu": cpu, "ram": ram, "disk_io": disk_io}

    async def _detect_anomalies(self) -> None:
        """IsolationForest ile anomali tespiti."""
        try:
            import numpy as np
            data = np.array(self._metrics_buffer[-100:])
            self._anomaly_detector.fit(data[:-1])
            latest = data[-1:].reshape(1, -1)
            prediction = self._anomaly_detector.predict(latest)

            if prediction[0] == -1:
                self.logger.warning(
                    self.name,
                    "⚡ Anomali tespit edildi — Kaynak kullanımında anormal değişim!",
                    f"CPU: {data[-1][0]:.1f}%, RAM: {data[-1][1]:.1f}%, Disk I/O: {data[-1][2]:.0f} MB",
                )
                await self.emit("anomaly_detected", {
                    "cpu": float(data[-1][0]),
                    "ram": float(data[-1][1]),
                    "disk_io": float(data[-1][2]),
                })
        except Exception as e:
            self.logger.debug(self.name, f"Anomali tespit hatası: {e}")

    async def _handle_cleanup_ram(self, event: Event) -> None:
        """RAM temizleme aksiyonu."""
        cleaned = await asyncio.get_event_loop().run_in_executor(None, self._cleanup_ram)
        self.logger.action(self.name, f"RAM temizleme tamamlandı: {cleaned} süreç optimize edildi")

    def _cleanup_ram(self) -> int:
        """Düşük öncelikli süreçlerin working set'ini temizle."""
        count = 0
        for proc in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                info = proc.info
                mem = info.get("memory_info")
                if mem and mem.rss > 100 * 1024 * 1024:  # 100MB üstü
                    from blue_ai.utils.helpers import is_system_process
                    if not is_system_process(info["name"] or ""):
                        if empty_working_set(info["pid"]):
                            count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return count

    async def _handle_emergency_throttle(self, event: Event) -> None:
        """Acil throttle — tüm kullanıcı süreçlerini yavaşlat."""
        self.logger.critical(self.name, "🔥 Acil throttle aktif — Sıcaklık kritik!")
        count = 0
        for proc in psutil.process_iter(["pid", "name", "cpu_percent"]):
            try:
                info = proc.info
                from blue_ai.utils.helpers import is_system_process
                if not is_system_process(info["name"] or ""):
                    if (info.get("cpu_percent") or 0) > 10:
                        set_process_priority(info["pid"], "idle")
                        count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self.logger.action(self.name, f"Acil throttle: {count} süreç yavaşlatıldı")

    async def _handle_profile_change(self, event: Event) -> None:
        """Profil değişikliğinde optimizasyon uygula."""
        profile = event.data.get("profile", "balanced")
        self.logger.info(self.name, f"Profil uygulanıyor: {profile}")

        if profile == "gaming":
            await self._apply_gaming_mode()
        elif profile == "power_saver":
            await self._apply_power_saver()
        elif profile == "work":
            await self._apply_work_mode()

    async def _apply_gaming_mode(self) -> None:
        """Oyun modu optimizasyonları."""
        # Gereksiz arka plan süreçlerini yavaşlat
        unnecessary = {
            "searchindexer.exe", "wsearch", "sysmain",
            "diagtrack.exe", "compattelrunner.exe",
        }
        count = 0
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.info["name"] and proc.info["name"].lower() in unnecessary:
                    set_process_priority(proc.info["pid"], "idle")
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self.logger.action(self.name, f"Oyun modu: {count} arka plan süreci yavaşlatıldı")

    async def _apply_power_saver(self) -> None:
        """Güç tasarrufu optimizasyonları."""
        self.logger.action(self.name, "Güç tasarrufu modu aktif")

    async def _apply_work_mode(self) -> None:
        """İş modu optimizasyonları."""
        self.logger.action(self.name, "İş modu aktif")

    # --- Public API ---

    async def optimize_now(self) -> dict[str, Any]:
        """Manuel tam optimizasyon."""
        ram_cleaned = await asyncio.get_event_loop().run_in_executor(None, self._cleanup_ram)
        self._optimization_count += 1
        return {
            "ram_processes_cleaned": ram_cleaned,
            "total_optimizations": self._optimization_count,
        }

    def get_status(self) -> dict[str, Any]:
        base = super().get_status()
        base["optimization_count"] = self._optimization_count
        base["anomaly_detector_active"] = self._anomaly_detector is not None
        base["metrics_buffer_size"] = len(self._metrics_buffer)
        return base
