"""
BLUE_AI Power — Güç yönetimi.

Pil izleme, güç profili değiştirme, enerji tasarrufu.
"""

import asyncio
from typing import Any

from blue_ai.plugins.base import BasePlugin
from blue_ai.core.event_bus import Event
from blue_ai.utils.win_api import get_system_power_status, set_power_scheme


class PowerPlugin(BasePlugin):
    name = "power"
    description = "Güç yönetimi ve enerji optimizasyonu"
    version = "1.0.0"

    def __init__(self, event_bus: Any, config: dict[str, Any]) -> None:
        super().__init__(event_bus, config)
        self._interval = 30.0  # 30 saniyede bir kontrol
        self._power_status: dict[str, Any] = {}
        self._profile_auto_switched = False

    def get_interval(self) -> float:
        return self._interval

    async def on_start(self) -> None:
        self.event_bus.subscribe("action.switch_power_saver", self._handle_switch_saver)
        self.event_bus.subscribe("action.emergency_power_save", self._handle_emergency_save)
        self.event_bus.subscribe("profile_changed", self._handle_profile_change)

        # İlk güç durumu
        self._power_status = get_system_power_status()
        if self._power_status.get("has_battery"):
            self.logger.info(
                self.name,
                f"Pil durumu: %{self._power_status.get('battery_percent', -1)} | "
                f"Şarjda: {'Evet' if self._power_status.get('ac_plugged') else 'Hayır'}",
            )
        else:
            self.logger.info(self.name, "Masaüstü bilgisayar — pil yok")

    async def on_stop(self) -> None:
        pass

    async def tick(self) -> None:
        self._power_status = await asyncio.get_event_loop().run_in_executor(
            None, get_system_power_status
        )

        battery = self._power_status.get("battery_percent", -1)
        if battery >= 0:
            await self.emit("metrics_update", {"battery_percent": float(battery)})

            # Otomatik güç profili geçişi
            ac = self._power_status.get("ac_plugged", True)
            if not ac and battery < 20 and not self._profile_auto_switched:
                self._profile_auto_switched = True
                await self._switch_to_power_saver()
            elif ac and self._profile_auto_switched:
                self._profile_auto_switched = False
                await self._switch_to_balanced()

    async def _handle_switch_saver(self, event: Event) -> None:
        """Güç tasarrufuna geç."""
        await self._switch_to_power_saver()

    async def _handle_emergency_save(self, event: Event) -> None:
        """Acil güç tasarrufu."""
        self.logger.critical(self.name, "🔋 Acil güç tasarrufu aktif — Pil kritik!")
        await self._switch_to_power_saver()

        # Ek tasarruf aksiyonları
        await self.emit("action.cleanup_ram", {})

    async def _switch_to_power_saver(self) -> None:
        """Güç tasarrufu moduna geç."""
        success = await asyncio.get_event_loop().run_in_executor(
            None, set_power_scheme, "power_saver"
        )
        if success:
            self.logger.action(self.name, "Güç planı değiştirildi: Güç Tasarrufu")
        else:
            self.logger.warning(self.name, "Güç planı değiştirilemedi")

    async def _switch_to_balanced(self) -> None:
        """Dengeli moda geç."""
        success = await asyncio.get_event_loop().run_in_executor(
            None, set_power_scheme, "balanced"
        )
        if success:
            self.logger.action(self.name, "Güç planı değiştirildi: Dengeli")

    async def _handle_profile_change(self, event: Event) -> None:
        """Profil değişikliğinde güç planını güncelle."""
        profile = event.data.get("settings", {})
        power_plan = profile.get("power_plan", "balanced")
        await asyncio.get_event_loop().run_in_executor(
            None, set_power_scheme, power_plan
        )

    # --- Public API ---

    def get_power_status(self) -> dict[str, Any]:
        """Güncel güç durumunu döndür."""
        return dict(self._power_status)

    async def set_power_plan(self, plan: str) -> bool:
        """Güç planını değiştir (balanced, high_performance, power_saver)."""
        success = await asyncio.get_event_loop().run_in_executor(
            None, set_power_scheme, plan
        )
        if success:
            self.logger.action(self.name, f"Güç planı değiştirildi: {plan}")
        return success

    def get_status(self) -> dict[str, Any]:
        base = super().get_status()
        base["power"] = self._power_status
        return base
