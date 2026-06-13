"""
BLUE_AI — Tool Base Class & Registry

Tüm tool'lar için abstract base class ve merkezi kayıt sistemi.
LLM'nin function calling ile çağırabileceği araçları tanımlar.
"""

from __future__ import annotations

import json
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional


class PermissionLevel(IntEnum):
    """Aksiyon izin seviyeleri."""
    AUTO = 1        # Otomatik — bilgi sorgulama (sistem durumu, süreçler)
    NOTIFY = 2      # Bildirimli — uygulama açma, belge oluşturma
    CONFIRM = 3     # Onaylı — dosya silme, süreç sonlandırma
    FORBIDDEN = 4   # Yasaklı — sistem dosyaları silme, registry


@dataclass
class ToolResult:
    """Tool çalıştırma sonucu."""
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    error: str = ""

    def to_llm_context(self) -> str:
        """LLM'e geri gönderilecek bağlam metni."""
        if self.success:
            parts = []
            if self.message:
                parts.append(self.message)
            if self.data:
                parts.append(json.dumps(self.data, ensure_ascii=False, indent=2))
            return "\n".join(parts) if parts else "İşlem başarılı."
        return f"Hata: {self.error}" if self.error else "İşlem başarısız."


@dataclass
class ToolParameter:
    """Tool parametre tanımı."""
    name: str
    type: str  # "string", "integer", "number", "boolean", "array"
    description: str
    required: bool = True
    enum: list[str] | None = None
    default: Any = None


class BaseTool(ABC):
    """Tüm BLUE_AI tool'ları için abstract base class."""

    name: str = ""
    description: str = ""
    description_en: str = ""
    permission_level: PermissionLevel = PermissionLevel.AUTO
    parameters: list[ToolParameter] = []

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Tool'u çalıştır ve sonuç döndür."""
        ...

    def get_confirmation_message(self, **kwargs) -> str:
        """Onay gerektiren işlemler için kullanıcıya gösterilecek mesaj."""
        return f"'{self.name}' işlemi çalıştırılacak. Emin misiniz?"

    def to_schema(self) -> dict:
        """LLM'e gönderilecek JSON schema (OpenAI function calling formatı)."""
        properties = {}
        required = []

        for param in self.parameters:
            prop: dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        schema = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                },
            },
        }
        if required:
            schema["function"]["parameters"]["required"] = required

        return schema


class ToolRegistry:
    """Merkezi tool kayıt sistemi.

    Tüm tool'lar burada kayıt edilir.
    LLM bu registry'den tool listesini alır.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Tool kaydet."""
        if not tool.name:
            raise ValueError(f"Tool adı boş olamaz: {tool.__class__.__name__}")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Tool kaydını sil."""
        self._tools.pop(name, None)

    def get(self, name: str) -> BaseTool | None:
        """İsme göre tool getir."""
        return self._tools.get(name)

    def get_all(self) -> dict[str, BaseTool]:
        """Tüm tool'ları getir."""
        return dict(self._tools)

    def get_schemas(self) -> list[dict]:
        """Tüm tool'ların JSON schema'larını döndür (LLM'e gönderilecek)."""
        return [tool.to_schema() for tool in self._tools.values()]

    def get_tool_descriptions(self) -> str:
        """Tüm tool'ların kısa açıklamalarını döndür — tek satır/araç (token tasarrufu)."""
        lines = []
        confirm_mark = {
            PermissionLevel.AUTO: "",
            PermissionLevel.NOTIFY: "",
            PermissionLevel.CONFIRM: " [CONFIRM]",
            PermissionLevel.FORBIDDEN: " [FORBIDDEN]",
        }
        for tool in self._tools.values():
            params = ", ".join(
                f"{p.name}" + ("?" if not p.required else "")
                for p in tool.parameters
            )
            mark = confirm_mark.get(tool.permission_level, "")
            param_str = f"({params})" if params else ""
            lines.append(f"{tool.name}{param_str}: {tool.description}{mark}")
        return "\n".join(lines)

    def get_tool_names_compact(self) -> str:
        """Sadece tool isimleri — minimum token kullanımı (~60% daha az).

        LLM sadece hangi tool'ların var olduğunu bilmesi yeterli,
        parametreler zaten fast-path veya context'te yönetiliyor.
        """
        names = list(self._tools.keys())
        # 10'ar grupla, virgülle ayır — tek satır format
        chunk = 10
        groups = [", ".join(names[i:i+chunk]) for i in range(0, len(names), chunk)]
        return " | ".join(groups)

    def execute_tool(self, name: str, **kwargs) -> ToolResult:
        """Tool'u isimle çalıştır."""
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool bulunamadı: '{name}'. Mevcut tool'lar: {list(self._tools.keys())}"
            )
        try:
            return tool.execute(**kwargs)
        except Exception as e:
            return ToolResult(success=False, error=f"{name} hatası: {str(e)}")

    @property
    def count(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        return f"ToolRegistry({self.count} tools: {list(self._tools.keys())})"


# ─── Singleton ─────────────────────────────────────
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Singleton registry döndür."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
