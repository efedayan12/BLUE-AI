"""
BLUE_AI Engine — Ana çekirdek motor.

Tüm bileşenleri orkestrasyonla birleştirir: Event Bus, Rule Engine, Plugin Manager.
"""

import asyncio
import signal
import sys
from pathlib import Path
from typing import Any

from blue_ai.core.config import load_config, get
from blue_ai.core.event_bus import Event, EventBus
from blue_ai.core.logger import get_logger
from blue_ai.core.plugin_manager import PluginManager
from blue_ai.core.rule_engine import RuleEngine


class BlueAIEngine:
    """BLUE_AI ana motoru."""

    def __init__(self, config_path: Path | None = None) -> None:
        self._config = load_config(config_path)
        self._logger = get_logger()
        self._event_bus = EventBus()
        self._rule_engine = RuleEngine()
        self._plugin_manager = PluginManager(self._event_bus, self._config)
        self._running = False
        self._current_profile = get("general.default_profile", "balanced")
        self._metrics_context: dict[str, float] = {}

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def rule_engine(self) -> RuleEngine:
        return self._rule_engine

    @property
    def plugin_manager(self) -> PluginManager:
        return self._plugin_manager

    @property
    def current_profile(self) -> str:
        return self._current_profile

    async def start(self) -> None:
        """Motoru başlat."""
        self._logger.info("Engine", "=" * 50)
        self._logger.info("Engine", "🔵 BLUE_AI Bilgisayar Yönetim Yapay Zekası")
        self._logger.info("Engine", f"   Sürüm: {get('general.version', '1.0.0')}")
        self._logger.info("Engine", f"   Profil: {self._current_profile}")
        self._logger.info("Engine", f"   Otomatik Aksiyon: {get('general.auto_action', True)}")
        self._logger.info("Engine", "=" * 50)

        # Varsayılan kuralları yükle
        rules_path = Path(__file__).parent.parent / "rules" / "default_rules.toml"
        if rules_path.exists():
            self._rule_engine.load_rules_from_toml(rules_path)

        # Metrikleri toplayan event handler
        self._event_bus.subscribe("metrics_update", self._on_metrics_update)

        # Plugin'leri keşfet ve yükle
        count = self._plugin_manager.discover_and_load()
        self._logger.info("Engine", f"{count} plugin yüklendi")

        # Plugin'leri başlat
        await self._plugin_manager.start_all()

        self._running = True

        # Event bus ve kural motoru döngüsünü başlat
        await asyncio.gather(
            self._event_bus.run(),
            self._rule_evaluation_loop(),
        )

    async def stop(self) -> None:
        """Motoru durdur."""
        self._logger.info("Engine", "🔴 BLUE_AI kapatılıyor...")
        self._running = False
        self._event_bus.stop()
        await self._plugin_manager.stop_all()
        self._logger.info("Engine", "BLUE_AI kapatıldı.")

    async def _on_metrics_update(self, event: Event) -> None:
        """Metrik güncellemelerini topla."""
        self._metrics_context.update(event.data)

    async def _rule_evaluation_loop(self) -> None:
        """Kural motoru değerlendirme döngüsü."""
        while self._running:
            try:
                if self._metrics_context:
                    triggered = self._rule_engine.evaluate(self._metrics_context)
                    for rule, action in triggered:
                        await self._execute_action(action, rule)
                await asyncio.sleep(2)  # 2 saniyede bir değerlendir
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error("Engine", f"Kural değerlendirme hatası: {e}")
                await asyncio.sleep(5)

    async def _execute_action(self, action: str, rule: Any) -> None:
        """Tetiklenen aksiyonu çalıştır."""
        auto_action = get("general.auto_action", True)

        if not auto_action:
            self._logger.warning(
                "Engine",
                f"Aksiyon bekliyor (manuel mod): {action}",
            )
            return

        # Aksiyonu event olarak yayınla — ilgili plugin yakalar
        await self._event_bus.emit(Event(
            name=f"action.{action}",
            data={"rule_name": rule.name, "params": rule.params},
            source="RuleEngine",
        ))

        self._logger.log_action(
            action_type=action,
            target=rule.name,
            result="executed",
            details=f"Kural: {rule.condition}",
        )

    def set_profile(self, profile_name: str) -> bool:
        """Aktif profili değiştir."""
        from blue_ai.core.config import get_profile
        profile = get_profile(profile_name)
        if profile:
            self._current_profile = profile_name
            self._logger.info("Engine", f"Profil değiştirildi: {profile_name}")
            # Profil değişikliğini tüm plugin'lere bildir
            asyncio.create_task(self._event_bus.emit(Event(
                name="profile_changed",
                data={"profile": profile_name, "settings": profile},
                source="Engine",
            )))
            return True
        return False

    def get_system_status(self) -> dict[str, Any]:
        """Genel sistem durumunu döndür."""
        return {
            "running": self._running,
            "profile": self._current_profile,
            "plugins": self._plugin_manager.get_all_status(),
            "event_stats": self._event_bus.stats,
            "rules_count": len(self._rule_engine.get_rules()),
            "metrics": dict(self._metrics_context),
        }
