"""
BLUE_AI Windows API Yardımcıları.

ctypes ile doğrudan Windows API erişimi sağlar.
"""

import ctypes
import ctypes.wintypes
from typing import Any


# Windows API sabitleri
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_SET_INFORMATION = 0x0200
PROCESS_TERMINATE = 0x0001
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
SE_PRIVILEGE_ENABLED = 0x00000002

# Öncelik sınıfları
IDLE_PRIORITY_CLASS = 0x00000040
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
NORMAL_PRIORITY_CLASS = 0x00000020
ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000
HIGH_PRIORITY_CLASS = 0x00000080
REALTIME_PRIORITY_CLASS = 0x00000100

PRIORITY_MAP = {
    "idle": IDLE_PRIORITY_CLASS,
    "below_normal": BELOW_NORMAL_PRIORITY_CLASS,
    "normal": NORMAL_PRIORITY_CLASS,
    "above_normal": ABOVE_NORMAL_PRIORITY_CLASS,
    "high": HIGH_PRIORITY_CLASS,
    "realtime": REALTIME_PRIORITY_CLASS,
}


def is_admin() -> bool:
    """Yönetici yetkileriyle çalışıp çalışmadığını kontrol et."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def set_process_priority(pid: int, priority: str) -> bool:
    """Sürecin öncelik sınıfını değiştir."""
    priority_class = PRIORITY_MAP.get(priority.lower())
    if priority_class is None:
        return False

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_SET_INFORMATION, False, pid)
    if not handle:
        return False

    try:
        result = kernel32.SetPriorityClass(handle, priority_class)
        return bool(result)
    finally:
        kernel32.CloseHandle(handle)


def set_process_affinity(pid: int, cpu_mask: int) -> bool:
    """Sürecin CPU affinity'sini ayarla."""
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_SET_INFORMATION, False, pid)
    if not handle:
        return False

    try:
        result = kernel32.SetProcessAffinityMask(handle, cpu_mask)
        return bool(result)
    finally:
        kernel32.CloseHandle(handle)


def get_system_power_status() -> dict[str, Any]:
    """Sistem güç durumunu al."""

    class SYSTEM_POWER_STATUS(ctypes.Structure):
        _fields_ = [
            ("ACLineStatus", ctypes.c_byte),
            ("BatteryFlag", ctypes.c_byte),
            ("BatteryLifePercent", ctypes.c_byte),
            ("SystemStatusFlag", ctypes.c_byte),
            ("BatteryLifeTime", ctypes.wintypes.DWORD),
            ("BatteryFullLifeTime", ctypes.wintypes.DWORD),
        ]

    status = SYSTEM_POWER_STATUS()
    ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))

    return {
        "ac_plugged": status.ACLineStatus == 1,
        "battery_percent": status.BatteryLifePercent if status.BatteryLifePercent <= 100 else -1,
        "battery_charging": bool(status.BatteryFlag & 8),
        "battery_life_seconds": status.BatteryLifeTime if status.BatteryLifeTime != 0xFFFFFFFF else -1,
        "has_battery": status.BatteryFlag != 128,
    }


def empty_working_set(pid: int) -> bool:
    """Sürecin working set'ini boşalt (RAM temizle)."""
    try:
        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi

        handle = kernel32.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_SET_INFORMATION, False, pid
        )
        if not handle:
            return False

        try:
            result = psapi.EmptyWorkingSet(handle)
            return bool(result)
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return False


def flash_taskbar_icon() -> None:
    """Taskbar ikonunu yanıp söndür (bildirim)."""
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.FlashWindow(hwnd, True)
    except Exception:
        pass


def get_idle_time_ms() -> int:
    """Sistemin boşta kalma süresini milisaniye cinsinden al."""

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_uint),
            ("dwTime", ctypes.c_uint),
        ]

    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
    current_tick = ctypes.windll.kernel32.GetTickCount()
    return current_tick - lii.dwTime


def set_power_scheme(scheme: str) -> bool:
    """Güç şemasını değiştir.

    Şemalar:
        balanced: 381b4222-f694-41f0-9685-ff5bb260df2e
        high_performance: 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c
        power_saver: a1841308-3541-4fab-bc81-f71556f20b4a
    """
    schemes = {
        "balanced": "381b4222-f694-41f0-9685-ff5bb260df2e",
        "high_performance": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
        "power_saver": "a1841308-3541-4fab-bc81-f71556f20b4a",
    }
    guid = schemes.get(scheme.lower())
    if not guid:
        return False

    import subprocess
    try:
        subprocess.run(
            ["powercfg", "/setactive", guid],
            capture_output=True,
            check=True,
        )
        return True
    except Exception:
        return False
