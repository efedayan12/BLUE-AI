"""
BLUE_AI — Ollama LLM Bağlantısı

Yerel Ollama sunucusuyla iletişim kurar.
Gemma 2 2B — RTX 3050 GPU ile hızlandırılmış, Türkçe destekli.
Streaming, function calling ve retry desteği.

Performans optimizasyonları:
 - keep_alive: -1 → Model GPU'dan asla kaldırılmaz
 - num_ctx: 1024 → Minimum bağlam penceresi
 - num_predict: 256 → Kısa, hızlı yanıtlar
 - warmup() → İlk çağrıyı önceden yapar, cold start'ı önler
"""

import httpx
import json
import time
from typing import Optional, Generator


OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "gemma3:1b"

# Fallback modeller (küçükten büyüğe — hız öncelikli)
FALLBACK_MODELS = [
    "gemma3:1b",
    "gemma3:4b",
    "gemma2:2b",
    "gemma2",
    "qwen2.5:1.5b",
    "llama3.2:1b",
    "phi3:mini",
    "phi3",
    "llama3.1:8b",
    "mistral",
]

# Performans sabitleri
_TIMEOUT = 45.0          # 45s — timeout
_NUM_PREDICT = 400       # Maks token — kısa ve net cevap
_NUM_CTX = 1024          # Bağlam penceresi (2048→1024: yarı context = ~30% hız artışı)
_KEEP_ALIVE = -1         # -1 = modeli GPU'da sonsuza kadar tut
_REPEAT_PENALTY = 1.15   # Tekrar eden token'ları cezalandır
_TOP_K = 40              # Olası token seçimini daralt
_TOP_P = 0.9             # Nucleus sampling


class OllamaLLM:
    """Yerel Ollama LLM istemcisi — Gemma 2 2B odaklı."""

    def __init__(self, model: str = DEFAULT_MODEL, base_url: str = OLLAMA_URL):
        self.model = model
        self.base_url = base_url
        self._client = httpx.Client(timeout=_TIMEOUT)
        self._async_client = httpx.AsyncClient(timeout=_TIMEOUT)
        self._available: Optional[bool] = None
        self._last_check: float = 0
        self._active_model: Optional[str] = None
        self._warmed_up = False

    def _build_options(self, temperature: float) -> dict:
        """Ortak Ollama seçenekleri."""
        return {
            "temperature": temperature,
            "num_predict": _NUM_PREDICT,
            "num_gpu": 99,
            "num_ctx": _NUM_CTX,
            "repeat_penalty": _REPEAT_PENALTY,
            "top_k": _TOP_K,
            "top_p": _TOP_P,
        }

    def is_available(self) -> bool:
        """Ollama sunucusu çalışıyorsa True. 30 sn cache'li."""
        now = time.time()
        if self._available is not None and (now - self._last_check) < 30:
            return self._available
        try:
            r = self._client.get(f"{self.base_url}/api/tags", timeout=3.0)
            self._available = r.status_code == 200
            self._last_check = now
            return self._available
        except Exception:
            self._available = False
            self._last_check = now
            return False

    def _resolve_model(self) -> str:
        """Kullanılacak modeli belirle.

        Eğer tercih edilen model (gemma3:1b) henüz yüklü değilse fallback'e düşer.
        Her 60s'de bir yeniden kontrol eder — model sonradan kurulursa otomatik geçer.
        """
        preferred_prefix = self.model.split(":")[0]

        # Tercih edilen model zaten aktifse direkt dön
        if self._active_model and self._active_model.startswith(preferred_prefix):
            return self._active_model

        # Tercih edilmeyen bir fallback aktifse 60s'de bir yeniden kontrol et
        if self._active_model:
            if (time.time() - self._last_check) < 60:
                return self._active_model
            self._active_model = None  # Yeniden sorgula

        try:
            r = self._client.get(f"{self.base_url}/api/tags", timeout=3.0)
            self._last_check = time.time()
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]

                # Önce tercih edilen model ailesini ara
                for m in models:
                    if m.startswith(preferred_prefix):
                        self._active_model = m
                        print(f"[LLM] Model seçildi: {m}")
                        return m

                # Fallback listesini sırayla dene (küçükten büyüğe)
                for fallback in FALLBACK_MODELS:
                    fp = fallback.split(":")[0]
                    for m in models:
                        if m.startswith(fp):
                            self._active_model = m
                            print(f"[LLM] Fallback model: {m}")
                            return m

                # Son çare: listedeki ilk model
                if models:
                    self._active_model = models[0]
                    return models[0]
        except Exception:
            pass

        return self.model

    def warmup(self) -> bool:
        """Modeli GPU'ya yükle (cold start'ı önle).
        
        Bu metod uygulama başlangıcında çağrılır.
        keep_alive=-1 ile model GPU'da kalıcı olarak tutulur.
        """
        if self._warmed_up:
            return True

        model = self._resolve_model()
        try:
            # Kısa bir istek gönder — modeli GPU'ya yükletir
            payload = {
                "model": model,
                "prompt": "Merhaba",
                "stream": False,
                "keep_alive": _KEEP_ALIVE,
                "options": {
                    "num_predict": 1,   # Sadece 1 token — hızlı
                    "num_gpu": 99,
                    "num_ctx": _NUM_CTX,
                },
            }
            # Warmup için uzun timeout — model ilk yüklemede 60-120s sürebilir
            r = self._client.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=180.0,
            )
            if r.status_code == 200:
                self._warmed_up = True
                print(f"[LLM] Model sicak: {model} (GPU'da kalici)")
                return True
            return False
        except Exception as e:
            print(f"[LLM] Warmup hatasi: {e}")
            return False

    def get_model_info(self) -> dict:
        """Aktif model bilgilerini döndür."""
        model = self._resolve_model()
        return {
            "requested_model": self.model,
            "active_model": model,
            "available": self.is_available(),
        }

    def generate(self, prompt: str, system: str = "", temperature: float = 0.7) -> str:
        """Senkron metin üretimi."""
        model = self._resolve_model()
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "keep_alive": _KEEP_ALIVE,
                "options": self._build_options(temperature),
            }
            if system:
                payload["system"] = system

            r = self._client.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=_TIMEOUT,
            )
            if r.status_code == 200:
                return r.json().get("response", "").strip()
            return f"Hata: HTTP {r.status_code}"
        except httpx.ConnectError:
            return "Hata: Ollama sunucusu çalışmıyor. 'ollama serve' ile başlatın."
        except httpx.ReadTimeout:
            return "Hata: Yanıt zaman aşımına uğradı."
        except Exception as e:
            return f"Hata: {str(e)}"

    async def generate_async(self, prompt: str, system: str = "", temperature: float = 0.7) -> str:
        """Asenkron metin üretimi."""
        model = self._resolve_model()
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "keep_alive": _KEEP_ALIVE,
                "options": self._build_options(temperature),
            }
            if system:
                payload["system"] = system

            r = await self._async_client.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=_TIMEOUT,
            )
            if r.status_code == 200:
                return r.json().get("response", "").strip()
            return f"Hata: HTTP {r.status_code}"
        except httpx.ConnectError:
            return "Hata: Ollama çalışmıyor."
        except Exception as e:
            return f"Hata: {str(e)}"

    def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        """Chat formatı ile konuşma — ana beyin iletişim metodu."""
        model = self._resolve_model()
        try:
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "keep_alive": _KEEP_ALIVE,
                "options": self._build_options(temperature),
            }
            r = self._client.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=_TIMEOUT,
            )
            if r.status_code == 200:
                return r.json().get("message", {}).get("content", "").strip()
            return f"Hata: HTTP {r.status_code}"
        except httpx.ConnectError:
            return "Ollama sunucusu çalışmıyor."
        except httpx.ReadTimeout:
            return "Yanıt zaman aşımına uğradı."
        except Exception as e:
            return f"Hata: {str(e)}"

    async def chat_async(self, messages: list[dict], temperature: float = 0.7) -> str:
        """Asenkron chat."""
        model = self._resolve_model()
        try:
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "keep_alive": _KEEP_ALIVE,
                "options": self._build_options(temperature),
            }
            r = await self._async_client.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=_TIMEOUT,
            )
            if r.status_code == 200:
                return r.json().get("message", {}).get("content", "").strip()
            return f"Hata: HTTP {r.status_code}"
        except Exception as e:
            return f"Hata: {str(e)}"

    def chat_stream(self, messages: list[dict], temperature: float = 0.7) -> Generator[str, None, None]:
        """Streaming chat — karakter karakter yanıt."""
        model = self._resolve_model()
        try:
            payload = {
                "model": model,
                "messages": messages,
                "stream": True,
                "keep_alive": _KEEP_ALIVE,
                "options": self._build_options(temperature),
            }
            with self._client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=_TIMEOUT,
            ) as response:
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception:
            yield ""


# Singleton
_llm: Optional[OllamaLLM] = None


def get_llm(model: str = DEFAULT_MODEL) -> OllamaLLM:
    global _llm
    if _llm is None:
        _llm = OllamaLLM(model=model)
    elif _llm.model != model:
        # İstenen model değiştiyse singleton'ı sıfırla
        _llm = OllamaLLM(model=model)
    return _llm


def reset_llm_model() -> None:
    """Model cache'ini temizle — bir sonraki çağrıda yeniden sorgular."""
    global _llm
    if _llm is not None:
        _llm._active_model = None
        _llm._warmed_up = False
