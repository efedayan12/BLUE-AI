"""
BLUE_AI Base Plugin — Tüm plugin'lerin temel sınıfı.

Her plugin bu sınıftan türemeli ve gerekli metodları uygulamalıdır.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from blue_ai.core.event_bus import Event, EventBus
from blue_ai.core.logger import get_logger


class BasePlugin(ABC):
    """Plugin temel sınıfı."""

    # Alt sınıflar bu değerleri override etmeli
    name: str = "base_plugin"
    description: str = "Base plugin"
    version: str = "1.0.0"

    def __init__(self, event_bus: EventBus, config: dict[str, Any]) -> None:
        self.event_bus = event_bus
        self.config = config
        self.logger = get_logger()
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Plugin'i başlat."""
        self._running = True
        self.logger.info(self.name, f"Plugin başlatıldı: {self.description}")
        await self.on_start()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Plugin'i durdur."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.on_stop()
        self.logger.info(self.name, "Plugin durduruldu")

    async def _run_loop(self) -> None:
        """Ana çalışma döngüsü."""
        while self._running:
            try:
                await self.tick()
                await asyncio.sleep(self.get_interval())
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(self.name, f"Tick hatası: {e}")
                await asyncio.sleep(5)  # Hata durumunda bekle

    def get_interval(self) -> float:
        """Tick aralığını döndür (saniye). Alt sınıflar override edebilir."""
        return 5.0

    async def emit(self, event_name: str, data: dict[str, Any] | None = None) -> None:
        """Olay yayınla."""
        event = Event(name=event_name, data=data or {}, source=self.name)
        await self.event_bus.emit(event)

    # --- Alt sınıfların uygulaması gereken metodlar ---

    @abstractmethod
    async def on_start(self) -> None:
        """Plugin başlatılırken çağrılır."""
        ...

    @abstractmethod
    async def on_stop(self) -> None:
        """Plugin durdurulurken çağrılır."""
        ...

    @abstractmethod
    async def tick(self) -> None:
        """Periyodik olarak çağrılan ana iş metodu."""
        ...

    async def handle_event(self, event: Event) -> None:
        """Gelen olaylara tepki ver. Alt sınıflar override edebilir."""
        pass

    def get_status(self) -> dict[str, Any]:
        """Plugin durumunu döndür. Alt sınıflar override edebilir."""
        return {
            "name": self.name,
            "running": self._running,
            "version": self.version,
            "description": self.description,
        }
