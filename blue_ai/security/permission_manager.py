"""
BLUE_AI — Permission Manager

LLM aksiyonları için izin seviyeleri ve onay mekanizması.

Seviyeler:
  1 (AUTO)      — Bilgi sorgulama: onay gerekmez
  2 (NOTIFY)    — Uygulama açma, belge oluşturma: bildirim
  3 (CONFIRM)   — Dosya silme, süreç sonlandırma: "Emin misiniz?" sorusu
  4 (FORBIDDEN) — Sistem dosyaları, registry: her zaman engellenir
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from blue_ai.brain.tool_registry import PermissionLevel, ToolResult


# Yasaklı yollar — hiçbir koşulda erişilemez
FORBIDDEN_PATHS = [
    "C:\\Windows\\System32",
    "C:\\Windows\\SysWOW64",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
]

# Yasaklı komutlar
FORBIDDEN_COMMANDS = [
    "format", "diskpart", "reg delete", "reg add",
    "bcdedit", "sc delete", "net user", "shutdown /s",
]


@dataclass
class PermissionRequest:
    """İzin talebi."""
    tool_name: str
    arguments: dict[str, Any]
    permission_level: PermissionLevel
    confirmation_message: str = ""
    approved: bool = False
    denied: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "permission_level": self.permission_level.name,
            "confirmation_message": self.confirmation_message,
            "approved": self.approved,
            "denied": self.denied,
        }


class PermissionManager:
    """İzin yöneticisi — tool çalıştırma izinlerini kontrol eder."""

    def __init__(self) -> None:
        self._pending_requests: list[PermissionRequest] = []
        self._auto_approve_level = PermissionLevel.NOTIFY  # Bu seviyeye kadar otomatik
        self._audit_log: list[dict] = []

    def check_permission(
        self,
        tool_name: str,
        permission_level: PermissionLevel,
        arguments: dict[str, Any],
        confirmation_message: str = "",
    ) -> PermissionRequest:
        """İzin kontrolü yap.

        Returns:
            PermissionRequest — approved=True ise çalıştır, değilse kullanıcıya sor.
        """
        request = PermissionRequest(
            tool_name=tool_name,
            arguments=arguments,
            permission_level=permission_level,
            confirmation_message=confirmation_message,
        )

        # Seviye 4: Her zaman engelle
        if permission_level == PermissionLevel.FORBIDDEN:
            request.denied = True
            self._log_action(request, "DENIED (forbidden)")
            return request

        # Yasaklı yol kontrolü
        if self._check_forbidden_paths(arguments):
            request.denied = True
            request.confirmation_message = "Bu işlem güvenlik nedeniyle engellenmiştir."
            self._log_action(request, "DENIED (forbidden path)")
            return request

        # Seviye 1 (AUTO): Otomatik onayla
        if permission_level == PermissionLevel.AUTO:
            request.approved = True
            self._log_action(request, "AUTO APPROVED")
            return request

        # Seviye 2 (NOTIFY): Bilgilendir ve onayla
        if permission_level == PermissionLevel.NOTIFY:
            request.approved = True
            self._log_action(request, "NOTIFY APPROVED")
            return request

        # Seviye 3 (CONFIRM): Kullanıcı onayı gerekli
        if permission_level == PermissionLevel.CONFIRM:
            if not confirmation_message:
                request.confirmation_message = (
                    f"'{tool_name}' işlemi çalıştırılacak. Emin misiniz?"
                )
            self._pending_requests.append(request)
            self._log_action(request, "PENDING CONFIRMATION")
            return request

        return request

    def approve_pending(self, tool_name: str) -> bool:
        """Bekleyen isteği onayla."""
        for req in self._pending_requests:
            if req.tool_name == tool_name and not req.approved and not req.denied:
                req.approved = True
                self._log_action(req, "USER APPROVED")
                self._pending_requests.remove(req)
                return True
        return False

    def deny_pending(self, tool_name: str) -> bool:
        """Bekleyen isteği reddet."""
        for req in self._pending_requests:
            if req.tool_name == tool_name and not req.approved and not req.denied:
                req.denied = True
                self._log_action(req, "USER DENIED")
                self._pending_requests.remove(req)
                return True
        return False

    def get_pending_requests(self) -> list[PermissionRequest]:
        """Bekleyen onay isteklerini döndür."""
        return list(self._pending_requests)

    def _check_forbidden_paths(self, arguments: dict[str, Any]) -> bool:
        """Yasaklı yolları kontrol et."""
        for key, value in arguments.items():
            if isinstance(value, str):
                for forbidden in FORBIDDEN_PATHS:
                    if value.lower().startswith(forbidden.lower()):
                        return True
        return False

    def _log_action(self, request: PermissionRequest, status: str) -> None:
        """Denetim kaydına ekle."""
        self._audit_log.append({
            "timestamp": time.time(),
            "tool_name": request.tool_name,
            "arguments": request.arguments,
            "permission_level": request.permission_level.name,
            "status": status,
        })
        # Max 1000 kayıt tut
        if len(self._audit_log) > 1000:
            self._audit_log = self._audit_log[-500:]

    def get_audit_log(self, limit: int = 50) -> list[dict]:
        """Denetim kaydını döndür."""
        return self._audit_log[-limit:]


# ─── Singleton ──────────────────────────────────────
_permission_manager: Optional[PermissionManager] = None


def get_permission_manager() -> PermissionManager:
    """Singleton permission manager döndür."""
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager()
    return _permission_manager
