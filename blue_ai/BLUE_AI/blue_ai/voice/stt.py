"""
BLUE_AI — Speech to Text (STT) Modülü

Sesi metne cevirmek icin Faster-Whisper kullanir.
Kullanicinin konustugunu tespit eder ve yaziya doker.
VRAM dostudur (small veya base modeli kullanimina olanak tanir).

Desteklenen modlar:
 - record_and_transcribe(): Sabit sureli kayit + ceviri
 - start_listening() / stop_listening(): Surekli dinleme dongusu
"""

import os
import queue
import tempfile
import threading
import time
from typing import Optional, Callable

# Lazy import — kurulu degilse hata vermesin
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
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


def _check_audio_deps() -> str:
    """Ses bagimliliklarini kontrol et, eksik varsa mesaj dondur."""
    missing = []
    if not SD_AVAILABLE:
        missing.append("sounddevice")
    if not SF_AVAILABLE:
        missing.append("soundfile")
    if not NP_AVAILABLE:
        missing.append("numpy")
    if not WHISPER_AVAILABLE:
        missing.append("faster-whisper")

    if missing:
        return f"Eksik paketler: {', '.join(missing)}. Kurmak icin: pip install {' '.join(missing)}"
    return ""


class STTEngine:
    """Sesi metne ceviren Whisper motoru."""

    def __init__(self, model_size: str = "small", device: str = "cpu", compute_type: str = "int8"):
        """
        Varsayilan olarak CPU + int8 kullanilir:
        - Her ortamda calisir (CUDA gerektirmez)
        - cublas64_12.dll hatasi olusturmaz
        - int8 CPU'da yeterince hizlidir (small model ~1-2s)
        GPU kullanmak isterseniz device='cuda', compute_type='int8_float16' ayarlayin.
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

        self.model = None
        self._is_listening = False
        self._listen_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.samplerate = 16000

        # Sessizlik tespiti parametreleri
        self.silence_threshold = 0.010  # Daha hassas
        self.silence_duration = 1.2     # Kaç saniye sessizlik olursa konuşma bitti say

        # PTT (Push-to-Talk) kayıt durumu
        self._recording = False
        self._recording_chunks: list = []
        self._recording_thread: Optional[threading.Thread] = None
        self._ptt_stream = None

    def _fallback_to_cpu(self) -> bool:
        """CUDA başarısızsa CPU moduna düş."""
        if not WHISPER_AVAILABLE:
            return False
        try:
            self.device = "cpu"
            self.compute_type = "int8"
            self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            print("Whisper CPU modunda yuklendi.")
            return True
        except Exception as e:
            print(f"CPU fallback basarisiz: {e}")
            self.model = None
            return False

    def load_model(self) -> bool:
        """Whisper modelini bellege yukler (singleton — sadece bir kez yuklenir)."""
        if not WHISPER_AVAILABLE:
            print("Uyari: faster-whisper kurulu degil. Sesli komutlar calismayacak.")
            return False

        if self.model is not None:
            return True  # Zaten yuklenmis — tekrar yukleme

        try:
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                num_workers=1,           # Tek thread, daha az bellek
                cpu_threads=4,           # CPU is parcacigi sayisi
            )
            print(f"Whisper ({self.model_size}) yuklendi [{self.device}/{self.compute_type}].")
            return True
        except Exception as e:
            print(f"Whisper yukleme hatasi: {e}. CPU int8 deneniyor...")
            return self._fallback_to_cpu()

    def _normalize_audio(self, audio_file: str) -> str:
        """Ses dosyasını normalize et — sessiz kayıtlarda Whisper'ı güçlendirir."""
        if not NP_AVAILABLE or not SF_AVAILABLE:
            return audio_file
        try:
            data, sr = sf.read(audio_file, dtype='float32')
            peak = float(np.max(np.abs(data)))
            if peak > 0.01 and peak < 0.7:
                data = data * (0.7 / peak)
                sf.write(audio_file, data, sr)
        except Exception:
            pass
        return audio_file

    def transcribe_file(self, audio_file: str) -> str:
        """Kayitli ses dosyasini metne cevirir."""
        if not self.model:
            if not self.load_model():
                return ""

        audio_file = self._normalize_audio(audio_file)

        kwargs = dict(
            language="tr",
            beam_size=5,
            condition_on_previous_text=False,  # önceki metne bakarak uydurmasın
            no_speech_threshold=0.5,           # sessizliği metin olarak döndürmesin
            compression_ratio_threshold=2.4,   # anlamsız tekrarları filtrele
            vad_filter=True,                   # VAD: sessiz kısımları Whisper öncesi at
            vad_parameters=dict(
                min_silence_duration_ms=300,
                speech_pad_ms=200,
            ),
        )

        try:
            segments, info = self.model.transcribe(audio_file, **kwargs)
            text = " ".join(s.text for s in segments).strip()
            if text:
                print(f"[Whisper] no_speech_prob: {info.all_language_probs.get('tr', '?') if hasattr(info,'all_language_probs') else '?'}")
            return text
        except Exception as e:
            err_str = str(e).lower()
            print(f"Transcribe hatasi: {e}")

            cuda_errors = ["cublas", "cuda", "cudnn", "library", "nvrtc"]
            if any(kw in err_str for kw in cuda_errors) and self.device != "cpu":
                print("CUDA hatasi tespit edildi. CPU moduna geciliyor...")
                if self._fallback_to_cpu():
                    try:
                        segments, info = self.model.transcribe(audio_file, **kwargs)
                        return " ".join(s.text for s in segments).strip()
                    except Exception as e2:
                        print(f"CPU modunda da hata: {e2}")

            # vad_filter için ONNX dosyası bulunamadıysa veya başka hata — VAD'sız tekrar dene
            kwargs.pop("vad_filter", None)
            kwargs.pop("vad_parameters", None)
            try:
                print("[Whisper] VAD'sız tekrar deneniyor...")
                segments, info = self.model.transcribe(audio_file, **kwargs)
                return " ".join(s.text for s in segments).strip()
            except Exception as e3:
                print(f"[Whisper] Fallback hatası: {e3}")
            return ""

    def record_and_transcribe(self, duration: int = 5) -> str:
        """Sabit sureli ses kaydeder ve metne cevirir."""
        dep_error = _check_audio_deps()
        if dep_error:
            print(dep_error)
            return ""

        if not self.load_model():
            return ""

        print(f"Dinleniyor... ({duration}s)")
        try:
            audio_data = sd.rec(
                int(duration * self.samplerate),
                samplerate=self.samplerate,
                channels=1,
                dtype='float32'
            )
            sd.wait()

            # Gecici dosyaya yaz
            temp_dir = tempfile.gettempdir()
            audio_file = os.path.join(temp_dir, "blue_ai_stt.wav")
            sf.write(audio_file, audio_data, self.samplerate)

            text = self.transcribe_file(audio_file)
            if text:
                print(f"Anlasilan: {text}")
            return text

        except Exception as e:
            print(f"Ses kayit hatasi: {e}")
            return ""

    def record_until_silence(self, max_duration: int = 15) -> str:
        """RawInputStream streaming ile ses topla + sessizlik algıla, sonra Whisper ile çözümle.

        Eski chunk-döngüsü (sd.rec + sd.wait per chunk) yerine sürekli akış kullanır.
        Whisper akış sırasında değil, kayıt bittikten sonra tek seferde çalışır.
        """
        dep_error = _check_audio_deps()
        if dep_error:
            print(f"[STT] {dep_error}")
            return ""

        if not self.load_model():
            print("[STT] Model yuklenemedi.")
            return ""

        q: queue.Queue = queue.Queue()
        audio_chunks = []
        speech_detected = False
        silence_start: Optional[float] = None
        noise_floor = self.silence_threshold
        noise_samples: list = []

        def _audio_cb(indata, frames, time_info, status):
            data = np.frombuffer(indata, dtype=np.float32).copy()
            q.put(data)

        print("Dinleniyor... (Konuşun, durduğunuzda otomatik kesilir)")
        try:
            with sd.RawInputStream(
                samplerate=self.samplerate,
                blocksize=int(self.samplerate * 0.1),  # 100ms chunk
                dtype='float32',
                channels=1,
                callback=_audio_cb,
            ):
                start_time = time.time()
                while time.time() - start_time < max_duration:
                    try:
                        chunk = q.get(timeout=0.3)
                    except queue.Empty:
                        if speech_detected and silence_start is not None:
                            if time.time() - silence_start > self.silence_duration:
                                break
                        continue

                    audio_chunks.append(chunk)
                    rms = float(np.sqrt(np.mean(chunk ** 2)))

                    # İlk 0.5s gürültü tabanını öğren
                    if time.time() - start_time < 0.5:
                        noise_samples.append(rms)
                        if noise_samples:
                            noise_floor = max(self.silence_threshold,
                                              float(np.mean(noise_samples)) * 1.8)
                        continue

                    if rms > noise_floor:
                        speech_detected = True
                        silence_start = None
                    elif speech_detected:
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start > self.silence_duration:
                            break

                    # 5 saniye içinde hiç ses yoksa pes et
                    if not speech_detected and time.time() - start_time > 5:
                        print("[STT] Konuşma algılanamadı.")
                        return ""

            if not audio_chunks or not speech_detected:
                return ""

            full_audio = np.concatenate(audio_chunks)
            temp_dir = tempfile.gettempdir()
            audio_file = os.path.join(temp_dir, "blue_ai_stt_continuous.wav")
            sf.write(audio_file, full_audio, self.samplerate)

            text = self.transcribe_file(audio_file)
            if text:
                print(f"[STT] Anlaşılan: {text}")
            return text

        except Exception as e:
            print(f"[STT] Kayıt hatası: {e}")
            return ""

    def start_recording(self):
        """PTT: mikrofon kaydını başlat — sd.InputStream ile doğrudan."""
        if not SD_AVAILABLE or not NP_AVAILABLE or not SF_AVAILABLE:
            print("[STT PTT] Eksik bağımlılık: sounddevice/numpy/soundfile")
            return
        if not self.load_model():
            print("[STT PTT] Model yüklenemedi.")
            return
        if self._recording:
            return

        self._recording = True
        self._recording_chunks = []

        def _cb(indata, frames, time_info, status):
            if status:
                print(f"[STT PTT] Ses durumu: {status}")
            self._recording_chunks.append(indata[:, 0].copy())

        try:
            self._ptt_stream = sd.InputStream(
                samplerate=self.samplerate,
                channels=1,
                dtype='float32',
                blocksize=int(self.samplerate * 0.05),
                callback=_cb,
            )
            self._ptt_stream.start()
            print(f"[STT PTT] Stream başladı. Cihaz: {sd.query_devices(kind='input')['name']}")
        except Exception as e:
            print(f"[STT PTT] Stream açma hatası: {e}")
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
                print(f"[STT PTT] Stream kapatma hatası: {e}")
            self._ptt_stream = None

        chunks = self._recording_chunks[:]
        self._recording_chunks = []

        print(f"[STT PTT] Toplanan chunk sayısı: {len(chunks)}")

        if not chunks:
            print("[STT PTT] Ses kaydı boş — stream açılamamış olabilir.")
            return ""

        full_audio = np.concatenate(chunks)
        duration = len(full_audio) / self.samplerate
        print(f"[STT PTT] Kayıt süresi: {duration:.2f}s, örnek sayısı: {len(full_audio)}")

        if duration < 0.15:
            print("[STT PTT] Kayıt çok kısa.")
            return ""

        temp_dir = tempfile.gettempdir()
        audio_file = os.path.join(temp_dir, "blue_ai_ptt.wav")
        sf.write(audio_file, full_audio, self.samplerate)

        text = self.transcribe_file(audio_file)
        if text:
            print(f"[STT PTT] Anlaşılan: {text}")
        else:
            print("[STT PTT] Whisper boş döndü.")
        return text

    def start_listening(self, on_result: Callable[[str], None] = None):
        """Surekli dinleme modunu baslat (arka plan thread)."""
        if self._is_listening:
            return

        dep_error = _check_audio_deps()
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
                    print(f"[STT] {text}")
                # Kısa bekleme
                time.sleep(0.3)

            self._is_listening = False

        self._listen_thread = threading.Thread(target=_listen_loop, daemon=True)
        self._listen_thread.start()

    def stop_listening(self):
        """Surekli dinleme modunu durdur."""
        self._stop_event.set()
        self._is_listening = False

    @property
    def is_listening(self) -> bool:
        return self._is_listening


# Singleton instance
_stt: Optional[STTEngine] = None

def get_stt(engine: str = "") -> "STTEngine | VoskSTTEngine":
    """Config'den ayarları okuyarak STT motorunu başlatır (singleton).
    
    Args:
        engine: "whisper" veya "vosk". Boş bırakılırsa config'den okunur.
    
    Returns:
        STTEngine (Whisper) veya VoskSTTEngine (Vosk)
    """
    global _stt
    if _stt is not None:
        return _stt

    model_size = "small"
    device = "cpu"
    compute_type = "int8"
    stt_engine = engine or "whisper"
    vosk_model_path = ""
    vosk_model_size = "small"

    # Config dosyasından oku
    try:
        import os
        cfg_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "config", "blue_ai.toml"
        )
        if os.path.exists(cfg_path):
            try:
                import toml
                cfg = toml.load(cfg_path)
            except ImportError:
                # toml yoksa basit parser
                cfg = {}
                with open(cfg_path, "r", encoding="utf-8") as f:
                    in_voice = False
                    for line in f:
                        line = line.strip()
                        if line == "[voice]":
                            in_voice = True
                        elif line.startswith("[") and line != "[voice]":
                            in_voice = False
                        elif in_voice and "=" in line:
                            k, v = line.split("=", 1)
                            cfg.setdefault("voice", {})[k.strip()] = v.split("#")[0].strip().strip('"')

            voice_cfg = cfg.get("voice", {})
            if not engine:  # Parametre verilmediyse config'den oku
                stt_engine = voice_cfg.get("stt_engine", stt_engine)
            model_size     = voice_cfg.get("stt_model", model_size)
            device         = voice_cfg.get("stt_device", device)
            compute_type   = voice_cfg.get("stt_compute", compute_type)
            vosk_model_path = voice_cfg.get("vosk_model_path", vosk_model_path)
            vosk_model_size = voice_cfg.get("vosk_model_size", vosk_model_size)
    except Exception as e:
        print(f"[STT] Config okunamadi, varsayilan kullaniliyor: {e}")

    # Motor seçimi
    if stt_engine == "vosk":
        try:
            from blue_ai.voice.stt_vosk import VoskSTTEngine
            _stt = VoskSTTEngine(model_path=vosk_model_path, model_size=vosk_model_size)
            print(f"[STT] Motor: Vosk (model: {vosk_model_size})")
        except ImportError:
            print("[STT] Vosk import hatası, Whisper'a düşülüyor...")
            _stt = STTEngine(model_size=model_size, device=device, compute_type=compute_type)
    else:
        _stt = STTEngine(model_size=model_size, device=device, compute_type=compute_type)
        print(f"[STT] Motor: Whisper (model: {model_size}, device: {device})")

    return _stt

