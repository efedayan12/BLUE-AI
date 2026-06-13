"""
BLUE_AI Event Bus — Asenkron Pub/Sub olay dağıtım sistemi.

Modüller arası gevşek bağlı iletişim sağlar.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Callable, Coroutine


class EventPriority(IntEnum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Event:
    """Sistem olayı."""
    name: str
    data: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    priority: EventPriority = EventPriority.NORMAL
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# Handler tipi: async callable
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Asenkron Pub/Sub olay yöneticisi."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[tuple[EventPriority, EventHandler]]] = defaultdict(list)
        self._global_handlers: list[tuple[EventPriority, EventHandler]] = []
        self._event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self._running = False
        self._history: list[Event] = []
        self._max_history = 500

    def subscribe(
        self,
        event_name: str,
        handler: EventHandler,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> None:
        """Belirli bir olay adına abone ol."""
        self._handlers[event_name].append((priority, handler))
        # Önceliğe göre sırala (yüksek öncelik önce)
        self._handlers[event_name].sort(key=lambda x: x[0], reverse=True)

    def subscribe_all(
        self,
        handler: EventHandler,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> None:
        """Tüm olaylara abone ol."""
        self._global_handlers.append((priority, handler))
        self._global_handlers.sort(key=lambda x: x[0], reverse=True)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        """Aboneliği iptal et."""
        self._handlers[event_name] = [
            (p, h) for p, h in self._handlers[event_name] if h is not handler
        ]

    async def emit(self, event: Event) -> None:
        """Olayı kuyruğa ekle."""
        await self._event_queue.put(event)

    def emit_sync(self, event: Event) -> None:
        """Senkron olarak olay yayınla (asyncio dışından)."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._event_queue.put(event))
        except RuntimeError:
            # Eğer event loop yoksa, yeni bir tane oluştur
            pass

    async def emit_now(self, event: Event) -> None:
        """Olayı hemen işle (kuyruk atlanır)."""
        await self._dispatch(event)

    async def _dispatch(self, event: Event) -> None:
        """Olayı ilgili handler'lara dağıt."""
        # Geçmişe ekle
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # Spesifik handler'lar
        handlers = self._handlers.get(event.name, [])
        # Global handler'lar
        all_handlers = handlers + self._global_handlers

        # Önceliğe göre sıralı çalıştır
        all_handlers.sort(key=lambda x: x[0], reverse=True)

        tasks = []
        for _, handler in all_handlers:
            tasks.append(asyncio.create_task(self._safe_call(handler, event)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_call(self, handler: EventHandler, event: Event) -> None:
        """Handler'ı güvenli şekilde çağır."""
        try:
            await handler(event)
        except Exception as e:
            # Handler hatası sistemi çökertmemeli
            pass

    async def run(self) -> None:
        """Olay döngüsünü başlat."""
        self._running = True
        while self._running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=0.5)
                await self._dispatch(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    def stop(self) -> None:
        """Olay döngüsünü durdur."""
        self._running = False

    def get_history(self, event_name: str | None = None, limit: int = 50) -> list[Event]:
        """Olay geçmişini getir."""
        if event_name:
            filtered = [e for e in self._history if e.name == event_name]
        else:
            filtered = self._history
        return filtered[-limit:]

    @property
    def stats(self) -> dict[str, int]:
        """Olay istatistikleri."""
        counts: dict[str, int] = defaultdict(int)
        for event in self._history:
            counts[event.name] += 1
        return dict(counts)
