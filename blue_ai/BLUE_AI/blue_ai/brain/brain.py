"""
BLUE_AI — Brain (Merkezi Beyin)

LLM merkezli karar verici orchestrator.
Tüm girdiyi alır, bağlam oluşturur, Llama'ya sorar,
tool çağrısı varsa çalıştırır, sonucu kullanıcıya sunar.

Akış:
  1. Kullanıcı mesajı al
  2. Bağlam hazırla (system prompt + history + system status + tools)
  3. LLM'e gönder
  4. Yanıtı parse et:
     a. Tool çağrısı varsa → güvenlik kontrolü → çalıştır → sonucu LLM'e geri gönder
     b. Düz metin yanıtı → kullanıcıya göster
  5. Multi-step: LLM tekrar tool çağrısı yaparsa döngüye devam et (max 5 adım)
"""

from __future__ import annotations

import json
import re
import asyncio
from typing import Any, Optional
from dataclasses import dataclass, field

from blue_ai.ai.llm import get_llm
from blue_ai.brain.tool_registry import get_registry, ToolResult, PermissionLevel
from blue_ai.brain.context_manager import get_context_manager
from blue_ai.security.permission_manager import get_permission_manager


MAX_TOOL_STEPS = 5  # Maksimum tool çağrı zinciri


@dataclass
class BrainResponse:
    """Beyin yanıtı."""
    message: str
    response_type: str = "info"         # info, success, warning, error, confirm
    tool_calls: list[dict] = field(default_factory=list)
    pending_confirmation: dict | None = None  # Onay bekleyen işlem
    raw_llm_response: str = ""

    def to_dict(self) -> dict:
        d = {
            "response": self.message,
            "type": self.response_type,
        }
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.pending_confirmation:
            d["pending_confirmation"] = self.pending_confirmation
        return d


class Brain:
    """BLUE AI Merkezi Beyin — LLM orchestrator."""

    # ML model class-level cache — bir kez yüklenir, tüm instance'lar paylaşır
    _ml_model_cache: "dict | None" = None
    _ml_model_ready: bool = False
    _ml_model_loading: bool = False

    def __init__(self) -> None:
        self._context = get_context_manager()
        self._registry = get_registry()
        self._permission = get_permission_manager()
        self._initialized = False

    def initialize(self) -> None:
        """Tool'ları kaydet ve sistemi başlat."""
        if self._initialized:
            return

        from blue_ai.tools.system_tools import register_all_tools
        register_all_tools()
        self._initialized = True

    def _load_ml_model_bg(self) -> None:
        """ML modeli arka plan thread'inde yükle — UI'ı bloklamaz."""
        if Brain._ml_model_ready or Brain._ml_model_loading:
            return
        import threading
        threading.Thread(target=self._load_ml_model_blocking,
                         daemon=True, name="ml_load").start()

    def _load_ml_model_blocking(self) -> None:
        """ML modeli yükle (bloklayan, thread'de çağrılmalı)."""
        if Brain._ml_model_ready or Brain._ml_model_loading:
            return
        Brain._ml_model_loading = True
        try:
            import sys
            from pathlib import Path
            import joblib

            # PyInstaller + kaynak kod için path adayları
            candidates = []
            if getattr(sys, "frozen", False):
                exe_dir = Path(sys.executable).parent
                candidates.append(exe_dir / "_internal" / "data" / "models" / "brain_intent_model.joblib")
                candidates.append(exe_dir / "data" / "models" / "brain_intent_model.joblib")
            candidates.append(Path(__file__).resolve().parent.parent.parent / "data" / "models" / "brain_intent_model.joblib")
            candidates.append(Path("C:/BLUE_AI/data/models/brain_intent_model.joblib"))

            model_path = None
            for c in candidates:
                if c.exists():
                    model_path = c
                    break

            if not model_path:
                print("[Brain] ML model dosyasi bulunamadi.")
                return

            Brain._ml_model_cache = joblib.load(str(model_path))
            Brain._ml_model_ready = True
            print(f"[Brain] ML model hazir: {model_path.name}")
        except Exception as e:
            print(f"[Brain] ML model yuklenemedi: {e}")
        finally:
            Brain._ml_model_loading = False

    # Tool komutları için LLM gerektirmeyen intent'ler
    # Bu set'teki intent'ler direkt ML → Tool yolundan gider (hızlı, <200ms)
    _FAST_PATH_INTENTS = frozenset({
        "system_status", "ram_info", "cpu_info", "disk_info", "network_info",
        "battery_info", "process_list", "process_kill", "clean_temp",
        "change_volume", "take_screenshot", "show_time", "lock_screen",
        "shutdown_pc", "restart_pc", "set_reminder", "open_app", "close_app",
        "file_list", "file_open", "file_copy", "file_move", "file_delete",
        "create_folder", "smart_web_search", "change_profile", "help",
        # Ek intent'ler — LLM bypass
        "gpu_info", "temp_info", "wifi_info", "bluetooth_info",
        "sound_info", "display_info", "usb_info",
        "optimize_ram", "optimize_cpu", "clean_browser_cache",
        "get_ip", "ping", "speedtest",
        "switch_stt_engine",
        "open_app",
        "get_weather",
    })

    # Keyword → tool hızlı eşleştirme (ML model olmasa da çalışır)
    _KEYWORD_MAP: dict[str, str] = {
        "durum": "system_status", "status": "system_status", "sistem": "system_status",
        "ram": "ram_info", "bellek": "ram_info", "memory": "ram_info",
        "cpu": "cpu_info", "işlemci": "cpu_info", "islemci": "cpu_info",
        "disk": "disk_info", "depolama": "disk_info",
        "ağ": "network_info", "ag": "network_info", "network": "network_info", "internet": "network_info",
        "pil": "battery_info", "batarya": "battery_info", "battery": "battery_info",
        "temizle": "clean_temp", "clean": "clean_temp", "temp": "clean_temp",
        "süreç": "process_list", "surec": "process_list", "process": "process_list",
        "yardım": "help", "yardim": "help", "help": "help",
        "ekran görüntüsü": "take_screenshot", "screenshot": "take_screenshot",
        "saat": "show_time", "zaman": "show_time", "time": "show_time",
        "aç": "open_app", "başlat": "open_app", "çalıştır": "open_app", "ac": "open_app",
        "ses": "change_volume", "volume": "change_volume", "sesi": "change_volume",
        "ses seviyesi": "change_volume", "sesi ayarla": "change_volume",
        "vosk": "switch_stt_engine", "whisper": "switch_stt_engine",
        "ses tanıma": "switch_stt_engine", "ses tanima": "switch_stt_engine",
        "stt": "switch_stt_engine",
        "hava": "get_weather", "hava durumu": "get_weather", "weather": "get_weather",
        "sıcaklık": "get_weather", "sicaklik": "get_weather", "yağmur": "get_weather",
        "kar": "get_weather", "güneş": "get_weather", "bulut": "get_weather",
    }

    # Selamlama → anında cevap (LLM bypass)
    _GREETINGS: dict[str, str] = {
        "merhaba": "Merhaba! 👋 Nasıl yardımcı olabilirim?",
        "selam": "Selam! Ne yapmamı istersin?",
        "naber": "İyiyim, teşekkürler! Sen nasılsın? Sana nasıl yardımcı olabilirim?",
        "nasilsin": "Teşekkürler, iyiyim! Sana nasıl yardımcı olabilirim?",
        "nasılsın": "Teşekkürler, iyiyim! Sana nasıl yardımcı olabilirim?",
        "hello": "Hello! How can I help you?",
        "hi": "Hi there! What can I do for you?",
        "hey": "Hey! How can I assist you?",
        "günaydın": "Günaydın! ☀️ Nasıl yardımcı olabilirim?",
        "iyi aksamlar": "İyi akşamlar! 🌙 Nasıl yardımcı olabilirim?",
        "iyi geceler": "İyi geceler! 🌙",
        "teşekkür": "Rica ederim! Başka bir konuda yardımcı olabilir miyim?",
        "tesekkur": "Rica ederim! Başka bir konuda yardımcı olabilir miyim?",
        "thanks": "You're welcome! Anything else?",
        "thank you": "You're welcome! Anything else?",
    }

    def process(self, user_message: str) -> BrainResponse:
        """Kullanıcı mesajını işle ve yanıt döndür."""
        self.initialize()
        self._context.auto_detect_and_set_language(user_message)
        self._context.add_user_message(user_message)

        response = self._try_greeting(user_message)
        if response is not None:
            self._context.add_assistant_message(response.message)
            return response

        # Bellek kaydet/sorgula — LLM'e gerek yok, doğrudan döner
        response = self._try_memory_operation(user_message)
        if response is not None:
            self._context.add_assistant_message(response.message)
            return response

        response = self._try_fast_path(user_message)
        if response is not None:
            self._context.add_assistant_message(response.message)
            self._process_memory(user_message, response.message)
            return response

        response = self._run_llm_loop(user_message)
        self._context.add_assistant_message(response.message)
        self._process_memory(user_message, response.message)
        return response

    # ══════════════════════════════════════════════════════════════
    #  BELLEK MOTORU — Otomatik bilgi çıkarımı ve kayıt
    # ══════════════════════════════════════════════════════════════

    # İsim/değer olarak kabul EDİLMEYECEK kelimeler (soru kelimeleri, zamir, ortak kelimeler)
    _NOT_A_VALUE = frozenset({
        # Soru kelimeleri
        "ne", "ney", "nedir", "neydi", "neyse", "kim", "kimin", "nerede", "nasil",
        "nasıl", "kac", "kacs", "hangi", "mi", "mu", "mı", "mü",
        # Zamirler
        "ben", "sen", "o", "biz", "siz", "onlar", "bu", "su", "onu",
        # Genel Türkçe kelimeler
        "var", "yok", "bir", "evet", "hayir", "tamam", "peki", "oldu",
        "gibi", "kadar", "icin", "ile", "de", "da", "ta", "te",
        "bilmiyorum", "hatirlamiyorum", "soyle", "soyledin",
        "adim", "ismim", "adi", "ismi",
    })

    # Kişisel bilgi örüntüleri (regex, Türkçe normalize edilmiş)
    # Yalnızca bildirim cümlelerinde eşleşir; soru cümlesi ise _NOT_A_VALUE filtreler
    _FACT_PATTERNS: list[tuple[str, str]] = [
        # İsim — "benim adım X", "adım X", "ismim X"
        (r"benim adim (\w{2,20})", "isim"),
        (r"^adim (\w{2,20})", "isim"),
        (r"benim ismim (\w{2,20})", "isim"),
        (r"^ismim (\w{2,20})", "isim"),
        # Yaş — "25 yaşındayım", "25 yaşım var"
        (r"\b(\d{1,3}) yasindayim\b", "yas"),
        (r"\b(\d{1,3}) yasim var\b", "yas"),
        # Şehir — "Ankara'da yaşıyorum", "İstanbul'da oturuyorum"
        (r"\b(\w{3,20})(?:da|de|ta|te) yasiyorum\b", "sehir"),
        (r"\b(\w{3,20})(?:da|de|ta|te) oturuyorum\b", "sehir"),
        (r"\b(\w{3,20}) sehrinde yasiyorum\b", "sehir"),
        # Meslek — "meslEğim X"
        (r"\bmeslegi?m (\w{3,20})\b", "meslek"),
    ]

    _SAVE_TRIGGERS = frozenset({
        "kaydet", "hatirla", "unutma", "aklinda tut", "not al", "not et",
        "bunu kaydet", "bunu hatirla", "onemli", "kaydetmeni istiyorum",
        "remember", "save this", "note this",
    })

    _JOB_WORDS = frozenset({
        "ogrenci", "muhendis", "doktor", "ogretmen", "yazilimci", "developer",
        "tasarimci", "avukat", "hemsire", "mudur", "memur", "isci", "calisan",
        "mimar", "psikolog", "pilot", "asker", "polis", "itfaiyeci",
    })

    # ── Bellek sorgulama anahtar kalıpları ────────────────────────────────────
    _MEMORY_QUERIES: dict[tuple, str] = {
        ("adim ne", "ismim ne", "benim adim ne", "adim nedir",
         "ismim nedir", "adini biliyor musun", "adimi biliyor musun",
         "benim ismim nedir", "benim adim nedir", "adimi hatirlıyor musun",
         "adimi hatirliyor musun"): "isim",
        ("yasim ne", "kac yasindayim", "yasim nedir", "kac yasinda"): "yas",
        ("nerede yasiyorum", "sehrim ne", "hangi sehirde",
         "sehrim nedir", "nerede oturuyorum"): "sehir",
        ("meslegi?m ne", "ne is yapiyorum", "meslegim ne",
         "meslegim nedir"): "meslek",
    }

    def _try_memory_operation(self, user_message: str) -> "BrainResponse | None":
        """Bellek kaydet/sorgula — LLM'e GEREK KALMADAN doğrudan yanıt üretir.

        Küçük LLM'ler bellek bağlamını görmezden gelebildiğinden,
        bu operasyonlar kod tarafından kesin olarak halleder.
        """
        from blue_ai.memory.manager import get_memory, get_session_memory
        perm  = get_memory()
        sess  = get_session_memory()
        msg_n = self._normalize_turkish(user_message.lower().strip().rstrip("?!."))

        # ── SORGULAMA: "adım ne?", "beni hatırlıyor musun?" ─────────────────
        # Soru işareti VEYA bilinen soru kalıbı
        is_question = (user_message.strip().endswith("?") or
                       any(q in msg_n.split() for q in
                           ("ne", "nedir", "neydi", "kim", "nerede", "nasil",
                            "hatirlıyor", "hatirliyor", "biliyor", "taniyor")))
        if is_question:
            # Belirli bir bilgi mi soruluyor?
            for keywords, fact_key in self._MEMORY_QUERIES.items():
                if any(kw in msg_n for kw in keywords):
                    value = perm.get_fact(fact_key)
                    if value:
                        replies = {
                            "isim": f"Adın {value}. 😊",
                            "yas":  f"{value} yaşındasın.",
                            "sehir": f"{value}'da yaşıyorsun.",
                            "meslek": f"Mesleğin {value}.",
                        }
                        return BrainResponse(
                            message=replies.get(fact_key, f"{fact_key}: {value}"),
                            response_type="success"
                        )
                    # Kayıt yok — LLM'e bırak
                    return None

            # "Beni tanıyor musun / hatırlıyor musun?"
            if any(kw in msg_n for kw in
                   ("beni taniyor", "beni hatirliyor", "beni hatirlıyor",
                    "bilgi var mi", "hakkimda ne biliyorsun")):
                facts = perm.get_all_facts()
                if facts:
                    label = {"isim": "İsim", "yas": "Yaş", "sehir": "Şehir",
                             "meslek": "Meslek"}
                    lines = ["Evet, seni hatırlıyorum! 🧠"]
                    for k, v in facts.items():
                        lines.append(f"• {label.get(k, k.capitalize())}: {v}")
                    return BrainResponse(message="\n".join(lines), response_type="success")
                return BrainResponse(
                    message="Henüz seni tanımıyorum. Adını, şehrini veya mesleğini söylersen hemen kaydederim!",
                    response_type="info"
                )

        # ── KAYDETME: "benim adım X", "X yaşındayım", "X'de yaşıyorum" ──────
        if not is_question:
            for pattern, fact_key in self._FACT_PATTERNS:
                m = re.search(pattern, msg_n)
                if not m:
                    continue
                value = m.group(1).strip()

                # Soru/zamir/ortak kelime filtresi
                if value in self._NOT_A_VALUE or len(value) < 2:
                    continue
                if fact_key != "yas" and value.isdigit():
                    continue
                if fact_key == "meslek" and value not in self._JOB_WORDS:
                    continue

                display = value.capitalize()
                perm.set_fact(fact_key, display)
                sess.add(f"{fact_key}: {display} kaydedildi ✓", pinned=True)
                self._context.invalidate_cache()  # Sonraki prompt'ta görsün

                confirms = {
                    "isim":   f"Merhaba {display}! 👋 Adını kaydettim, seni unutmayacağım.",
                    "yas":    f"Tamam, {display} yaşında olduğunu not ettim.",
                    "sehir":  f"Anladım, {display}'da yaşıyorsun. Kaydettim.",
                    "meslek": f"Anladım, mesleğin {display}. Not aldım.",
                }
                return BrainResponse(
                    message=confirms.get(fact_key,
                                         f"'{display}' kaydedildi. ✓"),
                    response_type="success"
                )

        return None  # Bellek işlemi değil → LLM'e devam

    def _process_memory(self, user_msg: str, ai_resp: str) -> None:
        """Her konuşmadan önemli bilgileri çıkar → uygun belleğe kaydet.

        Geçici bellek  → RAM, oturum boyunca yaşar
        Kalıcı bellek  → hafiza.txt, uygulama kapansa bile kalır
        """
        from blue_ai.memory.manager import get_memory, get_session_memory
        perm = get_memory()
        sess = get_session_memory()

        msg_norm = self._normalize_turkish(user_msg.lower().strip())

        # ── 1. Açık kaydet/hatırla komutu ──────────────────────────────
        explicit_save = any(t in msg_norm for t in self._SAVE_TRIGGERS)
        if explicit_save:
            # Konuşmayı kalıcı nota kaydet
            perm.add_note(user_msg[:200], tags="kullanici_notu")
            sess.add(f"📌 Kaydedildi: {user_msg[:80]}", pinned=True)
            self._context.invalidate_cache()
            return  # Explicit save yeterliyse devam etme

        # ── 2. Kişisel bilgi örüntüsü eşleştirme ──────────────────────
        saved_any = False
        # Soru cümlesi ise hiç eşleştirme yapma ("?" ile bitiyor veya soru kelimesi var)
        is_question = (user_msg.strip().endswith("?") or
                       any(q in msg_norm.split() for q in ("ne", "nedir", "kim", "nerede", "nasil")))

        if not is_question:
            for pattern, fact_key in self._FACT_PATTERNS:
                m = re.search(pattern, msg_norm)
                if not m:
                    continue
                value = m.group(1).strip()

                # Soru/zamir/ortak kelime kontrolü
                if value in self._NOT_A_VALUE:
                    continue
                # Çok kısa veya sadece rakam (yaş hariç)
                if len(value) < 2:
                    continue
                if fact_key != "yas" and value.isdigit():
                    continue
                # Meslek için bilinen meslek listesinde olmalı
                if fact_key == "meslek" and value not in self._JOB_WORDS:
                    continue

                display = value.capitalize()
                # Kalıcıya yaz
                perm.set_fact(fact_key, display)
                # Oturuma pinli not
                label_map = {"isim": "İsim", "yas": "Yaş", "sehir": "Şehir", "meslek": "Meslek"}
                label = label_map.get(fact_key, fact_key)
                sess.add(f"{label}: {display} (kalıcı kaydedildi ✓)", pinned=True)
                saved_any = True
                break

        # ── 3. Programlama dili / araç tercihi ─────────────────────────
        if not saved_any:
            tech_keywords = {
                "python": "Python", "javascript": "JavaScript", "java": "Java",
                "typescript": "TypeScript", "react": "React", "vue": "Vue",
                "django": "Django", "flutter": "Flutter", "swift": "Swift",
                "kotlin": "Kotlin", "rust": "Rust", "golang": "Go",
                "docker": "Docker", "kubernetes": "Kubernetes", "linux": "Linux",
            }
            use_words = {"kullaniyorum", "seviyorum", "ogreniyorum", "biliyorum",
                         "calisiyorum", "yaziyorum"}
            has_use = any(w in msg_norm for w in use_words)
            if has_use:
                for tech_norm, tech_name in tech_keywords.items():
                    if tech_norm in msg_norm:
                        perm.set_fact(f"kullanim_{tech_norm}", tech_name)
                        sess.add(f"Teknoloji: {tech_name} kullanıyor (kaydedildi ✓)", pinned=True)
                        saved_any = True
                        break

        # ── 4. Genel oturum notu (önemli konuşmalar için) ──────────────
        # Sadece uzun/anlamlı mesajları oturuma ekle (geçici, pin'siz)
        if len(user_msg.strip()) > 30 and not saved_any:
            short = user_msg.strip()[:90]
            sess.add(f"K: {short}", pinned=False)

        # Cache'i yenile — oturum belleği değişti
        if saved_any:
            self._context.invalidate_cache()

    def _try_fast_path(self, user_message: str) -> "BrainResponse | None":
        """Hızlı intent tespiti — LLM atlanır (<200ms).

        Önce ML modeli dener (yüksek doğruluk), sonra keyword eşleştirme.
        Her iki yöntemde de bir tool bulunamazsa None döner → LLM'e gidilir.
        """
        intent = self._detect_intent_fast(user_message)
        if intent is None:
            return None

        tool = self._registry.get(intent)
        if not tool:
            return None

        # Intent'e göre parametre çıkar
        tool_args = self._extract_fast_path_args(intent, user_message)

        if tool.permission_level.value >= 3:
            return BrainResponse(
                message=tool.get_confirmation_message(**tool_args),
                response_type="confirm",
                pending_confirmation={
                    "tool_name": intent,
                    "arguments": tool_args,
                    "message": tool.get_confirmation_message(**tool_args),
                },
            )

        result = self._registry.execute_tool(intent, **tool_args)
        return BrainResponse(
            message=result.message or result.to_llm_context(),
            response_type="success" if result.success else "error",
        )

    def _extract_fast_path_args(self, intent: str, user_message: str) -> dict:
        """Fast path için intent'e özel parametre çıkarımı."""
        if intent == "get_weather":
            return {"city": self._extract_city_from_message(user_message)}
        return {}

    # Bilinen Türkiye şehirleri (hızlı eşleştirme için)
    _KNOWN_CITIES = {
        "istanbul", "ankara", "izmir", "bursa", "antalya", "adana", "konya",
        "gaziantep", "mersin", "kayseri", "eskisehir", "samsun", "trabzon",
        "erzurum", "diyarbakir", "malatya", "siirt", "urfa", "sanliurfa",
        "van", "batman", "mardin", "hatay", "antakya", "kahramanmaras",
        "manisa", "balikesir", "tekirdag", "sakarya", "kocaeli", "gebze",
        "denizli", "muğla", "mugla", "afyon", "afyonkarahisar", "usak",
        "kutahya", "bilecik", "bolu", "duzce", "zonguldak", "karabuk",
        "kastamonu", "sinop", "amasya", "tokat", "corum", "yozgat",
        "kirikkale", "kirsehir", "nevsehir", "aksaray", "nigde", "karaman",
        "isparta", "burdur", "aydin", "canakkale", "edirne", "kirklareli",
        "golhisar", "burdur", "fethiye", "bodrum", "marmaris", "kusadasi",
        "london", "paris", "berlin", "madrid", "rome", "roma", "moscow",
        "tokyo", "dubai", "new york", "newyork", "amsterdam", "vienna",
    }

    def _extract_city_from_message(self, message: str) -> str:
        """Mesajdan şehir adını çıkar — önce bilinen şehir listesi, sonra akıllı soyma."""
        msg_lower = message.lower()
        msg_norm = self._normalize_turkish(msg_lower)

        # 1. Bilinen şehir listesinde ara (en güvenilir)
        for city in self._KNOWN_CITIES:
            if city in msg_norm or city in msg_lower:
                return city.capitalize()

        # 2. Türkçe eklerle gelen şehir adını çıkar
        skip_words = {
            "hava", "durumu", "duumu", "weather", "nasil", "nasıl",
            "bugun", "bugün", "yarin", "yarın", "sicaklik", "sıcaklık",
            "kac", "kaç", "derece", "celsius", "fahrenheit",
            "nedir", "ne", "var", "olan", "icin", "için", "mi",
            "bir", "sehir", "şehir", "yerde", "bölge", "bolge",
            "bugunku", "bugunun", "simdi", "şimdi", "simdiki",
        }
        # Türkçe konum ekleri (uzundan kısaya — doğru soyma için)
        loc_suffixes = ["'nda", "'nde", "'nda", "'nde", "ninda", "ninde",
                        "'da", "'de", "'ta", "'te", "nda", "nde", "da", "de", "ta", "te"]
        words = msg_lower.split()
        city_candidates = []
        for w in words:
            clean = w.strip("'\",.!?")
            # En uzun eşleşen eki soy
            for suffix in loc_suffixes:
                if clean.endswith(suffix) and len(clean) > len(suffix) + 2:
                    clean = clean[: -len(suffix)]
                    break
            clean_norm = self._normalize_turkish(clean.strip("'\""))
            if (clean_norm and clean_norm not in skip_words
                    and len(clean_norm) > 2
                    and not clean_norm.isdigit()):
                city_candidates.append(clean_norm)

        if city_candidates:
            return city_candidates[0].capitalize()
        return "Istanbul"

    # ML modelinin üzerinde öncelikli keyword'ler (ML yanlış tahmin etse bile bunlar kazanır)
    _HIGH_PRIORITY_KEYWORDS: dict[str, str] = {
        "hava durumu": "get_weather",
        "hava nasil": "get_weather",
        "hava nasıl": "get_weather",
        "hava ne": "get_weather",
        "weather": "get_weather",
        "sicaklik": "get_weather",
        "sıcaklık": "get_weather",
        "yagmur": "get_weather",
        "yağmur": "get_weather",
    }

    def _detect_intent_fast(self, user_message: str) -> "str | None":
        """Yüksek öncelikli keyword → ML model → genel keyword → None sırasıyla."""
        msg_lower = user_message.lower().strip()
        msg_norm = self._normalize_turkish(msg_lower)

        # 0. Yüksek öncelikli keyword — ML modelinden önce (yanlış tahmini engeller)
        for keyword, tool_name in self._HIGH_PRIORITY_KEYWORDS.items():
            if keyword in msg_norm or keyword in msg_lower:
                return tool_name
        # "hava" kelimesi tek başına da yeter (ama "hava alanı" gibi istisnalar olabilir)
        if ("hava" in msg_lower.split() or "hava" in msg_norm.split()):
            return "get_weather"

        # 1. ML model (en yüksek doğruluk, ~10-50ms)
        try:
            ml_result = self._predict_with_ml_model(user_message)
            if ml_result:
                intent = ml_result["intent"]
                confidence = ml_result["confidence"]
                if confidence >= 0.70 and intent in self._FAST_PATH_INTENTS:
                    return intent
        except Exception:
            pass

        # 2. Genel keyword eşleştirme (ML yoksa veya düşük güvende, ~0ms)
        for keyword, tool_name in self._KEYWORD_MAP.items():
            if keyword in msg_norm or keyword in msg_lower:
                return tool_name

        return None

    def _try_greeting(self, user_message: str) -> "BrainResponse | None":
        """Selamlama/sohbet mesajlarını anında yanıtla — LLM bypass (~0ms)."""
        msg = self._normalize_turkish(user_message.lower().strip())
        # Noktalama temizle
        for ch in ".,!?":
            msg = msg.replace(ch, "")
        msg = msg.strip()
        reply = self._GREETINGS.get(msg)
        if reply:
            return BrainResponse(message=reply, response_type="info")
        # Başlangıç eşleştirme (örn. "merhaba blue")
        for greeting, answer in self._GREETINGS.items():
            if msg.startswith(greeting):
                return BrainResponse(message=answer, response_type="info")
        return None

    def process_stream(self, user_message: str):
        """Streaming generator — LLM tokenları tek tek yield eder.

        Yields:
            {"type": "chunk", "text": str}   — LLM'den gelen token
            {"type": "final", "text": str, "response_type": str, ...} — bitiş/sonuç
        """
        self.initialize()
        self._context.auto_detect_and_set_language(user_message)
        self._context.add_user_message(user_message)

        # ── Selamlama: anında cevap (~0ms) ───────────────────────────────
        response = self._try_greeting(user_message)
        if response is not None:
            self._context.add_assistant_message(response.message)
            yield {"type": "final", "text": response.message, "response_type": response.response_type,
                   "pending_confirmation": None, "tool_calls": []}
            return

        # ── Fast path: anında cevap (LLM yok) ────────────────────────────
        response = self._try_fast_path(user_message)
        if response is not None:
            self._context.add_assistant_message(response.message)
            yield {
                "type": "final",
                "text": response.message,
                "response_type": response.response_type,
                "pending_confirmation": response.pending_confirmation,
                "tool_calls": response.tool_calls,
            }
            return

        # ── LLM yok ────────────────────────────────────────────────────
        llm = get_llm()
        if not llm.is_available():
            response = self._handle_without_llm(user_message)
            self._context.add_assistant_message(response.message)
            yield {"type": "final", "text": response.message, "response_type": response.response_type}
            return

        # ── LLM streaming ──────────────────────────────────────────────
        messages = self._context.build_messages()
        full_text = ""

        for chunk in llm.chat_stream(messages, temperature=0.3):
            if chunk:
                full_text += chunk
                yield {"type": "chunk", "text": chunk}

        # Tool call var mı kontrol et
        tool_call = self._extract_tool_call(full_text)
        if tool_call:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("arguments", {})
            tool = self._registry.get(tool_name)

            if not tool:
                msg = f"Tool bulunamadı: '{tool_name}'"
                self._context.add_assistant_message(msg)
                yield {"type": "final", "text": msg, "response_type": "error"}
                return

            permission = self._permission.check_permission(
                tool_name=tool_name,
                permission_level=tool.permission_level,
                arguments=tool_args,
                confirmation_message=tool.get_confirmation_message(**tool_args),
            )
            if permission.denied:
                msg = permission.confirmation_message or "Engellendi."
                self._context.add_assistant_message(msg)
                yield {"type": "final", "text": msg, "response_type": "error"}
                return
            if not permission.approved:
                self._context.add_assistant_message(permission.confirmation_message)
                yield {
                    "type": "final",
                    "text": permission.confirmation_message,
                    "response_type": "confirm",
                    "pending_confirmation": {
                        "tool_name": tool_name,
                        "arguments": tool_args,
                        "message": permission.confirmation_message,
                    },
                }
                return

            result = self._registry.execute_tool(tool_name, **tool_args)
            self._context.add_tool_result(tool_name, result.to_llm_context())

            # Tool sonrası kısa LLM özeti (streaming değil — genelde 1-2 cümle)
            messages2 = self._context.build_messages()
            final_resp = llm.chat(messages2, temperature=0.3)
            final_text = self._clean_response(final_resp, has_tools=True)
            self._context.add_assistant_message(final_text)
            yield {
                "type": "final",
                "text": final_text,
                "response_type": "success" if result.success else "error",
                "tool_calls": [{"tool": tool_name, "success": result.success}],
            }
        else:
            clean = self._clean_response(full_text)
            self._context.add_assistant_message(clean)
            yield {"type": "final", "text": clean, "response_type": "info"}

    def process_confirmation(self, tool_name: str, approved: bool) -> BrainResponse:
        """Onay bekleyen işlemi onayla veya reddet."""
        if approved:
            self._permission.approve_pending(tool_name)
            # Tool'u çalıştır
            tool = self._registry.get(tool_name)
            if tool:
                # Pending request'ten argümanları al
                for req in self._permission.get_pending_requests():
                    if req.tool_name == tool_name:
                        result = self._registry.execute_tool(tool_name, **req.arguments)
                        self._permission.approve_pending(tool_name)
                        return BrainResponse(
                            message=result.message or result.to_llm_context(),
                            response_type="success" if result.success else "error",
                        )
            return BrainResponse(
                message="İşlem onaylandı ancak tool bulunamadı.",
                response_type="warning",
            )
        else:
            self._permission.deny_pending(tool_name)
            return BrainResponse(
                message="İşlem iptal edildi.",
                response_type="info",
            )

    def _run_llm_loop(self, user_message: str) -> BrainResponse:
        """LLM döngüsü — tool çağrılarını zincirler."""
        llm = get_llm()
        tool_calls_log = []

        # LLM erişilebilir mi kontrol et
        if not llm.is_available():
            return self._handle_without_llm(user_message)

        # İlk LLM çağrısı
        messages = self._context.build_messages()
        llm_response = llm.chat(messages, temperature=0.3)

        # Multi-step tool çağrı döngüsü
        for step in range(MAX_TOOL_STEPS):
            # Tool çağrısı var mı kontrol et
            tool_call = self._extract_tool_call(llm_response)

            if not tool_call:
                # Düz metin yanıtı — döngüyü bitir
                return BrainResponse(
                    message=self._clean_response(llm_response, has_tools=len(tool_calls_log) > 0),
                    response_type="info",
                    tool_calls=tool_calls_log,
                    raw_llm_response=llm_response,
                )

            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("arguments", {})

            # Tool'u registry'den bul
            tool = self._registry.get(tool_name)
            if not tool:
                # Bilinmeyen tool — LLM'e hata bildir
                error_msg = f"Tool bulunamadı: '{tool_name}'"
                self._context.add_tool_result(tool_name, error_msg)
                messages = self._context.build_messages()
                llm_response = llm.chat(messages, temperature=0.3)
                continue

            # Güvenlik kontrolü
            permission = self._permission.check_permission(
                tool_name=tool_name,
                permission_level=tool.permission_level,
                arguments=tool_args,
                confirmation_message=tool.get_confirmation_message(**tool_args),
            )

            if permission.denied:
                return BrainResponse(
                    message=permission.confirmation_message or "Bu işlem güvenlik nedeniyle engellendi.",
                    response_type="error",
                    tool_calls=tool_calls_log,
                )

            if not permission.approved:
                # Onay gerekli — kullanıcıya sor
                return BrainResponse(
                    message=permission.confirmation_message,
                    response_type="confirm",
                    tool_calls=tool_calls_log,
                    pending_confirmation={
                        "tool_name": tool_name,
                        "arguments": tool_args,
                        "message": permission.confirmation_message,
                    },
                )

            # Tool'u çalıştır
            result = self._registry.execute_tool(tool_name, **tool_args)
            tool_calls_log.append({
                "tool": tool_name,
                "args": tool_args,
                "success": result.success,
                "message": result.message[:200],  # Kısa özet
            })

            # Sonucu bağlama ekle
            self._context.add_tool_result(tool_name, result.to_llm_context())

            # LLM'e sonucu gönder — özetlemesi/başka tool çağırması için
            messages = self._context.build_messages()
            llm_response = llm.chat(messages, temperature=0.3)

        # Max adım aşıldı
        return BrainResponse(
            message=self._clean_response(llm_response, has_tools=len(tool_calls_log) > 0),
            response_type="info",
            tool_calls=tool_calls_log,
            raw_llm_response=llm_response,
        )

    def _extract_tool_call(self, llm_response: str) -> dict | None:
        """LLM yanıtından tool çağrısını çıkar.

        LLM'in yanıtında şu formatı arar:
        ```json
        {"tool_call": {"name": "tool_adı", "arguments": {"param": "değer"}}}
        ```
        """
        if not llm_response:
            return None

        # JSON bloğu ara (```json ... ``` veya doğrudan {})
        patterns = [
            # ```json\n{...}\n```
            r'```(?:json)?\s*\n?\s*(\{[^`]*?"tool_call"[^`]*?\})\s*\n?\s*```',
            # Düz JSON: {"tool_call": ...}
            r'(\{"tool_call"\s*:\s*\{[^}]*\}\s*\})',
            # tool_call ile başlayan JSON
            r'(\{[^{}]*"tool_call"[^{}]*\{[^{}]*\}[^{}]*\})',
        ]

        for pattern in patterns:
            match = re.search(pattern, llm_response, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    if "tool_call" in data:
                        tc = data["tool_call"]
                        if "name" in tc:
                            return tc
                except (json.JSONDecodeError, KeyError):
                    continue

        # Daha esnek arama — name ve arguments ayrı ayrı
        name_match = re.search(r'"name"\s*:\s*"([^"]+)"', llm_response)
        args_match = re.search(r'"arguments"\s*:\s*(\{[^}]*\})', llm_response)

        if name_match:
            tool_name = name_match.group(1)
            # Bu gerçekten bir tool adı mı kontrol et
            if self._registry.get(tool_name):
                args = {}
                if args_match:
                    try:
                        args = json.loads(args_match.group(1))
                    except json.JSONDecodeError:
                        pass
                return {"name": tool_name, "arguments": args}

        return None

    def _clean_response(self, response: str, has_tools: bool = False) -> str:
        """LLM yanıtından gereksiz meta bilgileri temizle."""
        if not response:
            return "İşlem tamamlandı." if has_tools else "Bir sorun oluştu. Lütfen tekrar deneyin."

        # JSON tool_call bloklarını temizle
        response = re.sub(
            r'```json\s*\{[^`]*?"tool_call"[^`]*?\}\s*```',
            '', response
        ).strip()

        # Boş code block temizle
        response = re.sub(r'```\s*```', '', response).strip()

        if not response:
            return "İşlem tamamlandı."

        return response

    def _handle_without_llm(self, user_message: str) -> BrainResponse:
        """LLM olmadan ML model tabanlı intent tespiti (fallback).

        Ollama çalışmıyorsa, eğitilmiş ML modelini kullan (%99.22 doğruluk).
        ML model de yoksa basit keyword eşleştirme.
        """
        # 1. Eğitilmiş ML modelini dene
        ml_result = self._predict_with_ml_model(user_message)
        if ml_result:
            tool_name = ml_result["intent"]
            confidence = ml_result["confidence"]

            # general_question → LLM gerektirir, uyarı ver
            if tool_name == "general_question":
                return BrainResponse(
                    message=(
                        "Bu soruyu tam olarak cevaplayabilmem için LLM (Llama) gerekiyor.\n"
                        "Ollama'yı başlatmak için: `ollama serve`\n\n"
                        "Temel komutlar çalışır: sistem durumu, süreçler, temizle, disk, ağ, ram, yardım"
                    ),
                    response_type="warning",
                )

            # Tool'u çalıştır (güven %60'dan yüksekse)
            if confidence > 0.6:
                tool = self._registry.get(tool_name)
                if tool:
                    # Onay gerektiren işlemler için mesaj göster
                    if tool.permission_level.value >= 3:  # CONFIRM
                        return BrainResponse(
                            message=tool.get_confirmation_message(),
                            response_type="confirm",
                            pending_confirmation={
                                "tool_name": tool_name,
                                "arguments": {},
                                "message": tool.get_confirmation_message(),
                            },
                        )

                    result = self._registry.execute_tool(tool_name)
                    return BrainResponse(
                        message=result.message or result.to_llm_context(),
                        response_type="success" if result.success else "error",
                    )

        # 2. ML model yoksa keyword fallback
        return self._keyword_fallback(user_message)

    def _predict_with_ml_model(self, text: str) -> dict | None:
        """Eğitilmiş ML modeliyle intent tahmini.

        Model henüz yüklenmemişse hemen None döner (keyword fallback'e geçer).
        Model arka planda yükleniyorsa beklemeden None döner.
        """
        # Model hazır değilse beklemeden None dön — keyword fallback kullanılacak
        if not Brain._ml_model_ready:
            # Yükleme başlamadıysa başlat (arka planda, bloklamaz)
            if not Brain._ml_model_loading:
                self._load_ml_model_bg()
            return None

        try:
            import numpy as np
            model = Brain._ml_model_cache
            if model is None:
                return None
            pipeline = model["pipeline"]
            normalized = self._normalize_turkish(text.lower().strip())
            intent = pipeline.predict([normalized])[0]
            proba = pipeline.predict_proba([normalized])[0]
            confidence = float(max(proba))
            return {"intent": intent, "confidence": confidence}
        except Exception:
            return None

    def _keyword_fallback(self, user_message: str) -> BrainResponse:
        """Basit keyword eşleştirme (son çare)."""
        msg = user_message.lower().strip()
        msg_ascii = self._normalize_turkish(msg)

        keyword_tool_map = {
            ("durum", "status", "nasil", "nasıl", "system", "sistem"): "system_status",
            ("surec", "süreç", "process", "gorev", "görev", "calisan", "çalışan"): "process_list",
            ("temizle", "clean", "temp", "temizlik"): "clean_temp",
            ("disk", "depolama", "storage"): "disk_info",
            ("ag", "ağ", "net", "internet", "baglanti", "bağlantı", "network"): "network_info",
            ("ram", "bellek", "memory", "hafiza", "hafıza"): "ram_info",
            ("pil", "batarya", "battery", "sarj", "şarj"): "battery_info",
            ("yardim", "yardım", "help", "komut", "ne yapabilirsin"): "help",
        }

        for keywords, tool_name in keyword_tool_map.items():
            if any(kw in msg or kw in msg_ascii for kw in keywords):
                result = self._registry.execute_tool(tool_name)
                return BrainResponse(
                    message=result.message or result.to_llm_context(),
                    response_type="success" if result.success else "error",
                )

        # Profil değişikliği
        profile_map = {
            ("oyun", "gaming", "game"): "gaming",
            ("is", "iş", "work", "calisma", "çalışma"): "work",
            ("tasarruf", "power_saver", "enerji"): "power_saver",
            ("dengeli", "balanced", "normal"): "balanced",
        }
        for keywords, profile in profile_map.items():
            if any(kw in msg or kw in msg_ascii for kw in keywords):
                result = self._registry.execute_tool("change_profile", profile=profile)
                return BrainResponse(
                    message=result.message or result.to_llm_context(),
                    response_type="success" if result.success else "error",
                )

        return BrainResponse(
            message=(
                "Ollama sunucusu çalışmıyor. LLM özellikleri için:\n"
                "1. Ollama'yı başlatın: `ollama serve`\n"
                "2. Modeli yükleyin: `ollama pull llama3.1:8b-instruct-q4_K_M`\n\n"
                "Temel komutlar yine de çalışır: 'durum', 'süreçler', 'temizle', 'disk', 'ağ', 'ram', 'yardım'"
            ),
            response_type="warning",
        )

    @staticmethod
    def _normalize_turkish(text: str) -> str:
        """Türkçe karakterleri ASCII'ye çevir."""
        tr_map = {"ı": "i", "ö": "o", "ü": "u", "ş": "s", "ç": "c", "ğ": "g",
                  "İ": "I", "Ö": "O", "Ü": "U", "Ş": "S", "Ç": "C", "Ğ": "G"}
        for tr, en in tr_map.items():
            text = text.replace(tr, en)
        return text


# ─── Singleton ──────────────────────────────────────
_brain: Optional[Brain] = None


def get_brain() -> Brain:
    """Singleton brain döndür."""
    global _brain
    if _brain is None:
        _brain = Brain()
    return _brain
