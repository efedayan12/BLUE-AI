"""
BLUE_AI Process Manager — Süreç izleme ve yönetimi.

CPU/RAM hog tespiti, süreç önceliklendirme, zombie temizliği.
"""

import asyncio
from typing import Any

import psutil

from blue_ai.plugins.base import BasePlugin
from blue_ai.core.event_bus import Event
from blue_ai.utils.helpers import bytes_to_human, is_system_process
from blue_ai.utils.win_api import set_process_priority, set_process_affinity, empty_working_set


class ProcessManagerPlugin(BasePlugin):
    name = "process_manager"
    description = "Süreçleri izler ve yönetir"
    version = "1.0.0"

    def __init__(self, event_bus: Any, config: dict[str, Any]) -> None:
        super().__init__(event_bus, config)
        self._interval = config.get("polling", {}).get("process_check_interval", 5.0)
        self._thresholds = config.get("thresholds", {})
        self._cpu_hog_limit = self._thresholds.get("process_cpu_hog", 50)
        self._ram_hog_limit_mb = self._thresholds.get("process_ram_hog_mb", 2048)
        self._processes: list[dict[str, Any]] = []
        self._blacklist: set[str] = set()
        self._whitelist: set[str] = set(
            config.get("security", {}).get("whitelist", [])
        )

    def get_interval(self) -> float:
        return self._interval

    async def on_start(self) -> None:
        # Action event'lerine abone ol
        self.event_bus.subscribe("action.throttle_top_process", self._handle_throttle)
        self.event_bus.subscribe("action.investigate_process", self._handle_investigate)
        self.event_bus.subscribe("action.investigate_process_ram", self._handle_investigate_ram)

    async def on_stop(self) -> None:
        pass

    async def tick(self) -> None:
        procs = await asyncio.get_event_loop().run_in_executor(None, self._scan_processes)
        self._processes = procs

        # CPU hog tespiti
        top_cpu = procs[0] if procs else None
        if top_cpu and top_cpu["cpu_percent"] > self._cpu_hog_limit:
            await self.emit("metrics_update", {
                "top_process_cpu": top_cpu["cpu_percent"],
            })
            self.logger.warning(
                self.name,
                f"CPU hog tespit edildi: {top_cpu['name']} ({top_cpu['cpu_percent']:.1f}%)",
            )

        # RAM hog tespiti
        top_ram = max(procs, key=lambda p: p["memory_mb"]) if procs else None
        if top_ram and top_ram["memory_mb"] > self._ram_hog_limit_mb:
            await self.emit("metrics_update", {
                "top_process_ram_mb": top_ram["memory_mb"],
            })
            self.logger.warning(
                self.name,
                f"RAM hog tespit edildi: {top_ram['name']} ({top_ram['memory_mb']:.0f} MB)",
            )

        # Zombie süreç temizliği
        zombies = [p for p in procs if p.get("status") == "zombie"]
        if zombies:
            for z in zombies:
                self.logger.warning(self.name, f"Zombie süreç: {z['name']} (PID: {z['pid']})")

    def _scan_processes(self) -> list[dict[str, Any]]:
        """Tüm süreçleri tara ve bilgilerini topla."""
        procs = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "status", "create_time", "username"]):
            try:
                info = proc.info
                mem = info.get("memory_info")
                memory_mb = mem.rss / (1024 * 1024) if mem else 0

                procs.append({
                    "pid": info["pid"],
                    "name": info["name"] or "Unknown",
                    "cpu_percent": info.get("cpu_percent", 0) or 0,
                    "memory_mb": memory_mb,
                    "memory_human": bytes_to_human(mem.rss) if mem else "0 B",
                    "status": info.get("status", "unknown"),
                    "username": info.get("username", ""),
                    "is_system": is_system_process(info["name"] or ""),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # CPU kullanımına göre sırala
        procs.sort(key=lambda p: p["cpu_percent"], reverse=True)
        return procs

    async def _handle_throttle(self, event: Event) -> None:
        """En yüksek CPU kullanan süreci throttle et."""
        if not self._processes:
            return

        top = self._processes[0]
        if top["is_system"] or top["name"].lower() in self._whitelist:
            self.logger.info(self.name, f"Sistem süreci atlandı: {top['name']}")
            return

        success = set_process_priority(top["pid"], "below_normal")
        if success:
            self.logger.action(
                self.name,
                f"Süreç throttle edildi: {top['name']} (PID: {top['pid']}) → Below Normal",
            )
            self.logger.log_action("throttle_process", f"{top['name']}:{top['pid']}", "success")
        else:
            self.logger.warning(self.name, f"Throttle başarısız: {top['name']}")

    async def _handle_investigate(self, event: Event) -> None:
        """CPU hog sürecini araştır."""
        top_procs = self._processes[:5]
        details = "\n".join(
            f"  {p['name']:20s} CPU: {p['cpu_percent']:5.1f}%  RAM: {p['memory_human']}"
            for p in top_procs
        )
        self.logger.info(self.name, f"En yüksek CPU kullanan 5 süreç:\n{details}")

    async def _handle_investigate_ram(self, event: Event) -> None:
        """RAM hog sürecini araştır ve temizle."""
        top_ram = sorted(self._processes, key=lambda p: p["memory_mb"], reverse=True)[:5]
        for p in top_ram:
            if not p["is_system"]:
                success = empty_working_set(p["pid"])
                if success:
                    self.logger.action(
                        self.name,
                        f"Working set temizlendi: {p['name']} ({p['memory_human']})",
                    )

    # --- Public API ---

    def kill_process(self, pid: int) -> bool:
        """Süreci sonlandır."""
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            if is_system_process(name):
                self.logger.warning(self.name, f"Sistem süreci sonlandırılamaz: {name}")
                return False
            proc.terminate()
            self.logger.action(self.name, f"Süreç sonlandırıldı: {name} (PID: {pid})")
            self.logger.log_action("kill_process", f"{name}:{pid}", "success")
            return True
        except Exception as e:
            self.logger.error(self.name, f"Süreç sonlandırma hatası: {e}")
            return False

    def set_priority(self, pid: int, priority: str) -> bool:
        """Süreç önceliğini değiştir."""
        success = set_process_priority(pid, priority)
        if success:
            self.logger.action(self.name, f"Öncelik değişti: PID {pid} → {priority}")
        return success

    def get_processes(self) -> list[dict[str, Any]]:
        """Güncel süreç listesini döndür."""
        return list(self._processes)

    def get_top_cpu(self, n: int = 10) -> list[dict[str, Any]]:
        """En çok CPU kullanan N süreci döndür."""
        return self._processes[:n]

    def get_top_ram(self, n: int = 10) -> list[dict[str, Any]]:
        """En çok RAM kullanan N süreci döndür."""
        return sorted(self._processes, key=lambda p: p["memory_mb"], reverse=True)[:n]

    def get_status(self) -> dict[str, Any]:
        base = super().get_status()
        base["process_count"] = len(self._processes)
        base["top_cpu"] = self._processes[:3] if self._processes else []
        return base
