"""
BLUE_AI — Text to Speech (TTS) Modülü

Online: Edge TTS (Microsoft'un ücretsiz, yuksek kaliteli TTS hizmeti)
Offline Fallback: pyttsx3 (Windows SAPI5)
"""

import os
import tempfile
import asyncio
import subprocess
import threading
from typing import Optional


try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

try:
    import pygame
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except Exception:
    PYGAME_AVAILABLE = False


class TTSEngine:
    """Metni sese ceviren motor."""

    def __init__(self, voice: str = "tr-TR-AhmetNeural", use_edge: bool = True):
        self.voice = voice
        self.use_edge = use_edge and EDGE_TTS_AVAILABLE
        self._is_speaking = False
        self._stop_event = threading.Event()
        self._current_process: Optional[subprocess.Popen] = None

        # Offline motor hazirla (pyttsx3)
        self.offline_engine = None
        if PYTTSX3_AVAILABLE:
            try:
                self.offline_engine = pyttsx3.init()
                # Turkce sesi bul
                voices = self.offline_engine.getProperty('voices')
                for v in voices:
                    # pyttsx3 v.languages bazen bytes listesi dondurur
                    lang_match = False
                    if hasattr(v, 'languages'):
                        for lang in v.languages:
                            lang_str = lang.decode() if isinstance(lang, bytes) else str(lang)
                            if "tr" in lang_str.lower():
                                lang_match = True
                                break
                    if "Turkish" in v.name or "Türk" in v.name or lang_match:
                        self.offline_engine.setProperty('voice', v.id)
                        break

                self.offline_engine.setProperty('rate', 160)
                self.offline_engine.setProperty('volume', 0.9)
            except Exception as e:
                print(f"pyttsx3 baslatma hatasi: {e}")
                self.offline_engine = None

    async def _speak_edge(self, text: str) -> bool:
        """Edge TTS ile seslendir (Online)."""
        temp_dir = tempfile.gettempdir()
        output_file = os.path.join(temp_dir, "blue_ai_speak.mp3")

        try:
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(output_file)

            if self._stop_event.is_set():
                return False

            self._is_speaking = True

            # pygame varsa çok daha hızlı (process başlatma overhead'i yok)
            if PYGAME_AVAILABLE:
                try:
                    pygame.mixer.music.load(output_file)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        if self._stop_event.is_set():
                            pygame.mixer.music.stop()
                            break
                        import time; time.sleep(0.05)
                    self._is_speaking = False
                    return True
                except Exception as pe:
                    print(f"[TTS] pygame hatası, PowerShell'e düşüyor: {pe}")

            # PowerShell fallback — optimize edilmiş (500ms sleep kaldırıldı)
            ps_script = (
                f'Add-Type -AssemblyName PresentationCore; '
                f'$p = New-Object System.Windows.Media.MediaPlayer; '
                f'$p.Open([Uri]"{output_file}"); '
                f'$p.Play(); '
                f'$t = [Diagnostics.Stopwatch]::StartNew(); '
                f'while($t.Elapsed.TotalSeconds -lt 0.8) {{ Start-Sleep -ms 50 }}; '
                f'while(-not $p.NaturalDuration.HasTimeSpan -and $t.Elapsed.TotalSeconds -lt 3) {{ Start-Sleep -ms 50 }}; '
                f'if($p.NaturalDuration.HasTimeSpan) {{ '
                f'  $rem = $p.NaturalDuration.TimeSpan.TotalMilliseconds - $p.Position.TotalMilliseconds; '
                f'  if($rem -gt 0) {{ Start-Sleep -ms ([int]$rem + 200) }} '
                f'}}; '
                f'$p.Close()'
            )
            self._current_process = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._current_process.wait(timeout=30)
            self._current_process = None
            self._is_speaking = False
            return True

        except subprocess.TimeoutExpired:
            if self._current_process:
                self._current_process.kill()
                self._current_process = None
            self._is_speaking = False
            return True
        except Exception as e:
            print(f"Edge TTS hatasi: {e}")
            self._is_speaking = False
            self._current_process = None
            return False

    def _speak_offline(self, text: str):
        """pyttsx3 ile seslendir (Offline fallback)."""
        if not self.offline_engine:
            print("Offline TTS motoru kulanilamiyor.")
            return

        try:
            self._is_speaking = True
            self.offline_engine.say(text)
            self.offline_engine.runAndWait()
            self._is_speaking = False
        except RuntimeError:
            # pyttsx3 bazen "run loop already started" hatasi verir
            try:
                self.offline_engine.endLoop()
                self.offline_engine.say(text)
                self.offline_engine.runAndWait()
            except Exception:
                pass
            self._is_speaking = False
        except Exception as e:
            print(f"Offline TTS hatasi: {e}")
            self._is_speaking = False

    def speak(self, text: str):
        """Metni sese cevir ve dinlet."""
        if not text or not text.strip():
            return

        # Onceki konusmayi durdur
        self.stop()
        self._stop_event.clear()

        def _run():
            # Edge TTS calisirsa tamam, basarisiz olursa offline a dus
            success = False
            if self.use_edge:
                try:
                    # Thread icinde yeni event loop olustur (asyncio.run thread-safe degil)
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        success = loop.run_until_complete(self._speak_edge(text))
                    finally:
                        loop.close()
                except Exception as e:
                    print(f"Edge TTS thread hatasi: {e}")

            if not success and not self._stop_event.is_set():
                self._speak_offline(text)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def stop(self):
        """Konusmayi durdur."""
        self._stop_event.set()
        if self._current_process and self._current_process.poll() is None:
            try:
                self._current_process.kill()
            except Exception:
                pass
            self._current_process = None
        if self.offline_engine:
            try:
                self.offline_engine.stop()
            except Exception:
                pass
        self._is_speaking = False

    def is_speaking(self) -> bool:
        """Seslendirme devam ediyor mu?"""
        return self._is_speaking


# Singleton instance
_tts: Optional[TTSEngine] = None

def get_tts() -> TTSEngine:
    global _tts
    if _tts is None:
        _tts = TTSEngine()
    return _tts
