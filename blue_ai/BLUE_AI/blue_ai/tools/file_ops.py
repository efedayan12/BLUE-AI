"""
BLUE_AI — Dosya Islemleri Araci

Dosya arama, taşıma, kopyalama, silme, yeniden adlandirma.
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
from blue_ai.utils.helpers import bytes_to_human


def find_files(query: str, search_dir: str = None, max_results: int = 20) -> list[dict]:
    """Dosya ara."""
    if not search_dir:
        search_dir = str(Path.home())

    results = []
    query_lower = query.lower()

    try:
        for root, dirs, files in os.walk(search_dir):
            # Sistem klasorlerini atla
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                       ('AppData', 'node_modules', '.git', '__pycache__', 'Windows')]

            for fname in files:
                if query_lower in fname.lower():
                    fpath = os.path.join(root, fname)
                    try:
                        stat = os.stat(fpath)
                        results.append({
                            "name": fname,
                            "path": fpath,
                            "size": bytes_to_human(stat.st_size),
                            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M"),
                        })
                    except (OSError, PermissionError):
                        continue

                    if len(results) >= max_results:
                        return results
    except (OSError, PermissionError):
        pass

    return results


def list_directory(dir_path: str) -> list[dict]:
    """Dizin icerigini listele."""
    items = []
    try:
        for entry in os.scandir(dir_path):
            try:
                stat = entry.stat()
                items.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size": bytes_to_human(stat.st_size) if not entry.is_dir() else "",
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M"),
                })
            except (OSError, PermissionError):
                continue
    except (OSError, PermissionError):
        return [{"error": f"Erisim hatasi: {dir_path}"}]

    items.sort(key=lambda x: (not x.get("is_dir", False), x.get("name", "").lower()))
    return items


def move_file(source: str, destination: str) -> dict:
    """Dosya tasi."""
    try:
        shutil.move(source, destination)
        return {"success": True, "message": f"Taşindi: {source} -> {destination}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def copy_file(source: str, destination: str) -> dict:
    """Dosya kopyala."""
    try:
        if os.path.isdir(source):
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        return {"success": True, "message": f"Kopyalandı: {source} -> {destination}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def rename_file(old_path: str, new_name: str) -> dict:
    """Dosya yeniden adlandir."""
    try:
        new_path = os.path.join(os.path.dirname(old_path), new_name)
        os.rename(old_path, new_path)
        return {"success": True, "message": f"Yeniden adlandirildi: {new_name}", "new_path": new_path}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_large_files(directory: str = None, min_size_mb: int = 100, max_results: int = 20) -> list[dict]:
    """Buyuk dosyalari bul."""
    if not directory:
        directory = str(Path.home())

    min_size = min_size_mb * 1024 * 1024
    results = []

    try:
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                       ('AppData', 'node_modules', 'Windows')]

            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    size = os.path.getsize(fpath)
                    if size >= min_size:
                        results.append({
                            "name": fname,
                            "path": fpath,
                            "size": bytes_to_human(size),
                            "size_bytes": size,
                        })
                except (OSError, PermissionError):
                    continue

                if len(results) >= max_results:
                    break
    except (OSError, PermissionError):
        pass

    results.sort(key=lambda x: x.get("size_bytes", 0), reverse=True)
    return results
