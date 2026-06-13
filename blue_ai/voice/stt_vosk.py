"""
BLUE_AI — Vosk STT Motoru (Speech to Text)

Vosk-API kullanarak sesi metne çevirir.
Tamamen offline çalışır, CPU tabanlı, hafif ve hızlı.

Whisper'a alternatif olarak tasarlanmıştır.
Config'den stt_engine = "vosk" ile aktifleştirilir.

Avantajları:
 - Tamamen offline (internet gerektirmez)
 - Hafif (~45 MB small model)
 - Hızlı başlangıç (model yükleme ~1s)
 - Düşük CPU/RAM kullanımı
 - Gerçek zamanlı streaming desteği

Dezavantajları:
 - Whisper'a göre daha düşük doğruluk
 - Sınırlı dil desteği (model bağımlı)
"""

import os
import json
import queue
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from typing import Optional, Callable

# Lazy import
try:
    import sounddevice as sd
    SD_AVAILABLE = True
except (ImportError, OSError):
    SD_AVAILABLE = False

try:
    import soundfile as sf
    SF_AVAILABLE = True
except ImportError:
    SF_AVAILABLE = False

try:
    import numpy as np
    NP_AVAILABLE = True
except ImportError:
    NP_AVAILABLE = False

try:
    from vosk import Model, KaldiRecognizer, SetLogLevel
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False


# Vosk Türkçe model URL'leri
VOSK_MODEL_URLS = {
    "small": "https://alphacephei.com/vosk/models/vosk-model-small-tr-0.3.zip",
    "large": "https://alphacephei.com/vosk/models/vosk-model-tr-0.3.zip",
}

VOSK_MODEL_DIRS = {
    "small": "vosk-model-small-tr-0.3",
    "large": "vosk-model-tr-0.3",
}


def _check_vosk_deps() -> str:
    """Vosk bağımlılıklarını kontrol et."""
    missing = []
    if not SD_AVAILABLE:
        missing.append("sounddevice")
    if not NP_AVAILABLE:
        missing.append("numpy")
    if not VOSK_AVAILABLE:
        missing.append("vosk")

    if missing:
        return f"Eksik paketler: {', '.join(missing)}. Kurmak için: pip install {' '.join(missing)}"
    return ""


class VoskSTTEngine:
    """Vosk tabanlı Speech-to-Text motoru.
    
    Whisper STTEngine ile aynı arayüze sahip — drop-in replacement.
    """

    def __init__(self, model_path: str = "", model_size: str = "small"):
        """
        Args:
            model_path: Vosk model dizini yolu. Boşsa otomatik indirir.
            model_size: "small" (~45 MB) veya "large" (~1.5 GB)
        """
        self.model_path = model_path
        self.model_size = model_size
        self.model: Optional["Model"] = None
        self._is_listening = False
        self._listen_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.samplerate = 16000

        # Sessizlik tespiti parametreleri (Whisper ile aynı)
        self.silence_threshold = 0.010
        self.silence_duration = 1.2

        # PTT (Push-to-Talk) kayıt durumu
        self._recording = False
        self._recording_chunks: list = []
        self._recording_thread: Optional[threading.Thread] = None
        self._ptt_stream = None

    def _get_model_dir(self) -> str:
        """Model dizinini belirle veya indir."""
        import sys

        # Kullanıcı yol belirtmişse ve gerçekten varsa onu kullan
        if self.model_path and os.path.isdir(self.model_path):
            return self.model_path

        model_dir_name = VOSK_MODEL_DIRS.get(self.model_size, VOSK_MODEL_DIRS["small"])

        # Aday dizinler — PyInstaller + kaynak kod için sırayla dene
        candidates: list[Path] = []

        if getattr(sys, "frozen", False):
            # PyInstaller EXE: sys.executable = dist/BLUE_AI/BLUE_AI.exe
            exe_dir = Path(sys.executable).parent
            candidates.append(exe_dir / "_internal" / "data" / "models" / model_dir_name)
            candidates.append(exe_dir / "data" / "models" / model_dir_name)

        # Kaynak kod yapısı
        candidates.append(Path(__file__).resolve().parent.parent.parent / "data" / "models" / model_dir_name)

        # Sabit fallback — proje kök dizini
        candidates.append(Path("C:/BLUE_AI/data/models") / model_dir_name)

        for candidate in candidates:
            if candidate.exists():
                print(f"[Vosk] Model dizini: {candidate}")
                return str(candidate)

        # Hiçbiri bulunamadı — indir (kaynak modda çalışırken)
        if getattr(sys, "frozen", False):
            # EXE modunda indirme yapma — _internal'ı yazmak sorunlu olabilir
            # Proje kök dizinine yaz
            base_dir = Path("C:/BLUE_AI/data/models")
        else:
            base_dir = Path(__file__).resolve().parent.parent.parent / "data" / "models"

        return self._download_model(base_dir, model_dir_name)

    def _download_model(self, base_dir: Path, model_dir_name: str) -> str:
        """Vosk Türkçe modelini indir ve çıkart."""
        import requests

        url = VOSK_MODEL_URLS.get(self.model_size, VOSK_MODEL_URLS["small"])
        model_dir = base_dir / model_dir_name
        zip_path = base_dir / f"{model_dir_name}.zip"

        base_dir.mkdir(parents=True, exist_ok=True)

        print(f"[Vosk] Türkçe model indiriliyor: {self.model_size} ({url})")
        print(f"[Vosk] Hedef: {model_dir}")

        try:
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = (downloaded / total_size) * 100
                        if downloaded % (1024 * 1024) < 8192:  # Her ~1 MB'de yazdır
                            print(f"[Vosk] İndiriliyor... {pct:.0f}%")

            print(f"[Vosk] Çıkartılıyor: {zip_path}")
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(base_dir)

            # ZIP dosyasını temizle
            zip_path.unlink(missing_ok=True)

            if model_dir.exists():
                print(f"[Vosk] Model hazır: {model_dir}")
                return str(model_dir)
            else:
                # Bazı zip'ler farklı klasör adı ile çıkabilir
                extracted = [d for d in base_dir.iterdir() if d.is_dir() and "vosk" in d.name.lower()]
                if extracted:
                    return str(extracted[0])
                raise FileNotFoundError(f"Model dizini bulunamadı: {model_dir}")

        except Exception as e:
            print(f"[Vosk] Model indirme hatası: {e}")
            # ZIP dosyasını temizle
            if zip_path.exists():
                zip_path.unlink(missing_ok=True)
            raise

    def load_model(self) -> bool:
        """Vosk modelini belleğe yükle (singleton)."""
        if not VOSK_AVAILABLE:
            print("[Vosk] Uyarı: vosk paketi kurulu değil. pip install vosk")
            return False

        if self.model is not None:
            return True  # Zaten yüklenmiş

        try:
            SetLogLevel(-1)  # Vosk log'larını sustur
            model_dir = self._get_model_dir()
            self.model = Model(model_dir)
            print(f"[Vosk] Model yüklendi: {model_dir}")
            return True
        except Exception as e:
            print(f"[Vosk] Model yükleme hatası: {e}")
            self.model = None
            return False

    def transcribe_file(self, audio_file: str) -> str:
        """Kayıtlı ses dosyasını metne çevirir."""
        if not self.model:
            if not self.load_model():
                return ""

        try:
            # Ses dosyasını oku
            import wave

            # Önce soundfile ile WAV'a çevir (format uyumu için)
            if SF_AVAILABLE:
                data, sr = sf.read(audio_file, dtype='int16')
                if sr != self.samplerate:
                    # Resample gerekirse numpy ile basit
                    import numpy as np
                    ratio = self.samplerate / sr
                    n_samples = int(len(data) * ratio)
                    indices = np.linspace(0, len(data) - 1, n_samples).astype(int)
                    data = data[indices]

                temp_dir = tempfile.gettempdir()
                wav_path = os.path.join(temp_dir, "blue_ai_vosk_temp.wav")
                sf.write(wav_path, data, self.samplerate, subtype='PCM_16')
            else:
                wav_path = audio_file

            # Vosk ile çözümle
            rec = KaldiRecognizer(self.model, self.samplerate)
            rec.SetWords(True)

            with wave.open(wav_path, "rb") as wf:
                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break
                    rec.AcceptWaveform(data)

            result = json.loads(rec.FinalResult())
            text = result.get("text", "").strip()
            return text

        except Exception as e:
            print(f"[Vosk] Transcribe hatası: {e}")
            return ""

    def record_and_transcribe(self, duration: int = 5) -> str:
        """Sabit süreli ses kaydeder ve metne çevirir."""
        dep_error = _check_vosk_deps()
        if dep_error:
            print(dep_error)
            return ""

        if not self.load_model():
            return ""

        print(f"[Vosk] Dinleniyor... ({duration}s)")
        try:
            audio_data = sd.rec(
                int(duration * self.samplerate),
                samplerate=self.samplerate,
                channels=1,
                dtype='int16'  # Vosk int16 bekler
            )
            sd.wait()

            # Geçici dosyaya yaz
            temp_dir = tempfile.gettempdir()
            audio_file = os.path.join(temp_dir, "blue_ai_vosk_rec.wav")
            sf.write(audio_file, audio_data, self.samplerate, subtype='PCM_16')

            text = self.transcribe_file(audio_file)
            if text:
                print(f"[Vosk] Anlaşılan: {text}")
            return text

        except Exception as e:
            print(f"[Vosk] Ses kayıt hatası: {e}")
            return ""

    def record_until_silence(self, max_duration: int = 15) -> str:
        """RMS + Vosk hibrit ses tespiti ile kayıt.

        Sadece Vosk'un partial sonucunu beklememek için RMS kontrolü de yapılır.
        Kullanıcı konuştuğunda (yüksek RMS) Vosk tanısa da tanımasa da kayıt devam eder.
        Kayıt bittikten sonra tüm ses tek seferde Vosk'a gönderilir.
        """
        dep_error = _check_vosk_deps()
        if dep_error:
            print(f"[Vosk] {dep_error}")
            return ""

        if not self.load_model():
            print("[Vosk] Model yüklenemedi.")
            return ""

        q: queue.Queue = queue.Queue()
        audio_chunks_int16: list = []   # int16 bytes — Vosk için
        speech_started = False
        silence_start: Optional[float] = None
        # Gürültü tabanı: ilk 0.5s'de ölçülür
        noise_floor = self.silence_threshold
        noise_samples: list = []

        def _audio_cb(indata, frames, time_info, status):
            q.put(bytes(indata))

        print("[Vosk] Dinleniyor... (Konuşun, durduğunuzda otomatik kesilir)")
        try:
            with sd.RawInputStream(
                samplerate=self.samplerate,
                blocksize=int(self.samplerate * 0.1),  # 100ms chunk
                dtype='int16',
                channels=1,
                callback=_audio_cb,
            ):
                start_time = time.time()
                while time.time() - start_time < max_duration:
                    try:
                        data = q.get(timeout=0.3)
                    except queue.Empty:
                        if speech_started and silence_start is not None:
                            if time.time() - silence_start > self.silence_duration:
                                break
                        continue

                    audio_chunks_int16.append(data)

                    # RMS hesapla (int16 → float normalize)
                    arr = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                    rms = float(np.sqrt(np.mean(arr ** 2)))

                    # Gürültü tabanını ilk 0.5s'de öğren
                    if time.time() - start_time < 0.5:
                        noise_samples.append(rms)
                        if noise_samples:
                            noise_floor = max(self.silence_threshold,
                                              float(np.mean(noise_samples)) * 1.8)
                        continue

                    # Konuşma tespiti: RMS eşiğini aştı mı?
                    if rms > noise_floor:
                        speech_started = True
                        silence_start = None
                    elif speech_started:
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start > self.silence_duration:
                            break

                    # 5 saniye içinde hiç ses yoksa pes et
                    if not speech_started and time.time() - start_time > 5:
                        print("[Vosk] Konuşma algılanamadı.")
                        return ""

            if not audio_chunks_int16 or not speech_started:
                return ""

            # Tüm ses verisini birleştir ve Vosk ile tanı
            rec = KaldiRecognizer(self.model, self.samplerate)
            rec.SetWords(True)

            result_parts = []
            chunk_size = 4000 * 2  # 4000 frame × 2 bytes (int16)
            all_bytes = b"".join(audio_chunks_int16)

            for i in range(0, len(all_bytes), chunk_size):
                chunk = all_bytes[i: i + chunk_size]
                if rec.AcceptWaveform(chunk):
                    word = json.loads(rec.Result()).get("text", "").strip()
                    if word:
                        result_parts.append(word)

            final = json.loads(rec.FinalResult()).get("text", "").strip()
            if final:
                result_parts.append(final)

            text = " ".join(result_parts).strip()
            if text:
                print(f"[Vosk] Anlaşılan: {text}")
            else:
                print("[Vosk] Ses alındı ancak metin çıkarılamadı.")
            return text

        except Exception as e:
            print(f"[Vosk] Kayıt hatası: {e}")
            return ""

    def start_recording(self):
        """PTT: mikrofon kaydını başlat — sd.InputStream ile doğrudan."""
        if not SD_AVAILABLE or not NP_AVAILABLE:
            print("[Vosk PTT] Eksik bağımlılık.")
            return
        if not self.load_model():
            print("[Vosk PTT] Model yüklenemedi.")
            return
        if self._recording:
            return

        self._recording = True
        self._recording_chunks = []

        def _cb(indata, frames, time_info, status):
            if status:
                print(f"[Vosk PTT] Ses durumu: {status}")
            # indata: numpy int16 (frames, 1) → bytes
            self._recording_chunks.append(indata[:, 0].tobytes())

        try:
            self._ptt_stream = sd.InputStream(
                samplerate=self.samplerate,
                channels=1,
                dtype='int16',
                blocksize=int(self.samplerate * 0.05),
                callback=_cb,
            )
            self._ptt_stream.start()
            print(f"[Vosk PTT] Stream başladı. Cihaz: {sd.query_devices(kind='input')['name']}")
        except Exception as e:
            print(f"[Vosk PTT] Stream açma hatası: {e}")
            self._recording = False
            self._ptt_stream = None

    def stop_and_transcribe(self) -> str:
        """PTT: kaydı durdur ve metne çevir."""
        self._recording = False

        if self._ptt_stream:
            try:
                self._ptt_stream.stop()
                self._ptt_stream.close()
            except Exception as e:
                print(f"[Vosk PTT] Stream kapatma hatası: {e}")
            self._ptt_stream = None

        chunks = self._recording_chunks[:]
        self._recording_chunks = []

        print(f"[Vosk PTT] Toplanan chunk sayısı: {len(chunks)}")

        if not chunks:
            print("[Vosk PTT] Ses kaydı boş.")
            return ""

        all_bytes = b"".join(chunks)
        num_samples = len(all_bytes) // 2
        duration = num_samples / self.samplerate
        print(f"[Vosk PTT] Kayıt süresi: {duration:.2f}s")

        if duration < 0.15:
            print("[Vosk PTT] Kayıt çok kısa.")
            return ""

        if not self.model:
            if not self.load_model():
                return ""

        rec = KaldiRecognizer(self.model, self.samplerate)
        rec.SetWords(True)

        result_parts = []
        chunk_size = 4000 * 2
        for i in range(0, len(all_bytes), chunk_size):
            chunk = all_bytes[i: i + chunk_size]
            if rec.AcceptWaveform(chunk):
                word = json.loads(rec.Result()).get("text", "").strip()
                if word:
                    result_parts.append(word)

        final = json.loads(rec.FinalResult()).get("text", "").strip()
        if final:
            result_parts.append(final)

        text = " ".join(result_parts).strip()
        if text:
            print(f"[Vosk PTT] Anlaşılan: {text}")
        else:
            print("[Vosk PTT] Boş döndü.")
        return text

    def record_realtime(self, max_duration: int = 10) -> str:
        """Gerçek zamanlı streaming ile ses tanıma.
        
        Vosk'un en güçlü özelliği: Ses gelirken anlık çözümleme.
        Whisper'da bu yetenek yoktur.
        """
        dep_error = _check_vosk_deps()
        if dep_error:
            print(f"[Vosk] {dep_error}")
            return ""

        if not self.load_model():
            return ""

        rec = KaldiRecognizer(self.model, self.samplerate)
        rec.SetWords(True)

        q = queue.Queue()
        result_text = ""
        silence_start = None

        def audio_callback(indata, frames, time_info, status):
            if status:
                print(f"[Vosk] Audio status: {status}")
            q.put(bytes(indata))

        print("[Vosk] Gerçek zamanlı dinleme... (Konuşun)")
        try:
            with sd.RawInputStream(
                samplerate=self.samplerate,
                blocksize=8000,
                dtype='int16',
                channels=1,
                callback=audio_callback
            ):
                start_time = time.time()
                while time.time() - start_time < max_duration:
                    try:
                        data = q.get(timeout=0.5)
                    except queue.Empty:
                        continue

                    if rec.AcceptWaveform(data):
                        partial = json.loads(rec.Result())
                        text = partial.get("text", "").strip()
                        if text:
                            result_text += " " + text
                            print(f"[Vosk] Tanındı: {text}")
                    else:
                        partial = json.loads(rec.PartialResult())
                        partial_text = partial.get("partial", "").strip()
                        if partial_text:
                            # Konuşma devam ediyor
                            silence_start = None
                        elif result_text:
                            # Sessizlik başladı
                            if silence_start is None:
                                silence_start = time.time()
                            elif time.time() - silence_start > self.silence_duration:
                                break

                # Son kalan kısmı al
                final = json.loads(rec.FinalResult())
                final_text = final.get("text", "").strip()
                if final_text:
                    result_text += " " + final_text

            result_text = result_text.strip()
            if result_text:
                print(f"[Vosk] Tam sonuç: {result_text}")
            return result_text

        except Exception as e:
            print(f"[Vosk] Gerçek zamanlı hata: {e}")
            return ""

    def start_listening(self, on_result: Callable[[str], None] = None):
        """Sürekli dinleme modunu başlat (arka plan thread)."""
        if self._is_listening:
            return

        dep_error = _check_vosk_deps()
        if dep_error:
            print(dep_error)
            return

        self._stop_event.clear()
        self._is_listening = True

        def _listen_loop():
            while not self._stop_event.is_set():
                text = self.record_until_silence(max_duration=10)
                if text and on_result:
                    on_result(text)
                elif text:
                    print(f"[Vosk] {text}")
                time.sleep(0.3)

            self._is_listening = False

        self._listen_thread = threading.Thread(target=_listen_loop, daemon=True)
        self._listen_thread.start()

    def stop_listening(self):
        """Sürekli dinleme modunu durdur."""
        self._stop_event.set()
        self._is_listening = False

    @property
    def is_listening(self) -> bool:
        return self._is_listening


# Singleton instance
_vosk_stt: Optional[VoskSTTEngine] = None


def get_vosk_stt(model_path: str = "", model_size: str = "small") -> VoskSTTEngine:
    """Vosk STT motorunu döndür (singleton)."""
    global _vosk_stt
    if _vosk_stt is None:
        _vosk_stt = VoskSTTEngine(model_path=model_path, model_size=model_size)
    return _vosk_stt
