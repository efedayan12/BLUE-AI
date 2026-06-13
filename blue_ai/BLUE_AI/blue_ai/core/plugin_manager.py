"""
BLUE_AI Plugin Manager — Dinamik plugin keşfi, yükleme ve yönetim.
"""

import importlib
from typing import Any

from blue_ai.core.config import get_plugin_enabled
from blue_ai.core.event_bus import EventBus
from blue_ai.core.logger import get_logger
from blue_ai.plugins.base import BasePlugin


# Plugin modül adı → sınıf adı eşleştirmesi
_PLUGIN_REGISTRY: dict[str, str] = {
    "system_monitor": "SystemMonitorPlugin",
    "process_manager": "ProcessManagerPlugin",
    "file_manager": "FileManagerPlugin",
    "performance": "PerformancePlugin",
    "security": "SecurityPlugin",
    "network": "NetworkPlugin",
    "scheduler": "SchedulerPlugin",
    "startup": "StartupPlugin",
    "cleaner": "CleanerPlugin",
    "power": "PowerPlugin",
    "updater": "UpdaterPlugin",
}


class PluginManager:
    """Plugin yaşam döngüsü yöneticisi."""

    def __init__(self, event_bus: EventBus, config: dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._config = config
        self._plugins: dict[str, BasePlugin] = {}
        self._logger = get_logger()

    def discover_and_load(self) -> int:
        """Kayıtlı tüm plugin'leri keşfet ve yükle."""
        count = 0
        for module_name, class_name in _PLUGIN_REGISTRY.items():
            if not get_plugin_enabled(module_name):
                self._logger.info("PluginManager", f"Plugin devre dışı: {module_name}")
                continue

            try:
                module = importlib.import_module(f"blue_ai.plugins.{module_name}")
                plugin_class = getattr(module, class_name)

                if not issubclass(plugin_class, BasePlugin):
                    self._logger.warning(
                        "PluginManager",
                        f"{class_name} BasePlugin'den türemiyor, atlanıyor",
                    )
                    continue

                plugin = plugin_class(
                    event_bus=self._event_bus,
                    config=self._config,
                )
                self._plugins[module_name] = plugin
                count += 1
                self._logger.info("PluginManager", f"Plugin yüklendi: {module_name}")

            except Exception as e:
                self._logger.error(
                    "PluginManager",
                    f"Plugin yükleme hatası: {module_name} — {e}",
                )

        return count

    async def start_all(self) -> None:
        """Tüm plugin'leri başlat."""
        for name, plugin in self._plugins.items():
            try:
                await plugin.start()
            except Exception as e:
                self._logger.error("PluginManager", f"Başlatma hatası: {name} — {e}")

    async def stop_all(self) -> None:
        """Tüm plugin'leri durdur."""
        for name, plugin in reversed(list(self._plugins.items())):
            try:
                await plugin.stop()
            except Exception as e:
                self._logger.error("PluginManager", f"Durdurma hatası: {name} — {e}")

    def get_plugin(self, name: str) -> BasePlugin | None:
        """İsimle plugin al."""
        return self._plugins.get(name)

    def get_all_plugins(self) -> dict[str, BasePlugin]:
        """Tüm yüklü plugin'leri döndür."""
        return dict(self._plugins)

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Tüm plugin durumlarını döndür."""
        return {name: plugin.get_status() for name, plugin in self._plugins.items()}

    async def restart_plugin(self, name: str) -> bool:
        """Tek bir plugin'i yeniden başlat."""
        plugin = self._plugins.get(name)
        if plugin is None:
            return False
        try:
            await plugin.stop()
            await plugin.start()
            self._logger.info("PluginManager", f"Plugin yeniden başlatıldı: {name}")
            return True
        except Exception as e:
            self._logger.error("PluginManager", f"Yeniden başlatma hatası: {name} — {e}")
            return False
