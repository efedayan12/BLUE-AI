"""
BLUE_AI — Context Manager

LLM'e gönderilecek bağlamı oluşturur ve yönetir:
- System Prompt (BLUE AI kimliği ve kuralları)
- Conversation History (konuşma geçmişi)
- System Context (anlık sistem durumu)
- Tool Schemas (çağrılabilir araçlar)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from collections import deque

import psutil

from blue_ai.brain.tool_registry import get_registry
from blue_ai.memory.manager import get_memory, get_session_memory

# ─── System Prompt — Kısa ve öz (token tasarrufu) ───
# Küçük model (gemma3:1b) için sıkı kurallar — hallucination azaltır
SYSTEM_PROMPT_TR = """Sen BLUE AI — Windows bilgisayar asistanısın.
KURALLAR:
- Türkçe cevap ver, kısa ve net ol.
- Emin olmadığın şeyleri UYDURMA. Bilmiyorsan "Bilmiyorum" de.
- Sistem komutu için: {{"tool_call": {{"name": "ARAÇ_ADI", "arguments": {{}}}}}}
- Tehlikeli işlemlerde onay iste.
- Cevabı yarıda bırakma.

Sistem: {system_context}
Araçlar: {tool_descriptions}"""

SYSTEM_PROMPT_EN = """You are BLUE AI — a Windows PC assistant.
RULES:
- Answer in Turkish, be concise and accurate.
- Do NOT make up information. Say "I don't know" if unsure.
- For system commands use: {{"tool_call": {{"name": "TOOL_NAME", "arguments": {{}}}}}}
- Ask confirmation for dangerous operations.
- Never cut answers short.

System: {system_context}
Tools: {tool_descriptions}"""


@dataclass
class Message:
    """Konuşma mesajı."""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: float = field(default_factory=time.time)
    tool_name: str = ""
    tool_result: str = ""

    def to_dict(self) -> dict:
        d = {"role": self.role, "content": self.content}
        if self.tool_name:
            d["tool_name"] = self.tool_name
        return d


class ContextManager:
    """LLM bağlam yöneticisi."""

    def __init__(self, max_history: int = 4, language: str = "tr"):
        self._history: deque[Message] = deque(maxlen=max_history)
        self._language = language
        self._max_history = max_history

        # Cache — her mesajda sıfırdan rebuild edilmemesi için
        self._prompt_cache: str = ""
        self._prompt_cache_ts: float = 0.0
        self._sysctx_cache: str = ""
        self._sysctx_cache_ts: float = 0.0
        _PROMPT_TTL = 60.0   # sistem prompt 60s geçerli
        _SYSCTX_TTL = 5.0    # sistem bilgisi 5s geçerli
        self._PROMPT_TTL = _PROMPT_TTL
        self._SYSCTX_TTL = _SYSCTX_TTL

    @property
    def language(self) -> str:
        return self._language

    @language.setter
    def language(self, lang: str) -> None:
        self._language = lang

    def add_message(self, role: str, content: str, **kwargs) -> None:
        """Konuşma geçmişine mesaj ekle."""
        self._history.append(Message(role=role, content=content, **kwargs))

    def add_user_message(self, content: str) -> None:
        """Kullanıcı mesajı ekle."""
        self.add_message("user", content)

    def add_assistant_message(self, content: str) -> None:
        """Asistan yanıtı ekle."""
        self.add_message("assistant", content)

    def add_tool_result(self, tool_name: str, result: str) -> None:
        """Tool sonucunu ekle."""
        self.add_message(
            "system",
            f"[Tool Sonucu: {tool_name}]\n{result}",
            tool_name=tool_name,
            tool_result=result,
        )

    def get_system_context(self) -> str:
        """Anlık sistem durumunu kısa metin olarak döndür — 5s cache'li."""
        now = time.time()
        if self._sysctx_cache and now - self._sysctx_cache_ts < self._SYSCTX_TTL:
            return self._sysctx_cache
        try:
            cpu = psutil.cpu_percent(interval=0)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage("C:\\")
            # Kısa format — daha az token
            self._sysctx_cache = (
                f"CPU:{cpu:.0f}% RAM:{ram.percent:.0f}%"
                f"({ram.used//(1024**3):.0f}/{ram.total//(1024**3):.0f}GB)"
                f" Disk:{disk.percent:.0f}% Boş:{disk.free//(1024**3):.0f}GB"
            )
            self._sysctx_cache_ts = now
        except Exception:
            self._sysctx_cache = "Windows"
        return self._sysctx_cache

    def build_system_prompt(self) -> str:
        """Tam system prompt oluştur — 60s cache'li (her mesajda rebuild yok)."""
        now = time.time()
        if self._prompt_cache and now - self._prompt_cache_ts < self._PROMPT_TTL:
            # Sadece sistem verisini değiştir (araç listesi aynı kalır)
            sys_ctx = self.get_system_context()
            return self._prompt_cache.split("Sistem:")[0] + f"Sistem: {sys_ctx}\n\n" + \
                   "Araçlar:\n" + self._prompt_cache.split("Araçlar:\n", 1)[-1] \
                   if "Sistem:" in self._prompt_cache and "Araçlar:" in self._prompt_cache \
                   else self._prompt_cache

        registry = get_registry()
        tool_desc = registry.get_tool_names_compact()  # sadece isimler — daha az token
        sys_ctx = self.get_system_context()

        # Kalıcı hafıza bağlamını ekle
        memory_ctx = get_memory().generate_context_string()
        if memory_ctx and "Henuz" not in memory_ctx:
            sys_ctx = f"{sys_ctx} | {memory_ctx}"

        # Oturum belleği bağlamını ekle (varsa)
        session_ctx = get_session_memory().generate_context()
        if session_ctx:
            sys_ctx = f"{sys_ctx}\n{session_ctx}"

        template = SYSTEM_PROMPT_TR if self._language == "tr" else SYSTEM_PROMPT_EN
        prompt = template.format(
            system_context=sys_ctx,
            tool_descriptions=tool_desc,
        )
        self._prompt_cache = prompt
        self._prompt_cache_ts = now
        return prompt

    def invalidate_cache(self) -> None:
        """Cache'i zorla temizle (dil değiştiğinde çağır)."""
        self._prompt_cache = ""
        self._prompt_cache_ts = 0.0

    def build_messages(self, user_message: str | None = None) -> list[dict]:
        """LLM'e gönderilecek mesaj listesini oluştur (Ollama chat formatı)."""
        messages = [
            {"role": "system", "content": self.build_system_prompt()}
        ]

        # Konuşma geçmişini ekle
        for msg in self._history:
            messages.append(msg.to_dict())

        # Yeni kullanıcı mesajını ekle (henüz history'e eklenmemişse)
        if user_message:
            messages.append({"role": "user", "content": user_message})

        return messages

    def get_history(self) -> list[dict]:
        """Konuşma geçmişini döndür."""
        return [msg.to_dict() for msg in self._history]

    def clear_history(self) -> None:
        """Konuşma geçmişini temizle."""
        self._history.clear()

    def detect_language(self, text: str) -> str:
        """Basit dil algılama — Türkçe karakterler varsa TR."""
        turkish_chars = set("çğıöşüÇĞİÖŞÜ")
        turkish_words = {"merhaba", "nasıl", "nedir", "yap", "aç", "kapat",
                         "göster", "bul", "sil", "temizle", "bilgisayar",
                         "sistem", "dosya", "klasör", "ne", "nasıl", "neden"}
        text_lower = text.lower()
        if any(c in text for c in turkish_chars):
            return "tr"
        if any(w in text_lower.split() for w in turkish_words):
            return "tr"
        return "en"

    def auto_detect_and_set_language(self, text: str) -> str:
        """Dili otomatik algıla ve ayarla."""
        lang = self.detect_language(text)
        if lang != self._language:
            self._language = lang
            self.invalidate_cache()  # Dil değişince prompt'u yenile
        return lang


# ─── Singleton ──────────────────────────────────────
_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """Singleton context manager döndür."""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
