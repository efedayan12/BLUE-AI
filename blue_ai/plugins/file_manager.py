"""
BLUE_AI File Manager — Dosya yönetimi, arama, organizasyon, yedekleme.

Büyük dosya tespiti, duplicate arama, otomatik organizasyon, watchdog izleme.
"""

import asyncio
import os
import shutil
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from blue_ai.plugins.base import BasePlugin
from blue_ai.utils.helpers import bytes_to_human, file_hash


class FileManagerPlugin(BasePlugin):
    name = "file_manager"
    description = "Dosya yönetimi, arama ve organizasyon"
    version = "1.0.0"

    def __init__(self, event_bus: Any, config: dict[str, Any]) -> None:
        super().__init__(event_bus, config)
        self._interval = config.get("polling", {}).get("file_watch_interval", 10.0)
        self._large_files: list[dict[str, Any]] = []
        self._duplicates: list[dict[str, Any]] = []
        self._scan_running = False
        self._watch_dirs: list[Path] = [
            Path.home() / "Downloads",
            Path.home() / "Desktop",
        ]

    def get_interval(self) -> float:
        return self._interval

    async def on_start(self) -> None:
        self.logger.info(self.name, f"Dosya izleme dizinleri: {[str(d) for d in self._watch_dirs]}")

    async def on_stop(self) -> None:
        pass

    async def tick(self) -> None:
        # Periyodik olarak indirilenler klasörünü kontrol et
        downloads = Path.home() / "Downloads"
        if downloads.exists():
            await asyncio.get_event_loop().run_in_executor(
                None, self._check_downloads_size, downloads
            )

    def _check_downloads_size(self, path: Path) -> None:
        """İndirilenler klasörünün boyutunu kontrol et."""
        try:
            total_size = sum(
                f.stat().st_size for f in path.rglob("*") if f.is_file()
            )
            if total_size > 5 * 1024 * 1024 * 1024:  # 5 GB
                self.logger.warning(
                    self.name,
                    f"İndirilenler klasörü büyük: {bytes_to_human(total_size)}",
                )
        except Exception:
            pass

    # --- Public API ---

    async def find_large_files(
        self, path: Path | None = None, min_size_mb: float = 100, max_results: int = 50
    ) -> list[dict[str, Any]]:
        """Büyük dosyaları bul."""
        search_path = path or Path.home()
        min_bytes = int(min_size_mb * 1024 * 1024)

        def _scan() -> list[dict[str, Any]]:
            results = []
            try:
                for f in search_path.rglob("*"):
                    if f.is_file():
                        try:
                            size = f.stat().st_size
                            if size >= min_bytes:
                                results.append({
                                    "path": str(f),
                                    "size": size,
                                    "size_human": bytes_to_human(size),
                                    "modified": time.ctime(f.stat().st_mtime),
                                    "extension": f.suffix.lower(),
                                })
                        except (PermissionError, OSError):
                            continue
            except (PermissionError, OSError):
                pass
            results.sort(key=lambda x: x["size"], reverse=True)
            return results[:max_results]

        self._large_files = await asyncio.get_event_loop().run_in_executor(None, _scan)
        return self._large_files

    async def find_duplicates(self, path: Path | None = None) -> list[dict[str, Any]]:
        """Hash tabanlı duplicate dosya tespiti."""
        search_path = path or (Path.home() / "Downloads")

        def _scan() -> list[dict[str, Any]]:
            # Önce boyuta göre grupla (hızlı ön filtreleme)
            size_groups: dict[int, list[Path]] = defaultdict(list)
            try:
                for f in search_path.rglob("*"):
                    if f.is_file():
                        try:
                            size = f.stat().st_size
                            if size > 1024:  # 1KB'den küçükleri atla
                                size_groups[size].append(f)
                        except (PermissionError, OSError):
                            continue
            except (PermissionError, OSError):
                pass

            # Aynı boyuttaki dosyaları hash'le
            duplicates = []
            for size, files in size_groups.items():
                if len(files) < 2:
                    continue

                hash_groups: dict[str, list[Path]] = defaultdict(list)
                for f in files:
                    try:
                        h = file_hash(f)
                        hash_groups[h].append(f)
                    except Exception:
                        continue

                for h, group in hash_groups.items():
                    if len(group) >= 2:
                        duplicates.append({
                            "hash": h,
                            "size": size,
                            "size_human": bytes_to_human(size),
                            "files": [str(f) for f in group],
                            "count": len(group),
                        })

            duplicates.sort(key=lambda x: x["size"], reverse=True)
            return duplicates

        self._duplicates = await asyncio.get_event_loop().run_in_executor(None, _scan)
        return self._duplicates

    async def organize_directory(self, path: Path | None = None) -> dict[str, int]:
        """Dosyaları türlerine göre organize et."""
        target = path or (Path.home() / "Downloads")

        categories = {
            "Resimler": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico"},
            "Belgeler": {".pdf", ".doc", ".docx", ".txt", ".xlsx", ".pptx", ".csv", ".odt"},
            "Videolar": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"},
            "Müzik": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"},
            "Arsivler": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"},
            "Programlar": {".exe", ".msi", ".dmg", ".deb", ".rpm"},
            "Kod": {".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".sql"},
        }

        def _organize() -> dict[str, int]:
            counts: dict[str, int] = defaultdict(int)
            try:
                for f in target.iterdir():
                    if not f.is_file():
                        continue

                    ext = f.suffix.lower()
                    dest_folder = None
                    for cat, exts in categories.items():
                        if ext in exts:
                            dest_folder = cat
                            break

                    if dest_folder is None:
                        dest_folder = "Diğer"

                    dest_dir = target / dest_folder
                    dest_dir.mkdir(exist_ok=True)
                    dest_path = dest_dir / f.name

                    if dest_path.exists():
                        # İsim çakışması — numara ekle
                        stem = f.stem
                        i = 1
                        while dest_path.exists():
                            dest_path = dest_dir / f"{stem}_{i}{f.suffix}"
                            i += 1

                    shutil.move(str(f), str(dest_path))
                    counts[dest_folder] += 1
            except Exception as e:
                pass

            return dict(counts)

        result = await asyncio.get_event_loop().run_in_executor(None, _organize)
        total = sum(result.values())
        self.logger.action(self.name, f"Organize edildi: {total} dosya, {len(result)} kategori")
        return result

    async def get_directory_size(self, path: Path) -> dict[str, Any]:
        """Dizin boyutunu hesapla."""
        def _calc() -> dict[str, Any]:
            total = 0
            file_count = 0
            dir_count = 0
            try:
                for entry in path.rglob("*"):
                    if entry.is_file():
                        total += entry.stat().st_size
                        file_count += 1
                    elif entry.is_dir():
                        dir_count += 1
            except (PermissionError, OSError):
                pass
            return {
                "path": str(path),
                "total_size": total,
                "total_human": bytes_to_human(total),
                "file_count": file_count,
                "dir_count": dir_count,
            }

        return await asyncio.get_event_loop().run_in_executor(None, _calc)

    def get_status(self) -> dict[str, Any]:
        base = super().get_status()
        base["large_files_found"] = len(self._large_files)
        base["duplicates_found"] = len(self._duplicates)
        return base
