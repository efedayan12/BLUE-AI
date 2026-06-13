"""
BLUE_AI Logger — SQLite tabanlı yapılandırılmış loglama sistemi.

Tüm sistem olaylarını, aksiyonları ve metrikleri SQLite veritabanına kaydeder.
Aynı zamanda terminale renkli çıktı verir.
"""

import sqlite3
import threading
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from rich.console import Console

from blue_ai.core.config import get

console = Console()


class LogLevel(Enum):
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4
    ACTION = 5  # Otomatik aksiyon logları


_LEVEL_STYLES = {
    LogLevel.DEBUG: "dim",
    LogLevel.INFO: "cyan",
    LogLevel.WARNING: "yellow bold",
    LogLevel.ERROR: "red bold",
    LogLevel.CRITICAL: "red bold reverse",
    LogLevel.ACTION: "green bold",
}

_LEVEL_ICONS = {
    LogLevel.DEBUG: "[DBG]",
    LogLevel.INFO: "[INF]",
    LogLevel.WARNING: "[WRN]",
    LogLevel.ERROR: "[ERR]",
    LogLevel.CRITICAL: "[CRT]",
    LogLevel.ACTION: "[ACT]",
}


class Logger:
    """Thread-safe SQLite tabanlı logger."""

    _instance: "Logger | None" = None
    _lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> "Logger":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: Path | None = None) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        data_dir = Path(get("general.data_dir", "data"))
        if not data_dir.is_absolute():
            data_dir = Path(__file__).parent.parent.parent / data_dir
        data_dir.mkdir(parents=True, exist_ok=True)

        self._db_path = db_path or (data_dir / "blue_ai.db")
        self._local = threading.local()
        self._min_level = LogLevel[get("general.log_level", "INFO").upper()]
        self._console_enabled = True

        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._db_path))
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                source TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT
            );
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                source TEXT
            );
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action_type TEXT NOT NULL,
                target TEXT,
                result TEXT,
                details TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp);
            CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level);
            CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name);
            CREATE INDEX IF NOT EXISTS idx_actions_type ON actions(action_type);
        """)
        conn.commit()

    def _log(self, level: LogLevel, source: str, message: str, details: str | None = None) -> None:
        if level.value < self._min_level.value:
            return

        ts = datetime.now(timezone.utc).isoformat()

        # SQLite'a yaz
        try:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO logs (timestamp, level, source, message, details) VALUES (?, ?, ?, ?, ?)",
                (ts, level.name, source, message, details),
            )
            conn.commit()
        except Exception:
            pass  # Loglama hatası sessizce geçilir

        # Terminale yaz
        if self._console_enabled:
            icon = _LEVEL_ICONS.get(level, "")
            style = _LEVEL_STYLES.get(level, "")
            ts_short = datetime.now().strftime("%H:%M:%S")
            console.print(
                f"[dim]{ts_short}[/dim] {icon} [{style}][{level.name:8s}][/{style}] "
                f"[bold]{source}[/bold] -> {message}"
            )

    def debug(self, source: str, message: str, details: str | None = None) -> None:
        self._log(LogLevel.DEBUG, source, message, details)

    def info(self, source: str, message: str, details: str | None = None) -> None:
        self._log(LogLevel.INFO, source, message, details)

    def warning(self, source: str, message: str, details: str | None = None) -> None:
        self._log(LogLevel.WARNING, source, message, details)

    def error(self, source: str, message: str, details: str | None = None) -> None:
        self._log(LogLevel.ERROR, source, message, details)

    def critical(self, source: str, message: str, details: str | None = None) -> None:
        self._log(LogLevel.CRITICAL, source, message, details)

    def action(self, source: str, message: str, details: str | None = None) -> None:
        self._log(LogLevel.ACTION, source, message, details)

    def log_metric(self, metric_name: str, value: float, source: str = "") -> None:
        """Sayısal metrik kaydet."""
        ts = datetime.now(timezone.utc).isoformat()
        try:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO metrics (timestamp, metric_name, metric_value, source) VALUES (?, ?, ?, ?)",
                (ts, metric_name, value, source),
            )
            conn.commit()
        except Exception:
            pass

    def log_action(self, action_type: str, target: str = "", result: str = "", details: str = "") -> None:
        """Otomatik aksiyon kaydı."""
        ts = datetime.now(timezone.utc).isoformat()
        try:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO actions (timestamp, action_type, target, result, details) VALUES (?, ?, ?, ?, ?)",
                (ts, action_type, target, result, details),
            )
            conn.commit()
        except Exception:
            pass

    def get_recent_logs(self, limit: int = 50, level: str | None = None) -> list[dict[str, Any]]:
        """Son logları getir."""
        conn = self._get_conn()
        if level:
            rows = conn.execute(
                "SELECT timestamp, level, source, message, details FROM logs WHERE level = ? ORDER BY id DESC LIMIT ?",
                (level.upper(), limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT timestamp, level, source, message, details FROM logs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"timestamp": r[0], "level": r[1], "source": r[2], "message": r[3], "details": r[4]}
            for r in rows
        ]

    def get_metrics(self, metric_name: str, limit: int = 100) -> list[dict[str, Any]]:
        """Belirli metriğin son N kaydını getir."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT timestamp, metric_value FROM metrics WHERE metric_name = ? ORDER BY id DESC LIMIT ?",
            (metric_name, limit),
        ).fetchall()
        return [{"timestamp": r[0], "value": r[1]} for r in rows]

    def cleanup_old(self, days: int = 30) -> int:
        """Eski logları sil."""
        conn = self._get_conn()
        cutoff = datetime.now(timezone.utc).isoformat()
        # Simple approach: delete by rowcount based on time
        cursor = conn.execute(
            "DELETE FROM logs WHERE timestamp < datetime('now', ?)",
            (f"-{days} days",),
        )
        conn.execute(
            "DELETE FROM metrics WHERE timestamp < datetime('now', ?)",
            (f"-{days} days",),
        )
        conn.commit()
        return cursor.rowcount


def get_logger() -> Logger:
    """Tekil Logger örneği al."""
    return Logger()
