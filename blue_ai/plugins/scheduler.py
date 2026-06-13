"""
BLUE_AI Scheduler — Görev zamanlayıcı.

Tekrarlayan bakım görevleri, koşullu çalıştırma, cron benzeri zamanlama.
"""

import asyncio
from datetime import datetime
from typing import Any, Callable, Coroutine

from blue_ai.plugins.base import BasePlugin
from blue_ai.core.event_bus import Event
from blue_ai.utils.win_api import get_idle_time_ms


ScheduledCallback = Callable[[], Coroutine[Any, Any, None]]


class ScheduledTask:
    """Zamanlanmış görev tanımı."""

    def __init__(
        self,
        name: str,
        callback: ScheduledCallback,
        interval_seconds: float,
        run_when_idle: bool = False,
        idle_threshold_ms: int = 300_000,  # 5 dakika
        enabled: bool = True,
    ) -> None:
        self.name = name
        self.callback = callback
        self.interval_seconds = interval_seconds
        self.run_when_idle = run_when_idle
        self.idle_threshold_ms = idle_threshold_ms
        self.enabled = enabled
        self.last_run: datetime | None = None
        self.run_count = 0
        self.last_error: str | None = None


class SchedulerPlugin(BasePlugin):
    name = "scheduler"
    description = "Görev zamanlama ve otomatik bakım"
    version = "1.0.0"

    def __init__(self, event_bus: Any, config: dict[str, Any]) -> None:
        super().__init__(event_bus, config)
        self._interval = 30.0  # 30 saniyede bir kontrol
        self._tasks: dict[str, ScheduledTask] = {}

    def get_interval(self) -> float:
        return self._interval

    async def on_start(self) -> None:
        # Varsayılan zamanlanmış görevler
        self.add_task(ScheduledTask(
            name="log_cleanup",
            callback=self._task_log_cleanup,
            interval_seconds=86400,  # 24 saat
            run_when_idle=True,
        ))
        self.add_task(ScheduledTask(
            name="metrics_cleanup",
            callback=self._task_metrics_cleanup,
            interval_seconds=43200,  # 12 saat
            run_when_idle=True,
        ))
        self.add_task(ScheduledTask(
            name="health_check",
            callback=self._task_health_check,
            interval_seconds=300,  # 5 dakika
            run_when_idle=False,
        ))

        self.logger.info(self.name, f"{len(self._tasks)} zamanlanmış görev eklendi")

    async def on_stop(self) -> None:
        pass

    async def tick(self) -> None:
        now = datetime.now()
        idle_time = get_idle_time_ms()

        for task_name, task in self._tasks.items():
            if not task.enabled:
                continue

            # Zaman kontrolü
            if task.last_run is not None:
                elapsed = (now - task.last_run).total_seconds()
                if elapsed < task.interval_seconds:
                    continue

            # Boşta olma kontrolü
            if task.run_when_idle and idle_time < task.idle_threshold_ms:
                continue

            # Görevi çalıştır
            try:
                await task.callback()
                task.last_run = now
                task.run_count += 1
                task.last_error = None
                self.logger.debug(self.name, f"Görev tamamlandı: {task_name}")
            except Exception as e:
                task.last_error = str(e)
                self.logger.error(self.name, f"Görev hatası: {task_name} — {e}")

    def add_task(self, task: ScheduledTask) -> None:
        """Zamanlanmış görev ekle."""
        self._tasks[task.name] = task

    def remove_task(self, name: str) -> bool:
        """Zamanlanmış görevi kaldır."""
        if name in self._tasks:
            del self._tasks[name]
            return True
        return False

    def enable_task(self, name: str) -> bool:
        if name in self._tasks:
            self._tasks[name].enabled = True
            return True
        return False

    def disable_task(self, name: str) -> bool:
        if name in self._tasks:
            self._tasks[name].enabled = False
            return True
        return False

    # --- Varsayılan görevler ---

    async def _task_log_cleanup(self) -> None:
        """Eski logları temizle."""
        from blue_ai.core.logger import get_logger
        logger = get_logger()
        deleted = logger.cleanup_old(days=30)
        self.logger.action(self.name, f"Log temizliği: {deleted} kayıt silindi")

    async def _task_metrics_cleanup(self) -> None:
        """Eski metrikleri temizle."""
        from blue_ai.core.logger import get_logger
        logger = get_logger()
        logger.cleanup_old(days=7)

    async def _task_health_check(self) -> None:
        """Sistem sağlık kontrolü."""
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage("C:\\").percent if psutil.disk_usage("C:\\") else 0

        if cpu > 90 or ram > 95 or disk > 95:
            self.logger.warning(
                self.name,
                f"Sağlık kontrolü uyarı — CPU: {cpu}%, RAM: {ram}%, Disk: {disk}%",
            )

    # --- Public API ---

    def get_tasks(self) -> list[dict[str, Any]]:
        """Tüm zamanlanmış görevleri listele."""
        return [
            {
                "name": t.name,
                "interval": t.interval_seconds,
                "run_when_idle": t.run_when_idle,
                "enabled": t.enabled,
                "last_run": t.last_run.isoformat() if t.last_run else None,
                "run_count": t.run_count,
                "last_error": t.last_error,
            }
            for t in self._tasks.values()
        ]

    def get_status(self) -> dict[str, Any]:
        base = super().get_status()
        base["task_count"] = len(self._tasks)
        base["active_tasks"] = sum(1 for t in self._tasks.values() if t.enabled)
        return base
