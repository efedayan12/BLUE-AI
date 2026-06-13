"""
BLUE_AI Cleaner — Disk ve Registry temizlik.

Temp dosyalar, tarayıcı cache, Windows Update cache, geri dönüşüm kutusu.
"""

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any

from blue_ai.plugins.base import BasePlugin
from blue_ai.core.event_bus import Event
from blue_ai.utils.helpers import bytes_to_human, expand_env_path


class CleanerPlugin(BasePlugin):
    name = "cleaner"
    description = "Disk ve sistem temizliği"
    version = "1.0.0"

    def __init__(self, event_bus: Any, config: dict[str, Any]) -> None:
        super().__init__(event_bus, config)
        self._interval = config.get("polling", {}).get("cleanup_interval", 3600.0)
        self._clean_config = config.get("cleaner", {})
        self._last_cleanup_stats: dict[str, Any] = {}
        self._total_cleaned_bytes = 0

    def get_interval(self) -> float:
        return self._interval

    async def on_start(self) -> None:
        self.event_bus.subscribe("action.emergency_disk_cleanup", self._handle_emergency)

    async def on_stop(self) -> None:
        pass

    async def tick(self) -> None:
        auto_cleanup = self.config.get("profiles", {}).get(
            self.config.get("general", {}).get("default_profile", "balanced"), {}
        ).get("auto_cleanup", True)

        if auto_cleanup:
            stats = await self.clean_temp_files()
            if stats.get("total_cleaned", 0) > 0:
                self.logger.action(
                    self.name,
                    f"Otomatik temizlik: {bytes_to_human(stats['total_cleaned'])} temizlendi",
                )

    async def _handle_emergency(self, event: Event) -> None:
        """Acil disk temizliği."""
        self.logger.critical(self.name, "🚨 Acil disk temizliği başlatılıyor!")
        stats = await self.full_cleanup()
        self.logger.action(
            self.name,
            f"Acil temizlik tamamlandı: {bytes_to_human(stats['total_cleaned'])}",
        )

    # --- Public API ---

    async def clean_temp_files(self) -> dict[str, Any]:
        """Geçici dosyaları temizle."""
        def _clean() -> dict[str, Any]:
            total = 0
            file_count = 0
            errors = 0

            temp_dirs = self._clean_config.get("temp_dirs", ["$TEMP", "$TMP"])
            for td in temp_dirs:
                temp_path = expand_env_path(td)
                if not temp_path.exists():
                    continue

                for item in temp_path.iterdir():
                    try:
                        if item.is_file():
                            size = item.stat().st_size
                            item.unlink()
                            total += size
                            file_count += 1
                        elif item.is_dir():
                            size = sum(
                                f.stat().st_size
                                for f in item.rglob("*")
                                if f.is_file()
                            )
                            shutil.rmtree(item, ignore_errors=True)
                            total += size
                            file_count += 1
                    except (PermissionError, OSError):
                        errors += 1
                        continue

            return {
                "total_cleaned": total,
                "total_human": bytes_to_human(total),
                "files_deleted": file_count,
                "errors": errors,
            }

        stats = await asyncio.get_event_loop().run_in_executor(None, _clean)
        self._total_cleaned_bytes += stats["total_cleaned"]
        self._last_cleanup_stats = stats
        return stats

    async def clean_browser_cache(self) -> dict[str, Any]:
        """Tarayıcı cache temizliği."""
        def _clean() -> dict[str, Any]:
            total = 0
            cleaned_browsers: list[str] = []

            # Chrome cache
            chrome_cache = Path(os.environ.get("LOCALAPPDATA", "")) / r"Google\Chrome\User Data\Default\Cache"
            if chrome_cache.exists():
                size = sum(f.stat().st_size for f in chrome_cache.rglob("*") if f.is_file())
                shutil.rmtree(chrome_cache, ignore_errors=True)
                total += size
                cleaned_browsers.append("Chrome")

            # Edge cache
            edge_cache = Path(os.environ.get("LOCALAPPDATA", "")) / r"Microsoft\Edge\User Data\Default\Cache"
            if edge_cache.exists():
                size = sum(f.stat().st_size for f in edge_cache.rglob("*") if f.is_file())
                shutil.rmtree(edge_cache, ignore_errors=True)
                total += size
                cleaned_browsers.append("Edge")

            # Firefox cache
            ff_profiles = Path(os.environ.get("LOCALAPPDATA", "")) / r"Mozilla\Firefox\Profiles"
            if ff_profiles.exists():
                for profile in ff_profiles.iterdir():
                    cache = profile / "cache2"
                    if cache.exists():
                        size = sum(f.stat().st_size for f in cache.rglob("*") if f.is_file())
                        shutil.rmtree(cache, ignore_errors=True)
                        total += size
                if total > 0:
                    cleaned_browsers.append("Firefox")

            return {
                "total_cleaned": total,
                "total_human": bytes_to_human(total),
                "browsers": cleaned_browsers,
            }

        return await asyncio.get_event_loop().run_in_executor(None, _clean)

    async def clean_recycle_bin(self) -> bool:
        """Geri dönüşüm kutusunu boşalt."""
        try:
            import ctypes
            # SHEmptyRecycleBin API
            SHERB_NOCONFIRMATION = 0x00000001
            SHERB_NOPROGRESSUI = 0x00000002
            SHERB_NOSOUND = 0x00000004
            flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
            self.logger.action(self.name, "Geri dönüşüm kutusu boşaltıldı")
            return True
        except Exception:
            return False

    async def clean_windows_update_cache(self) -> dict[str, Any]:
        """Windows Update cache temizliği."""
        def _clean() -> dict[str, Any]:
            total = 0
            wu_path = Path(r"C:\Windows\SoftwareDistribution\Download")
            if wu_path.exists():
                try:
                    for item in wu_path.iterdir():
                        try:
                            if item.is_file():
                                total += item.stat().st_size
                                item.unlink()
                            elif item.is_dir():
                                total += sum(
                                    f.stat().st_size for f in item.rglob("*") if f.is_file()
                                )
                                shutil.rmtree(item, ignore_errors=True)
                        except (PermissionError, OSError):
                            continue
                except (PermissionError, OSError):
                    pass
            return {"total_cleaned": total, "total_human": bytes_to_human(total)}

        return await asyncio.get_event_loop().run_in_executor(None, _clean)

    async def full_cleanup(self) -> dict[str, Any]:
        """Tam temizlik — tüm temizlik işlemlerini çalıştır."""
        results: dict[str, Any] = {}
        total = 0

        # Temp dosyalar
        temp = await self.clean_temp_files()
        results["temp_files"] = temp
        total += temp["total_cleaned"]

        # Tarayıcı cache
        if self._clean_config.get("browser_cache", True):
            browser = await self.clean_browser_cache()
            results["browser_cache"] = browser
            total += browser["total_cleaned"]

        # Windows Update cache
        if self._clean_config.get("windows_update_cache", True):
            wu = await self.clean_windows_update_cache()
            results["windows_update"] = wu
            total += wu["total_cleaned"]

        results["total_cleaned"] = total
        results["total_human"] = bytes_to_human(total)

        self._total_cleaned_bytes += total
        return results

    async def analyze_disk_usage(self, path: str = "C:\\") -> list[dict[str, Any]]:
        """Disk kullanım analizi — en büyük dizinler."""
        def _analyze() -> list[dict[str, Any]]:
            root = Path(path)
            dirs = []
            try:
                for entry in root.iterdir():
                    if entry.is_dir():
                        try:
                            size = sum(
                                f.stat().st_size
                                for f in entry.rglob("*")
                                if f.is_file()
                            )
                            dirs.append({
                                "path": str(entry),
                                "size": size,
                                "size_human": bytes_to_human(size),
                            })
                        except (PermissionError, OSError):
                            continue
            except (PermissionError, OSError):
                pass
            dirs.sort(key=lambda x: x["size"], reverse=True)
            return dirs[:20]

        return await asyncio.get_event_loop().run_in_executor(None, _analyze)

    def get_status(self) -> dict[str, Any]:
        base = super().get_status()
        base["total_cleaned"] = bytes_to_human(self._total_cleaned_bytes)
        base["last_cleanup"] = self._last_cleanup_stats
        return base
