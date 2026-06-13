"""
BLUE_AI — Intent Detection (Niyet Tespiti)

Kullanicinin mesajini analiz edip hangi araci kullanacagini belirler.
Oncesi kural tabanli hizli eslestirme, eslesmezse LLM'e sorar.
"""

import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional

from blue_ai.ai.llm import get_llm


class IntentType(Enum):
    SYSTEM_STATUS = "system_status"
    PROCESS_LIST = "process_list"
    PROCESS_KILL = "process_kill"
    CLEAN = "clean"
    OPTIMIZE = "optimize"
    PROFILE_CHANGE = "profile_change"
    DISK_INFO = "disk_info"
    NETWORK_INFO = "network_info"
    BATTERY_INFO = "battery_info"
    RAM_INFO = "ram_info"
    HELP = "help"
    # Yeni AI yetenekleri
    CREATE_DOCUMENT = "create_document"
    CREATE_SPREADSHEET = "create_spreadsheet"
    CREATE_PRESENTATION = "create_presentation"
    FILE_OPERATION = "file_operation"
    OPEN_APP = "open_app"
    WEB_SEARCH = "web_search"
    GENERAL_QUESTION = "general_question"
    UNKNOWN = "unknown"


@dataclass
class Intent:
    type: IntentType
    confidence: float
    params: dict
    raw_message: str


# Kural tabanli hizli eslestirme
_KEYWORD_MAP = {
    IntentType.SYSTEM_STATUS: [
        r"\b(durum|status|sistem|nasil|ne\s*durumda)\b",
    ],
    IntentType.PROCESS_LIST: [
        r"\b(surec|process|calisan|top\s*process|gorev)\b",
    ],
    IntentType.PROCESS_KILL: [
        r"\b(kapat|sonlandir|kill|oldur|durdur)\b.*\b(surec|process|uygulama)\b",
        r"\b(surec|process).*\b(kapat|sonlandir|kill)\b",
    ],
    IntentType.CLEAN: [
        r"\b(temizle|temizlik|clean|sil|cache|temp)\b",
    ],
    IntentType.OPTIMIZE: [
        r"\b(optimize|optimizasyon|hizlandir|performans)\b",
    ],
    IntentType.PROFILE_CHANGE: [
        r"\b(oyun|gaming|game)\s*(mod|profil)?\b",
        r"\b(is|work|calisma)\s*(mod|profil)?\b",
        r"\b(tasarruf|power.?saver|enerji)\s*(mod|profil)?\b",
        r"\b(dengeli|balanced|normal)\s*(mod|profil)?\b",
    ],
    IntentType.DISK_INFO: [
        r"\b(disk|alan|depolama|storage|hdd|ssd)\b",
    ],
    IntentType.NETWORK_INFO: [
        r"\b(ag|net|internet|baglanti|wifi|network)\b",
    ],
    IntentType.BATTERY_INFO: [
        r"\b(pil|batarya|sarj|battery|enerji)\b",
    ],
    IntentType.RAM_INFO: [
        r"\b(ram|bellek|hafiza|memory)\b",
    ],
    IntentType.HELP: [
        r"\b(yardim|help|komut|ne\s*yapabilirsin|menu)\b",
    ],
    # AI yetenekleri
    IntentType.CREATE_DOCUMENT: [
        r"\b(word|belge|dokuman|document|yazi|makale|rapor|mektup)\b.*\b(olustur|hazirla|yaz|yap)\b",
        r"\b(olustur|hazirla|yaz|yap)\b.*\b(word|belge|dokuman|document|yazi|makale|rapor|mektup)\b",
    ],
    IntentType.CREATE_SPREADSHEET: [
        r"\b(excel|tablo|spreadsheet|hesap)\b.*\b(olustur|hazirla|yap)\b",
        r"\b(olustur|hazirla|yap)\b.*\b(excel|tablo|spreadsheet)\b",
    ],
    IntentType.CREATE_PRESENTATION: [
        r"\b(sunum|powerpoint|pptx|slayt|presentation)\b.*\b(olustur|hazirla|yap)\b",
        r"\b(olustur|hazirla|yap)\b.*\b(sunum|powerpoint|slayt)\b",
    ],
    IntentType.FILE_OPERATION: [
        r"\b(dosya|klasor|dizin|folder)\b.*\b(bul|ara|tasi|kopyala|sil|yeniden\s*adlandir|duzenle|listele)\b",
        r"\b(bul|ara|tasi|kopyala)\b.*\b(dosya|klasor)\b",
    ],
    IntentType.OPEN_APP: [
        r"\b(ac|baslat|calistir|open|launch)\b.*\b(chrome|firefox|word|excel|notepad|hesap|tarayici|browser)\b",
        r"\b(chrome|firefox|word|excel|notepad)\b.*\b(ac|baslat)\b",
    ],
    IntentType.WEB_SEARCH: [
        r"\b(ara|arastir|search|bul|sor)\b.*\b(internette|webde|google|online)\b",
        r"\b(internette|webde)\b.*\b(ara|arastir|bul)\b",
    ],
}


def detect_intent(message: str) -> Intent:
    """Mesajdan niyet tespit et."""
    msg = message.lower().strip()

    # 1. Kural tabanli hizli eslestirme
    for intent_type, patterns in _KEYWORD_MAP.items():
        for pattern in patterns:
            if re.search(pattern, msg, re.IGNORECASE):
                params = _extract_params(intent_type, msg)
                return Intent(
                    type=intent_type,
                    confidence=0.9,
                    params=params,
                    raw_message=message,
                )

    # 2. Eslesmezse LLM ile analiz (fallback)
    return _llm_detect_intent(message)


def _extract_params(intent_type: IntentType, msg: str) -> dict:
    """Intent'e ozel parametreleri cikar."""
    params = {}

    if intent_type == IntentType.PROFILE_CHANGE:
        if any(w in msg for w in ["oyun", "gaming", "game"]):
            params["profile"] = "gaming"
        elif any(w in msg for w in ["is", "work", "calisma"]):
            params["profile"] = "work"
        elif any(w in msg for w in ["tasarruf", "power_saver", "enerji"]):
            params["profile"] = "power_saver"
        else:
            params["profile"] = "balanced"

    if intent_type == IntentType.OPEN_APP:
        app_map = {
            "chrome": "chrome", "firefox": "firefox",
            "word": "winword", "excel": "excel",
            "notepad": "notepad", "hesap": "calc",
            "tarayici": "chrome", "browser": "chrome",
        }
        for key, val in app_map.items():
            if key in msg:
                params["app"] = val
                break

    if intent_type in (IntentType.CREATE_DOCUMENT, IntentType.CREATE_SPREADSHEET,
                       IntentType.CREATE_PRESENTATION, IntentType.GENERAL_QUESTION):
        params["topic"] = msg  # LLM tam mesajla calisir

    return params


def _llm_detect_intent(message: str) -> Intent:
    """LLM ile niyet tespiti (fallback)."""
    llm = get_llm()
    if not llm.is_available():
        return Intent(IntentType.GENERAL_QUESTION, 0.5, {"topic": message}, message)

    system = """You are an intent classifier. Classify the user message into ONE of these categories:
system_status, process_list, clean, optimize, disk_info, network_info, ram_info,
create_document, create_spreadsheet, create_presentation, file_operation, open_app, general_question.
Reply with ONLY the category name, nothing else."""

    result = llm.generate(message, system=system, temperature=0.1)
    result = result.strip().lower().replace(" ", "_")

    try:
        intent_type = IntentType(result)
    except ValueError:
        intent_type = IntentType.GENERAL_QUESTION

    return Intent(
        type=intent_type,
        confidence=0.7,
        params={"topic": message},
        raw_message=message,
    )
