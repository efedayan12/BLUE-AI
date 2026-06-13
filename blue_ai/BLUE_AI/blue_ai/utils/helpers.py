"""
BLUE_AI Helpers — Genel yardımcı fonksiyonlar.
"""

import os
import hashlib
from pathlib import Path
from typing import Any


def bytes_to_human(n: float) -> str:
    """Byte değerini okunabilir formata çevir."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def seconds_to_human(seconds: float) -> str:
    """Saniyeyi okunabilir süreye çevir."""
    if seconds < 60:
        return f"{seconds:.0f}sn"
    elif seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}dk {s}sn"
    elif seconds < 86400:
        h, remainder = divmod(int(seconds), 3600)
        m, s = divmod(remainder, 60)
        return f"{h}sa {m}dk"
    else:
        d, remainder = divmod(int(seconds), 86400)
        h, _ = divmod(remainder, 3600)
        return f"{d}gün {h}sa"


def file_hash(filepath: Path, algorithm: str = "md5") -> str:
    """Dosyanın hash'ini hesapla."""
    h = hashlib.new(algorithm)
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def expand_env_path(path_str: str) -> Path:
    """Ortam değişkenlerini genişlet ($TEMP → gerçek yol)."""
    expanded = os.path.expandvars(path_str)
    return Path(expanded)


def safe_divide(a: float, b: float, default: float = 0.0) -> float:
    """Güvenli bölme (sıfıra bölme koruması)."""
    if b == 0:
        return default
    return a / b


def truncate(text: str, max_length: int = 60) -> str:
    """Metni maksimum uzunlukta kes."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def is_system_process(name: str) -> bool:
    """Kritik sistem süreci olup olmadığını kontrol et."""
    system_processes = {
        "system", "idle", "registry", "smss.exe", "csrss.exe",
        "wininit.exe", "services.exe", "lsass.exe", "svchost.exe",
        "dwm.exe", "explorer.exe", "winlogon.exe", "fontdrvhost.exe",
        "sihost.exe", "taskhostw.exe", "ctfmon.exe", "runtimebroker.exe",
        "searchhost.exe", "startmenuexperiencehost.exe",
        "textinputhost.exe", "shellexperiencehost.exe",
    }
    return name.lower() in system_processes


def get_temp_dirs() -> list[Path]:
    """Geçici dizinleri döndür."""
    dirs = []
    for var in ("TEMP", "TMP"):
        val = os.environ.get(var)
        if val:
            p = Path(val)
            if p.exists():
                dirs.append(p)

    # Windows genel temp
    win_temp = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Temp"
    if win_temp.exists() and win_temp not in dirs:
        dirs.append(win_temp)

    return dirs
