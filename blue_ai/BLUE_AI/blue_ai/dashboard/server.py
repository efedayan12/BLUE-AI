"""
BLUE_AI Dashboard — FastAPI + HTMX web dashboard.

Gerçek zamanlı sistem izleme paneli.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import psutil

from blue_ai.core.config import load_config, get_profile
from blue_ai.utils.helpers import bytes_to_human, seconds_to_human
from blue_ai.utils.win_api import get_system_power_status


TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    """FastAPI uygulaması oluştur."""
    app = FastAPI(title="BLUE_AI Dashboard", version="1.0.0")

    # Statik dosyalar
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Templates
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    # ----- Routes -----

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/api/system")
    async def api_system():
        """Sistem metrikleri API."""
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, _get_system_data)
        return JSONResponse(data)

    @app.get("/api/processes")
    async def api_processes():
        """Süreç listesi API."""
        loop = asyncio.get_event_loop()
        procs = await loop.run_in_executor(None, _get_processes)
        return JSONResponse(procs)

    @app.get("/api/network")
    async def api_network():
        """Ağ bilgileri API."""
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, _get_network_data)
        return JSONResponse(data)

    @app.get("/api/disks")
    async def api_disks():
        """Disk bilgileri API."""
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, _get_disk_data)
        return JSONResponse(data)

    @app.post("/api/profile/{name}")
    async def api_set_profile(name: str):
        """Profil değiştir."""
        from blue_ai.utils.win_api import set_power_scheme
        profile = get_profile(name)
        if profile:
            power_plan = profile.get("power_plan", "balanced")
            set_power_scheme(power_plan)
            return JSONResponse({"success": True, "profile": name})
        return JSONResponse({"success": False, "error": "Profil bulunamadı"}, status_code=400)

    @app.post("/api/process/{pid}/kill")
    async def api_kill_process(pid: int):
        """Süreci sonlandır."""
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            return JSONResponse({"success": True})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

    return app


def _get_system_data() -> dict[str, Any]:
    """Sistem metriklerini topla."""
    import time

    cpu_percent = psutil.cpu_percent(interval=None)
    cpu_per_core = psutil.cpu_percent(percpu=True)
    cpu_freq = psutil.cpu_freq()
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    power = get_system_power_status()
    boot_time = time.time() - psutil.boot_time()

    return {
        "cpu": {
            "percent": cpu_percent,
            "per_core": cpu_per_core,
            "freq": cpu_freq.current if cpu_freq else 0,
            "cores": psutil.cpu_count(),
        },
        "ram": {
            "percent": ram.percent,
            "used": bytes_to_human(ram.used),
            "total": bytes_to_human(ram.total),
            "available": bytes_to_human(ram.available),
        },
        "disk": {
            "percent": disk.percent,
            "used": bytes_to_human(disk.used),
            "total": bytes_to_human(disk.total),
            "free": bytes_to_human(disk.free),
        },
        "power": power,
        "uptime": seconds_to_human(boot_time),
    }


def _get_processes() -> list[dict[str, Any]]:
    """Süreç listesi."""
    procs = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "status"]):
        try:
            info = proc.info
            mem = info.get("memory_info")
            procs.append({
                "pid": info["pid"],
                "name": info["name"] or "Unknown",
                "cpu": round(info.get("cpu_percent", 0) or 0, 1),
                "ram": bytes_to_human(mem.rss) if mem else "0 B",
                "ram_bytes": mem.rss if mem else 0,
                "status": info.get("status", ""),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda p: p["cpu"], reverse=True)
    return procs[:50]


def _get_network_data() -> dict[str, Any]:
    """Ağ verileri."""
    try:
        counters = psutil.net_io_counters()
        return {
            "bytes_sent": bytes_to_human(counters.bytes_sent),
            "bytes_recv": bytes_to_human(counters.bytes_recv),
            "packets_sent": counters.packets_sent,
            "packets_recv": counters.packets_recv,
        }
    except Exception:
        return {}


def _get_disk_data() -> list[dict[str, Any]]:
    """Disk bilgileri."""
    disks = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "percent": usage.percent,
                "used": bytes_to_human(usage.used),
                "total": bytes_to_human(usage.total),
                "free": bytes_to_human(usage.free),
            })
        except (PermissionError, OSError):
            continue
    return disks
