"""
BLUE_AI Native Desktop Application

PyWebView ile native masaustu uygulamasi.
Tek pencerede: Dashboard + Chat + Tum moduller.
"""

import webview
import psutil
import time
import json
import threading
import subprocess
import os
import sys

# Proje kokunu path'e ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blue_ai.utils.helpers import bytes_to_human, seconds_to_human
from blue_ai.utils.win_api import get_system_power_status, set_power_scheme
from blue_ai.core.config import load_config, get_profile


class BlueAIBackend:
    """PyWebView JS-Python koprusu."""

    def __init__(self):
        self._config = load_config()
        self._current_profile = "balanced"
        self._brain = None          # Lazy + prewarm
        self._voice_enabled = None  # Cache — her seferinde dosya okuma yok
        self._window = None         # webview penceresi (push icin)

        # Arka planda modelleri yükle (kullanıcı ilk komutu verene hazır olsun)
        threading.Thread(target=self._prewarm, daemon=True, name="prewarm").start()

    def _prewarm(self):
        """Brain, ML model, LLM ve STT'yi arka planda önceden yükle."""
        try:
            from blue_ai.brain.brain import get_brain
            self._brain = get_brain()
            self._brain.initialize()           # Tool registry (hizli, 3ms)
            # ML modeli ayri thread'de yukle — prewarm'u 17s bloklamasin
            self._brain._load_ml_model_bg()
            print("[Prewarm] Brain hazir, ML model arka planda yukleniyor.")
        except Exception as e:
            print(f"[Prewarm] Brain hatasi: {e}")

        # LLM'i GPU'ya yukle (cold start'i onle) — uzun timeout ile
        try:
            from blue_ai.ai.llm import get_llm, reset_llm_model
            reset_llm_model()  # Kurulu modelleri yeniden tara
            llm = get_llm()
            if llm.is_available():
                llm.warmup()
                print(f"[Prewarm] LLM hazir: {llm._active_model}")
            else:
                print("[Prewarm] Ollama calismiyor -- LLM atlandi.")
        except Exception as e:
            print(f"[Prewarm] LLM hatasi: {e}")

        # TTS'i onceden import et — ilk mesajda 7s beklemeyi onle
        try:
            from blue_ai.voice.tts import get_tts
            get_tts()
            print("[Prewarm] TTS hazir.")
        except Exception as e:
            print(f"[Prewarm] TTS hatasi: {e}")

        try:
            from blue_ai.voice.stt import get_stt
            stt = get_stt()
            stt.load_model()  # Secili STT motorunu yukle (Whisper veya Vosk)
            engine_name = type(stt).__name__
            print(f"[Prewarm] STT ({engine_name}) hazir.")
        except Exception as e:
            print(f"[Prewarm] STT hatasi: {e}")


    def _get_brain(self):
        """Brain singleton — prewarm tamamlanmamışsa senkron yükle."""
        if self._brain is None:
            from blue_ai.brain.brain import get_brain
            self._brain = get_brain()
        return self._brain

    def _is_voice_enabled(self) -> bool:
        """Ses ayarını cache'den döndür."""
        if self._voice_enabled is None:
            try:
                config_path = os.path.join(
                    os.path.dirname(__file__), "..", "config", "blue_ai.toml"
                )
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    # [voice] bölümünde enabled = true/false bak
                    in_voice = False
                    for line in content.splitlines():
                        stripped = line.strip()
                        if stripped == '[voice]':
                            in_voice = True
                        elif stripped.startswith('[') and stripped != '[voice]':
                            in_voice = False
                        elif in_voice and stripped.startswith('enabled'):
                            self._voice_enabled = 'true' in stripped.lower()
                            break
                    if self._voice_enabled is None:
                        self._voice_enabled = False
                else:
                    self._voice_enabled = False
            except Exception:
                self._voice_enabled = False
        return self._voice_enabled


    # =================== SYSTEM ===================

    def get_system_data(self):
        """Sistem metrikleri."""
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_per_core = psutil.cpu_percent(percpu=True)
        cpu_freq = psutil.cpu_freq()
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        power = get_system_power_status()
        boot_time = time.time() - psutil.boot_time()

        return json.dumps({
            "cpu": {
                "percent": cpu_percent,
                "per_core": cpu_per_core,
                "freq": cpu_freq.current if cpu_freq else 0,
                "cores": psutil.cpu_count(),
            },
            "ram": {
                "percent": ram.percent,
                "used": bytes_to_human(ram.used),
                "total": bytes_to_human(ram.total),
                "available": bytes_to_human(ram.available),
                "used_bytes": ram.used,
                "total_bytes": ram.total,
            },
            "disk": {
                "percent": disk.percent,
                "used": bytes_to_human(disk.used),
                "total": bytes_to_human(disk.total),
                "free": bytes_to_human(disk.free),
            },
            "power": power,
            "uptime": seconds_to_human(boot_time),
            "profile": self._current_profile,
        })

    # =================== PROCESSES ===================

    def get_processes(self):
        """Surec listesi."""
        procs = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "status"]):
            try:
                info = proc.info
                mem = info.get("memory_info")
                procs.append({
                    "pid": info["pid"],
                    "name": info["name"] or "Unknown",
                    "cpu": round(info.get("cpu_percent", 0) or 0, 1),
                    "ram": bytes_to_human(mem.rss) if mem else "0 B",
                    "ram_bytes": mem.rss if mem else 0,
                    "status": info.get("status", ""),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda p: p["cpu"], reverse=True)
        return json.dumps(procs[:50])

    def kill_process(self, pid):
        """Sureci sonlandir."""
        try:
            p = psutil.Process(int(pid))
            p.terminate()
            return json.dumps({"success": True, "message": f"PID {pid} sonlandirildi."})
        except Exception as e:
            return json.dumps({"success": False, "message": str(e)})

    # =================== DISKS ===================

    def get_disks(self):
        """Disk bilgileri."""
        disks = []
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "percent": usage.percent,
                    "used": bytes_to_human(usage.used),
                    "total": bytes_to_human(usage.total),
                    "free": bytes_to_human(usage.free),
                })
            except (PermissionError, OSError):
                continue
        return json.dumps(disks)

    # =================== NETWORK ===================

    def get_network(self):
        """Ag verileri."""
        try:
            c = psutil.net_io_counters()
            conns = psutil.net_connections(kind='inet')
            return json.dumps({
                "bytes_sent": bytes_to_human(c.bytes_sent),
                "bytes_recv": bytes_to_human(c.bytes_recv),
                "packets_sent": c.packets_sent,
                "packets_recv": c.packets_recv,
                "connections": len(conns),
            })
        except Exception:
            return json.dumps({})

    # =================== PROFILE ===================

    def set_profile(self, name):
        """Profil degistir."""
        try:
            profile = get_profile(name)
            if profile:
                power_plan = profile.get("power_plan", "balanced")
                set_power_scheme(power_plan)
                self._current_profile = name
                return json.dumps({"success": True, "profile": name})
            return json.dumps({"success": False})
        except Exception as e:
            return json.dumps({"success": False, "message": str(e)})

    # =================== CHAT / COMMAND ===================

    def confirm_action(self, tool_name, approved):
        """Onay bekleyen islemi onayla/reddet."""
        try:
            from blue_ai.brain.brain import get_brain
            if not hasattr(self, '_brain'):
                self._brain = get_brain()
            result = self._brain.process_confirmation(tool_name, approved)
            return json.dumps(result.to_dict(), ensure_ascii=False)
        except Exception as e:
            return json.dumps({"response": f"Hata: {str(e)}", "type": "error"})

    def get_llm_status(self):
        """LLM bağlantı durumu — cache temizleyip yeniden sorgular, yeni modeli yakalar."""
        try:
            from blue_ai.ai.llm import get_llm, reset_llm_model
            reset_llm_model()
            llm = get_llm()
            info = llm.get_model_info()
            return json.dumps(info, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"available": False, "error": str(e)})

    # ── Canlı ekran izleme ───────────────────────────────────────────────────
    def screen_watch_start(self):
        """Canlı ekran izlemeyi başlat (arka planda yakalar)."""
        try:
            from blue_ai.tools.screen import get_watcher
            started = get_watcher().start()
            return json.dumps({"status": "started" if started else "already", "active": True})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e), "active": False})

    def screen_watch_stop(self):
        """Canlı ekran izlemeyi durdur."""
        try:
            from blue_ai.tools.screen import get_watcher
            get_watcher().stop()
            return json.dumps({"status": "stopped", "active": False})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def get_screen_frame(self):
        """En son canlı ekran karesini döndür (UI periyodik olarak çeker)."""
        try:
            from blue_ai.tools.screen import get_watcher
            return json.dumps(get_watcher().latest_frame(), ensure_ascii=False)
        except Exception as e:
            return json.dumps({"active": False, "frame": None, "error": str(e)})

    def listen_voice(self):
        """Mikrofon kaydını başlat — async (JS callback ile sonuç gönderir).

        Hemen 'recording' döner, arka planda kayıt + STT + Brain çalışır,
        bitince window.receiveVoiceResult(data) JS fonksiyonu çağrılır.
        """
        if not self._window:
            # Fallback: senkron mod
            return self._listen_voice_sync()

        def _worker():
            result = self._listen_voice_sync()
            try:
                # JS'e push et
                import json as _json
                safe = result.replace('`', "'").replace('\\', '\\\\')
                self._window.evaluate_js(f'receiveVoiceResult(`{safe}`)')
            except Exception as ex:
                print(f"[Voice] JS push hatasi: {ex}")

        threading.Thread(target=_worker, daemon=True, name="voice_worker").start()
        return json.dumps({"status": "recording"})

    def _listen_voice_sync(self) -> str:
        """Ses kaydet + STT + Brain — bloklayan senkron iş."""
        try:
            from blue_ai.voice.stt import get_stt
            stt = get_stt()

            text = stt.record_until_silence(max_duration=10)
            # NOT: 5 saniyelik fallback KALDIRILDI — çok yavaştı

            if not text:
                return json.dumps({
                    "response": "Ses algılanamadı. Mikrofona yakın konuşun.",
                    "type": "warning"
                })

            brain = self._get_brain()
            result = brain.process(text)
            self._speak_if_enabled(result.message)

            return json.dumps({
                "recognized_text": text,
                "response": result.message,
                "type": result.response_type,
                "tool_calls": result.tool_calls if hasattr(result, 'tool_calls') else [],
                "pending_confirmation": (
                    result.pending_confirmation
                    if hasattr(result, 'pending_confirmation') else None
                )
            }, ensure_ascii=False)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return json.dumps({"response": f"Ses sistemi hatası: {str(e)}", "type": "error"})


    def start_voice_ptt(self) -> str:
        """PTT: kaydı başlat (non-blocking)."""
        try:
            from blue_ai.voice.stt import get_stt
            stt = get_stt()
            stt.start_recording()
            return json.dumps({"status": "ok"})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def stop_voice_ptt(self) -> str:
        """PTT: kaydı durdur, tanı ve işle — async (sonuç JS'e push edilir)."""
        if not self._window:
            return self._stop_voice_ptt_sync()

        def _worker():
            result = self._stop_voice_ptt_sync()
            try:
                safe = result.replace('`', "'").replace('\\', '\\\\')
                self._window.evaluate_js(f'receiveVoiceResult(`{safe}`)')
            except Exception as ex:
                print(f"[PTT] JS push hatası: {ex}")

        threading.Thread(target=_worker, daemon=True, name="ptt_worker").start()
        return json.dumps({"status": "processing"})

    def _stop_voice_ptt_sync(self) -> str:
        """PTT: kaydı durdur, tanı, Brain'e gönder."""
        try:
            from blue_ai.voice.stt import get_stt
            stt = get_stt()
            text = stt.stop_and_transcribe()

            if not text:
                return json.dumps({"response": "Ses algılanamadı. Boşluk tuşunu basılı tutarken konuşun.", "type": "warning"})

            brain = self._get_brain()
            result = brain.process(text)
            self._speak_if_enabled(result.message)

            return json.dumps({
                "recognized_text": text,
                "response": result.message,
                "type": result.response_type,
                "tool_calls": result.tool_calls if hasattr(result, 'tool_calls') else [],
                "pending_confirmation": (
                    result.pending_confirmation
                    if hasattr(result, 'pending_confirmation') else None
                )
            }, ensure_ascii=False)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return json.dumps({"response": f"PTT hatası: {str(e)}", "type": "error"})

    def _speak_if_enabled(self, text: str):
        """TTS — tamamen arka plan thread'de, HİÇBİR ZAMAN BLOKLAMAz."""
        if not text:
            return
        def _tts_worker():
            try:
                if not self._is_voice_enabled():
                    return
                from blue_ai.brain.response_formatter import ResponseFormatter
                from blue_ai.voice.tts import get_tts
                short_text = ResponseFormatter.format_for_voice(text)
                if short_text:
                    get_tts().speak(short_text)
            except Exception as e:
                print(f"[TTS] Hata: {e}")
        threading.Thread(target=_tts_worker, daemon=True, name="tts_speak").start()

    def _extract_tool_params(self, intent: str, message: str) -> dict:
        """Mesajdan tool parametrelerini çıkar (ses seviyesi, STT motoru vb.)."""
        import re
        params = {}

        # Ekran müdahale + not defteri tool'ları → Brain'in akıllı çıkarımını kullan.
        # start_chat_stream (yazılı chat) bu yoldan geçer; bu tool'lar aksi halde
        # parametresiz çağrılıp "metin/hedef boş" hatası verir (PC'ye müdahale etmez).
        if intent in ("type_on_screen", "click_on_screen", "press_keys",
                      "scroll_screen", "watch_screen", "write_to_notepad",
                      "open_app", "close_app"):
            try:
                return self._get_brain()._extract_fast_path_args(intent, message)
            except Exception:
                return {}

        if intent == "change_volume":
            # "sesi %20 yap", "ses 50", "volume 75", "sesi 20ye ayarla" gibi
            nums = re.findall(r'\d+', message)
            if nums:
                level = max(0, min(100, int(nums[0])))
                params["level"] = level
            else:
                # Sözel komutlar: aç/yükselt → 80, kapat/düşür → 20, sustur → 0
                msg_lower = message.lower()
                if any(w in msg_lower for w in ["sustur", "mute", "kapat", "sıfır"]):
                    params["level"] = 0
                elif any(w in msg_lower for w in ["düşür", "azalt", "dusur", "azalt"]):
                    params["level"] = 20
                elif any(w in msg_lower for w in ["yükselt", "artır", "aç", "yukselt", "artir"]):
                    params["level"] = 80
                else:
                    params["level"] = 50  # varsayılan

        elif intent == "switch_stt_engine":
            msg_lower = message.lower()
            if "whisper" in msg_lower:
                params["engine"] = "whisper"
            elif "vosk" in msg_lower:
                params["engine"] = "vosk"
            else:
                try:
                    import os
                    cfg_path = os.path.join(
                        os.path.dirname(__file__), "..", "config", "blue_ai.toml"
                    )
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if "stt_engine" in line and "=" in line:
                                current = line.split("=")[1].split("#")[0].strip().strip('"')
                                params["engine"] = "whisper" if current == "vosk" else "vosk"
                                break
                except Exception:
                    params["engine"] = "vosk"

        elif intent == "open_app":
            # Mesajdan uygulama adını çıkar
            # Önce gereksiz kelimeleri normalize et
            msg_n = message.lower()
            # Türkçe normalize
            for old, new in [("ş","s"),("ı","i"),("ğ","g"),("ü","u"),("ö","o"),("ç","c")]:
                msg_n = msg_n.replace(old, new)

            # "X uygulaması/üzerinden" gibi yapıda: X'i bul
            trigger_words = [
                "uygulamasini", "uygulamasiyla", "uygulamasinda", "uzerinden",
                "programini", "programiyla", "uygulamasi",
            ]
            skip_prewords = {
                "interneti", "internete", "webi", "siteyi", "agi", "neti",
                "bilgisayardaki", "lutfen", "bana", "bir", "ile", "ve", "da", "de",
                "uygulamasi", "uygulamasini", "uygulamasiyla", "programi", "programini",
                "uzerinden", "kullanarak", "ile",
            }
            for trigger in trigger_words:
                idx = msg_n.find(trigger)
                if idx > 0:
                    before_words = msg_n[:idx].split()
                    candidates = [w for w in before_words
                                  if w not in skip_prewords and len(w) > 1]
                    if candidates:
                        params["app_name"] = candidates[-1]  # Trigger'dan önceki son kelime
                        break

            # Bulunamadıysa "aç X" / "X'i aç" gibi
            if "app_name" not in params:
                import re
                skip_words = {
                    "ac", "aci", "acilsin", "bashlat", "calistir", "lütfen", "lutfen",
                    "uygulamasi", "programi", "benim", "misin", "mısın", "uzerinden", "ve",
                    "interneti", "internete", "webi", "bilgisayardaki",
                }
                words = [w for w in msg_n.split() if w not in skip_words and len(w) > 2]
                if words:
                    params["app_name"] = words[0]

        elif intent == "get_weather":
            # Brain'in akıllı city extraction'ını kullan
            try:
                brain = self._get_brain()
                params["city"] = brain._extract_city_from_message(message)
            except Exception:
                # Fallback: basit kelime çıkarımı
                msg_lower = message.lower()
                skip_weather = {
                    "hava", "durumu", "weather", "nasıl", "nasil",
                    "bugün", "bugun", "yarın", "yarin", "sıcaklık", "sicaklik",
                    "kaç", "kac", "derece", "celsius", "nedir", "ne", "var",
                    "olan", "için", "icin",
                }
                loc_suffixes = ["'nda", "'nde", "'da", "'de", "'ta", "'te",
                                "nda", "nde", "da", "de", "ta", "te"]
                words_raw = msg_lower.split()
                clean_words = []
                for w in words_raw:
                    c = w.strip("'\",.!?")
                    for suf in loc_suffixes:
                        if c.endswith(suf) and len(c) > len(suf) + 2:
                            c = c[: -len(suf)]
                            break
                    c = c.strip("'\"")
                    if c and c not in skip_weather and len(c) > 2:
                        clean_words.append(c)
                params["city"] = clean_words[0].capitalize() if clean_words else "Istanbul"

        return params


    def process_chat(self, message):
        """Chat mesajını işle — Brain üzerinden AI destekli (sync fallback)."""
        try:
            brain = self._get_brain()
            result = brain.process(message)
            self._speak_if_enabled(result.message)
            return json.dumps(result.to_dict(), ensure_ascii=False)
        except Exception as e:
            import traceback; traceback.print_exc()
            return json.dumps({"response": f"Hata: {str(e)}", "type": "error"})

    def start_chat_stream(self, message: str) -> str:
        """Hızlı chat — selamlama/sistem komutu anında döner, LLM arka planda stream eder."""
        import base64

        brain = self._get_brain()
        brain.initialize()

        # ── 1. SELAMLAMAlar → 0ms, senkron, thread yok ──────────────────────
        brain._context.auto_detect_and_set_language(message)
        greeting = brain._try_greeting(message)
        if greeting:
            brain._context.add_user_message(message)
            brain._context.add_assistant_message(greeting.message)
            self._speak_if_enabled(greeting.message)
            return json.dumps({
                "status": "done",
                "response": greeting.message,
                "type": greeting.response_type
            }, ensure_ascii=False)

        # ── 2. BELLEK KAYDET/SORGULA → anında, LLM yok ──────────────────────
        mem_resp = brain._try_memory_operation(message)
        if mem_resp is not None:
            brain._context.add_user_message(message)
            brain._context.add_assistant_message(mem_resp.message)
            self._speak_if_enabled(mem_resp.message)
            return json.dumps({
                "status": "done",
                "response": mem_resp.message,
                "type": mem_resp.response_type
            }, ensure_ascii=False)

        # ── 3. SİSTEM KOMUTLARI → ~50-200ms, senkron, thread yok ────────────
        intent = brain._detect_intent_fast(message)
        if intent:
            tool = brain._registry.get(intent)
            if tool and tool.permission_level.value < 3:
                brain._context.add_user_message(message)
                # Parametre gerektiren tool'lar için mesajdan değer çıkar
                tool_kwargs = self._extract_tool_params(intent, message)
                result = brain._registry.execute_tool(intent, **tool_kwargs)
                msg = result.message or result.to_llm_context()
                brain._context.add_assistant_message(msg)
                brain._process_memory(message, msg)
                self._speak_if_enabled(msg)
                return json.dumps({
                    "status": "done",
                    "response": msg,
                    "type": "success" if result.success else "error"
                }, ensure_ascii=False)

        # ── 3. LLM GEREKLİ → arka plan thread + streaming ───────────────────
        brain._context.add_user_message(message)

        if not self._window:
            result = brain._run_llm_loop(message)
            brain._context.add_assistant_message(result.message)
            return json.dumps(result.to_dict(), ensure_ascii=False)

        def _llm_worker():
            try:
                llm = brain._get_llm() if hasattr(brain, '_get_llm') else None
                # get_llm from module
                from blue_ai.ai.llm import get_llm
                llm = get_llm()

                if not llm.is_available():
                    resp = brain._handle_without_llm(message)
                    brain._context.add_assistant_message(resp.message)
                    payload = json.dumps({"type": "final", "text": resp.message,
                                          "response_type": resp.response_type})
                    b64 = base64.b64encode(payload.encode('ascii')).decode()
                    self._window.evaluate_js(f'finishChatStreamB64("{b64}")')
                    return

                messages = brain._context.build_messages()
                full_text = ""
                buf = ""
                import time
                last_flush = time.time()

                for chunk in llm.chat_stream(messages, temperature=0.1):
                    if chunk:
                        full_text += chunk
                        buf += chunk
                        now = time.time()
                        # Her 80ms'de bir veya 20 karakterde bir flush
                        if len(buf) >= 20 or (now - last_flush) >= 0.08:
                            self._window.evaluate_js(f'appendChatChunk({json.dumps(buf)})')
                            buf = ""
                            last_flush = now

                # Kalan buffer'ı flush et
                if buf:
                    self._window.evaluate_js(f'appendChatChunk({json.dumps(buf)})')

                # Tool call kontrolü
                tool_call = brain._extract_tool_call(full_text)
                if tool_call:
                    tool_name = tool_call.get("name", "")
                    tool_args = tool_call.get("arguments", {})
                    tool = brain._registry.get(tool_name)
                    if tool and tool.permission_level.value < 3:
                        result = brain._registry.execute_tool(tool_name, **tool_args)
                        brain._context.add_tool_result(tool_name, result.to_llm_context())
                        messages2 = brain._context.build_messages()
                        final_text = llm.chat(messages2, temperature=0.1)
                        final_text = brain._clean_response(final_text, has_tools=True)
                        brain._context.add_assistant_message(final_text)
                        payload = json.dumps({"type": "final", "text": final_text,
                                              "response_type": "success"})
                        b64 = base64.b64encode(payload.encode('ascii')).decode()
                        self._window.evaluate_js(f'finishChatStreamB64("{b64}")')
                        self._speak_if_enabled(final_text)
                        return

                clean = brain._clean_response(full_text)
                brain._context.add_assistant_message(clean)
                brain._process_memory(message, clean)
                payload = json.dumps({"type": "final", "text": clean,
                                      "response_type": "info"})
                b64 = base64.b64encode(payload.encode('ascii')).decode()
                self._window.evaluate_js(f'finishChatStreamB64("{b64}")')
                self._speak_if_enabled(clean)

            except Exception as e:
                import traceback
                traceback.print_exc()
                err_payload = json.dumps({"type": "final",
                                          "text": f"Hata: {str(e)}",
                                          "response_type": "error"})
                b64 = base64.b64encode(err_payload.encode('ascii')).decode()
                try:
                    self._window.evaluate_js(f'finishChatStreamB64("{b64}")')
                except Exception:
                    pass

        threading.Thread(target=_llm_worker, daemon=True, name="llm_stream").start()
        return json.dumps({"status": "streaming"})

def get_html():
    """Ana uygulama HTML'ini dondur."""
    return r'''<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BLUE AI</title>
<style>
:root {
    --bg-primary: #080c14;
    --bg-secondary: #0d1526;
    --bg-card: rgba(13, 21, 38, 0.6);
    --accent-blue: #3b82f6;
    --accent-cyan: #22d3ee;
    --accent-green: #10b981;
    --accent-yellow: #f59e0b;
    --accent-red: #ef4444;
    --accent-purple: #a78bfa;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-dim: #475569;
    --border: rgba(255, 255, 255, 0.06);
    --user-bubble: linear-gradient(135deg, #3b4fd8, #6d28d9);
    --ai-bubble: rgba(15, 23, 42, 0.7);
}

/* ─── Global Reset ─── */
* { margin: 0; padding: 0; box-sizing: border-box; }

html, body {
    height: 100vh; width: 100vw; overflow: hidden;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
}

/* ─── Animated background glows ─── */
body::before {
    content: '';
    position: fixed; inset: 0; pointer-events: none; z-index: 0;
    background:
        radial-gradient(ellipse 60% 40% at 20% 60%, rgba(59,130,246,0.07) 0%, transparent 70%),
        radial-gradient(ellipse 50% 40% at 80% 20%, rgba(139,92,246,0.07) 0%, transparent 70%),
        radial-gradient(ellipse 40% 30% at 60% 90%, rgba(34,211,238,0.04) 0%, transparent 60%);
    animation: bgPulse 12s ease-in-out infinite alternate;
}
@keyframes bgPulse {
    0%   { opacity: 0.7; transform: scale(1);    }
    100% { opacity: 1.0; transform: scale(1.06); }
}

/* ─── App shell ─── */
#app {
    position: relative; z-index: 1;
    display: flex; flex-direction: column;
    height: 100vh;
}

/* ─── Header ─── */
.header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0.9rem 1.6rem;
    background: rgba(8,12,20,0.75);
    backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
    border-bottom: 1px solid var(--border);
    -webkit-app-region: drag;
    flex-shrink: 0;
}
.header-brand { display: flex; align-items: center; gap: 0.75rem; }
.brand-orb {
    position: relative; width: 36px; height: 36px;
    border-radius: 50%;
    background: linear-gradient(135deg, #3b82f6, #8b5cf6);
    box-shadow: 0 0 20px rgba(59,130,246,0.5), 0 0 40px rgba(139,92,246,0.2);
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem;
    animation: orbPulse 3s ease-in-out infinite;
}
@keyframes orbPulse {
    0%,100% { box-shadow: 0 0 20px rgba(59,130,246,0.5), 0 0 40px rgba(139,92,246,0.2); }
    50%      { box-shadow: 0 0 30px rgba(59,130,246,0.7), 0 0 60px rgba(139,92,246,0.35); }
}
.brand-title {
    font-size: 1.15rem; font-weight: 700; letter-spacing: 1.5px;
    background: linear-gradient(120deg, #60a5fa 0%, #c084fc 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.brand-sub {
    font-size: 0.7rem; color: var(--text-dim); letter-spacing: 0.5px; margin-top: 1px;
}
.header-right {
    display: flex; align-items: center; gap: 0.75rem;
    -webkit-app-region: no-drag;
}
.status-pill {
    display: flex; align-items: center; gap: 0.4rem;
    padding: 0.3rem 0.75rem; border-radius: 999px;
    font-size: 0.72rem; font-weight: 500; letter-spacing: 0.3px;
    border: 1px solid; backdrop-filter: blur(8px);
    transition: all 0.3s;
}
.status-pill.online {
    color: #34d399; border-color: rgba(52,211,153,0.25);
    background: rgba(16,185,129,0.06);
}
.status-pill.offline {
    color: #f87171; border-color: rgba(248,113,113,0.25);
    background: rgba(239,68,68,0.06);
}
.status-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: currentColor;
    box-shadow: 0 0 6px currentColor;
    animation: dotBlink 2s ease-in-out infinite;
}
@keyframes dotBlink { 0%,100%{opacity:1} 50%{opacity:0.4} }

/* ─── Chat area ─── */
.chat-wrap {
    flex: 1; display: flex; flex-direction: column;
    overflow: hidden; position: relative;
    max-width: 860px; width: 100%; margin: 0 auto;
    padding: 0 1rem;
}

.chat-messages {
    flex: 1; overflow-y: auto; overflow-x: hidden;
    padding: 1.5rem 0.25rem;
    display: flex; flex-direction: column; gap: 1rem;
    scroll-behavior: smooth;
}

/* Scrollbar */
.chat-messages::-webkit-scrollbar { width: 5px; }
.chat-messages::-webkit-scrollbar-track { background: transparent; }
.chat-messages::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 99px; }
.chat-messages::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.15); }

/* ─── Message rows ─── */
.msg-row {
    display: flex; align-items: flex-end; gap: 0.65rem;
    animation: msgIn 0.35s cubic-bezier(0.2, 0.9, 0.4, 1) both;
}
.msg-row.user { flex-direction: row-reverse; }

@keyframes msgIn {
    from { opacity: 0; transform: translateY(14px) scale(0.97); }
    to   { opacity: 1; transform: translateY(0)   scale(1);    }
}

/* Avatar */
.msg-avatar {
    width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.9rem; font-weight: 700;
}
.msg-avatar.ai-av {
    background: linear-gradient(135deg, #3b4fd8, #7c3aed);
    box-shadow: 0 0 12px rgba(59,79,216,0.4);
    font-size: 0.8rem;
}
.msg-avatar.user-av {
    background: linear-gradient(135deg, #1e40af, #4338ca);
    font-size: 0.8rem;
}

/* Bubble */
.chat-bubble {
    max-width: min(72%, 580px);
    padding: 0.85rem 1.1rem;
    border-radius: 18px;
    font-size: 0.88rem; line-height: 1.65;
    word-break: break-word;
    position: relative;
}
.chat-bubble.ai {
    background: rgba(15,23,42,0.65);
    border: 1px solid rgba(255,255,255,0.07);
    border-bottom-left-radius: 5px;
    backdrop-filter: blur(12px);
    color: var(--text-primary);
    box-shadow: 0 4px 24px rgba(0,0,0,0.25);
}
.chat-bubble.ai.success { border-color: rgba(16,185,129,0.3); }
.chat-bubble.ai.warning { border-color: rgba(245,158,11,0.3); }
.chat-bubble.ai.error   { border-color: rgba(239,68,68,0.3); }
.chat-bubble.ai.confirm { border-color: rgba(239,68,68,0.35); }
.chat-bubble.ai.streaming {
    border-color: rgba(59,130,246,0.4);
    box-shadow: 0 0 0 1px rgba(59,130,246,0.1), 0 4px 24px rgba(0,0,0,0.25);
}
.chat-bubble.user {
    background: linear-gradient(135deg, rgba(55,65,200,0.55), rgba(109,40,217,0.45));
    border: 1px solid rgba(139,92,246,0.3);
    border-bottom-right-radius: 5px;
    color: #e0e7ff;
    box-shadow: 0 4px 20px rgba(79,46,200,0.2);
}

/* Blinking cursor while streaming */
.stream-cursor {
    display: inline-block; width: 2px; height: 0.9em;
    background: var(--accent-blue); margin-left: 2px;
    vertical-align: text-bottom;
    border-radius: 1px;
    animation: blink 0.65s step-end infinite;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }

/* Code inside bubbles */
.chat-bubble pre {
    background: rgba(0,0,0,0.35); border-radius: 8px;
    padding: 0.7rem 0.9rem; overflow-x: auto;
    font-family: 'Cascadia Code','Consolas',monospace; font-size: 0.8rem;
    margin: 0.4rem 0; border: 1px solid rgba(255,255,255,0.06);
    white-space: pre-wrap; word-break: break-all;
}
.chat-bubble code {
    background: rgba(0,0,0,0.3); padding: 0.1rem 0.35rem;
    border-radius: 4px; font-family: 'Cascadia Code','Consolas',monospace;
    font-size: 0.82em;
}

/* ─── Welcome card ─── */
.welcome-card {
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; gap: 0.6rem;
    padding: 2.5rem 1rem; text-align: center;
    animation: fadeUp 0.6s ease both;
}
@keyframes fadeUp {
    from { opacity:0; transform: translateY(20px); }
    to   { opacity:1; transform: translateY(0); }
}
.welcome-orb {
    width: 72px; height: 72px; border-radius: 50%;
    background: linear-gradient(135deg, #3b4fd8, #7c3aed);
    box-shadow: 0 0 40px rgba(59,79,216,0.5), 0 0 80px rgba(124,58,237,0.3);
    display: flex; align-items: center; justify-content: center;
    font-size: 2rem; margin-bottom: 0.5rem;
    animation: orbPulse 3s ease-in-out infinite;
}
.welcome-title {
    font-size: 1.5rem; font-weight: 700;
    background: linear-gradient(120deg, #60a5fa, #c084fc);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.welcome-sub { font-size: 0.9rem; color: var(--text-secondary); max-width: 380px; }
.welcome-hints {
    display: flex; flex-wrap: wrap; gap: 0.5rem; justify-content: center;
    margin-top: 0.5rem;
}
.hint-chip {
    padding: 0.35rem 0.9rem; border-radius: 999px; font-size: 0.78rem;
    background: rgba(59,130,246,0.08); border: 1px solid rgba(59,130,246,0.2);
    color: #93c5fd; cursor: pointer; transition: all 0.2s;
    user-select: none;
}
.hint-chip:hover {
    background: rgba(59,130,246,0.15); border-color: rgba(59,130,246,0.4);
    transform: translateY(-1px);
}

/* ─── Input area ─── */
.input-area {
    padding: 0.9rem 0 1.1rem;
    flex-shrink: 0;
}
.input-box {
    display: flex; align-items: center; gap: 0.5rem;
    background: rgba(13,21,38,0.8);
    border: 1px solid rgba(255,255,255,0.09);
    border-radius: 18px;
    padding: 0.5rem 0.5rem 0.5rem 1rem;
    backdrop-filter: blur(20px);
    transition: border-color 0.25s, box-shadow 0.25s;
}
.input-box:focus-within {
    border-color: rgba(59,130,246,0.45);
    box-shadow: 0 0 0 3px rgba(59,130,246,0.08), 0 8px 32px rgba(0,0,0,0.3);
}
.chat-input {
    flex: 1; background: transparent; border: none; outline: none;
    color: var(--text-primary); font-size: 0.9rem; font-family: inherit;
    padding: 0.3rem 0;
    caret-color: var(--accent-blue);
}
.chat-input::placeholder { color: var(--text-dim); }

/* Mic + Send buttons */
.icon-btn {
    width: 40px; height: 40px; border-radius: 12px; border: none;
    background: rgba(255,255,255,0.04); color: var(--text-secondary);
    cursor: pointer; display: flex; align-items: center; justify-content: center;
    font-size: 1.05rem; transition: all 0.2s; flex-shrink: 0;
}
.icon-btn:hover { background: rgba(255,255,255,0.08); color: var(--text-primary); }
.icon-btn.mic:hover { background: rgba(16,185,129,0.12); color: #34d399; }
.icon-btn.send {
    background: linear-gradient(135deg, #3b82f6, #6d28d9);
    color: white;
    box-shadow: 0 4px 12px rgba(59,130,246,0.3);
}
.icon-btn.send:hover {
    transform: scale(1.07);
    box-shadow: 0 6px 20px rgba(59,130,246,0.45);
}
.icon-btn.mic.listening {
    background: rgba(16,185,129,0.15) !important;
    color: #34d399 !important;
    box-shadow: 0 0 0 2px rgba(16,185,129,0.3);
    animation: micPulse 1s ease infinite;
}
@keyframes micPulse { 0%,100%{transform:scale(1)} 50%{transform:scale(1.1)} }

/* ─── Confirm buttons inside bubble ─── */
.confirm-btns { display: flex; gap: 0.5rem; margin-top: 0.6rem; flex-wrap: wrap; }
.confirm-btn {
    padding: 0.35rem 0.9rem; border-radius: 8px; border: 1px solid;
    font-size: 0.78rem; font-weight: 500; cursor: pointer;
    font-family: inherit; transition: all 0.2s;
}
.confirm-btn.yes {
    background: rgba(16,185,129,0.1); border-color: rgba(16,185,129,0.35);
    color: #34d399;
}
.confirm-btn.yes:hover { background: rgba(16,185,129,0.2); }
.confirm-btn.no {
    background: rgba(239,68,68,0.1); border-color: rgba(239,68,68,0.35);
    color: #f87171;
}
.confirm-btn.no:hover { background: rgba(239,68,68,0.2); }
/* ─── Canlı Ekran İzleme ─── */
.screen-toggle {
    cursor: pointer; user-select: none;
    display: inline-flex; align-items: center; gap: 0.4rem;
    padding: 0.32rem 0.7rem; margin-right: 0.5rem;
    border-radius: 999px; font-size: 0.8rem; font-weight: 600;
    color: var(--text-secondary);
    border: 1px solid var(--border);
    background: rgba(255,255,255,0.03);
    transition: all .18s ease;
}
.screen-toggle:hover { color: var(--text-primary); background: rgba(59,130,246,0.12); border-color: rgba(59,130,246,0.35); }
.screen-toggle.active { color: #34d399; border-color: rgba(16,185,129,0.45); background: rgba(16,185,129,0.10); }

.screen-panel {
    position: fixed; right: 18px; bottom: 96px; width: 380px; max-width: 42vw;
    background: var(--bg-secondary);
    border: 1px solid rgba(59,130,246,0.28);
    border-radius: 16px; overflow: hidden; z-index: 50;
    box-shadow: 0 18px 50px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.02);
    animation: panelIn .22s ease;
}
@keyframes panelIn { from { opacity:0; transform: translateY(12px) scale(.98);} to {opacity:1; transform:none;} }
.screen-panel.hidden { display: none; }
.screen-panel-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0.55rem 0.8rem; font-size: 0.82rem; font-weight: 700;
    color: var(--text-primary);
    background: linear-gradient(120deg, rgba(59,130,246,0.18), rgba(139,92,246,0.14));
    border-bottom: 1px solid var(--border);
}
.screen-panel-head .live-dot {
    display:inline-block; width:8px; height:8px; border-radius:50%;
    background:#ef4444; margin-right:6px; animation: livePulse 1.1s infinite;
}
@keyframes livePulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.screen-panel-head .sp-btns { display:flex; gap:0.3rem; }
.screen-panel-head button {
    cursor:pointer; border:none; border-radius:7px; padding:0.2rem 0.5rem;
    font-size:0.74rem; font-weight:600; color:var(--text-secondary);
    background: rgba(255,255,255,0.06); transition: all .15s;
}
.screen-panel-head button:hover { color:#fff; background: rgba(59,130,246,0.3); }
.screen-panel img { display:block; width:100%; height:auto; background:#000; min-height:120px; }
.screen-panel-foot {
    padding: 0.4rem 0.8rem; font-size:0.72rem; color: var(--text-dim);
    display:flex; justify-content:space-between; align-items:center;
    border-top: 1px solid var(--border); background: rgba(0,0,0,0.25);
}
</style>
</head>
<body>
<div id="app">

  <!-- ═══ HEADER ═══ -->
  <header class="header">
    <div class="header-brand">
      <div class="brand-orb">✦</div>
      <div>
        <div class="brand-title">BLUE AI</div>
        <div class="brand-sub" id="model-name">Yükleniyor...</div>
      </div>
    </div>
    <div class="header-right">
      <div class="screen-toggle" id="screen-toggle" onclick="toggleScreenWatch()" title="Canlı ekran izlemeyi aç/kapat">
        <span>👁️</span><span id="screen-label">Ekranı İzle</span>
      </div>
      <div class="status-pill online" id="llm-status">
        <span class="status-dot"></span>
        <span id="llm-label">Bağlı</span>
      </div>
    </div>
  </header>

  <!-- ═══ CHAT ═══ -->
  <div class="chat-wrap">
    <div class="chat-messages" id="chat-messages">

      <!-- Welcome state -->
      <div class="welcome-card" id="welcome-card">
        <div class="welcome-orb">✦</div>
        <div class="welcome-title">Merhaba, ben BLUE AI</div>
        <div class="welcome-sub">Sana yardımcı olmak için buradayım. Bir şeyler sor, sistem komutları ver ya da kod yazmamı iste.</div>
        <div class="welcome-hints">
          <span class="hint-chip" onclick="quickSend('CPU ve RAM durumu nedir?')">Sistem durumu</span>
          <span class="hint-chip" onclick="quickSend('Sesi %40 yap')">Ses ayarı</span>
          <span class="hint-chip" onclick="quickSend('Python ile merhaba dünya kodu yaz')">Kod yaz</span>
          <span class="hint-chip" onclick="quickSend('Hangi uygulamalar çalışıyor?')">Süreçler</span>
        </div>
      </div>

    </div><!-- /chat-messages -->

    <!-- Input -->
    <div class="input-area">
      <div class="input-box">
        <button class="icon-btn mic" id="mic-btn" onclick="listenMic()" title="Sesli komut">🎙️</button>
        <input class="chat-input" id="chat-input"
               placeholder="Bir şey sor veya komut ver..."
               onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendChat()}"
               autocomplete="off">
        <button class="icon-btn send" onclick="sendChat()" title="Gönder">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
    </div>
  </div><!-- /chat-wrap -->

  <!-- ═══ CANLI EKRAN PANELİ ═══ -->
  <div class="screen-panel hidden" id="screen-panel">
    <div class="screen-panel-head">
      <span><span class="live-dot"></span>Canlı Ekran</span>
      <div class="sp-btns">
        <button onclick="quickSend('ekranı oku')" title="Ekrandaki yazıları oku">🔍 Oku</button>
        <button onclick="stopScreenWatch()" title="İzlemeyi kapat">✕</button>
      </div>
    </div>
    <img id="screen-view" alt="Canlı ekran görüntüsü">
    <div class="screen-panel-foot">
      <span id="screen-info">Başlatılıyor…</span>
      <span>👁️ BLUE AI izliyor</span>
    </div>
  </div>

</div><!-- /app -->

<script>
// ── Markdown renderer ──────────────────────────────────────────────────────
function renderMarkdown(text) {
    if (!text) return '';
    var s = text
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    // Fenced code blocks
    var parts = s.split('```');
    for (var i = 1; i < parts.length; i += 2) {
        var code = parts[i];
        var firstNL = code.indexOf('\n');
        if (firstNL >= 0) {
            var tag = code.substring(0, firstNL).trim();
            if (/^[a-z]*$/.test(tag)) { code = code.substring(firstNL + 1); }
        }
        parts[i] = '<pre><code>' + code + '</code></pre>';
    }
    s = parts.join('');
    // Inline code
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    // Bold
    s = s.split('**').map(function(p,i){return i%2===1?'<strong>'+p+'</strong>':p;}).join('');
    // Italic
    s = s.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
    // Headers
    s = s.replace(/^#{1,3} (.+)$/gm,
        '<strong style="font-size:1.02em;display:block;margin-bottom:0.2rem">$1</strong>');
    // Lists
    s = s.replace(/^[-*] (.+)$/gm,
        '<span style="display:block;padding-left:1rem;margin:0.1rem 0">• $1</span>');
    s = s.replace(/^\d+\. (.+)$/gm,
        '<span style="display:block;padding-left:1rem;margin:0.1rem 0">• $1</span>');
    // Newlines
    s = s.replace(/\n/g, '<br>');
    return s;
}

// ── State ─────────────────────────────────────────────────────────────────
var isSending      = false;
var _streamDiv     = null;
var _streamRawText = '';

// ── Helpers ───────────────────────────────────────────────────────────────
function scrollBottom() {
    var box = document.getElementById('chat-messages');
    box.scrollTop = box.scrollHeight;
}

function hideWelcome() {
    var w = document.getElementById('welcome-card');
    if (w) w.style.display = 'none';
}

function quickSend(text) {
    document.getElementById('chat-input').value = text;
    sendChat();
}

// ── Canlı ekran izleme ─────────────────────────────────────────────────────
// Backend (ScreenWatcher) tek doğru kaynaktır. UI bu duruma göre kendini eşitler;
// böylece izleme ister header butonundan ister sesli/yazılı komuttan açılsın panel uyumlu.
var _screenReconcile = null;

function startScreenReconcile() {
    if (_screenReconcile) return;
    _screenReconcile = setInterval(reconcileScreen, 450);
    reconcileScreen();
}

async function reconcileScreen() {
    try {
        var d = JSON.parse(await pywebview.api.get_screen_frame());
        var panel = document.getElementById('screen-panel');
        var tog   = document.getElementById('screen-toggle');
        var label = document.getElementById('screen-label');
        if (d.active) {
            panel.classList.remove('hidden');
            tog.classList.add('active');
            if (label) label.textContent = 'İzleniyor';
            if (d.frame) document.getElementById('screen-view').src = d.frame;
            var info = document.getElementById('screen-info');
            if (info) info.textContent = 'Kare #' + (d.frames || 0);
        } else {
            panel.classList.add('hidden');
            tog.classList.remove('active');
            if (label) label.textContent = 'Ekranı İzle';
        }
    } catch (e) { /* api henüz hazır değil */ }
}

async function toggleScreenWatch() {
    try {
        var d = JSON.parse(await pywebview.api.get_screen_frame());
        if (d.active) { await pywebview.api.screen_watch_stop(); }
        else          { await pywebview.api.screen_watch_start(); }
    } catch (e) {}
    reconcileScreen();
}

async function stopScreenWatch() {
    try { await pywebview.api.screen_watch_stop(); } catch (e) {}
    reconcileScreen();
}

window.addEventListener('pywebviewready', startScreenReconcile);

// ── Add message row ────────────────────────────────────────────────────────
function addChat(who, text, type) {
    hideWelcome();
    var box  = document.getElementById('chat-messages');
    var row  = document.createElement('div');
    row.className = 'msg-row ' + who;

    var av   = document.createElement('div');
    av.className = 'msg-avatar ' + (who === 'ai' ? 'ai-av' : 'user-av');
    av.textContent = who === 'ai' ? '✦' : '👤';

    var bub  = document.createElement('div');
    bub.className = 'chat-bubble ' + who + (type ? ' ' + type : '');

    if (who === 'ai') {
        bub.innerHTML = renderMarkdown(text);
    } else {
        bub.textContent = text;
    }

    row.appendChild(av);
    row.appendChild(bub);
    box.appendChild(row);
    scrollBottom();
    return bub;
}

// ── Streaming ─────────────────────────────────────────────────────────────
function _createStreamBubble() {
    hideWelcome();
    _streamRawText = '';
    var box  = document.getElementById('chat-messages');
    var row  = document.createElement('div');
    row.className = 'msg-row ai';
    row.id = 'stream-row';

    var av   = document.createElement('div');
    av.className = 'msg-avatar ai-av';
    av.textContent = '✦';

    var bub  = document.createElement('div');
    bub.className = 'chat-bubble ai streaming';
    var cur  = document.createElement('span');
    cur.className = 'stream-cursor';
    bub.appendChild(cur);

    row.appendChild(av);
    row.appendChild(bub);
    box.appendChild(row);
    scrollBottom();
    return bub;
}

function appendChatChunk(text) {
    if (!_streamDiv) return;
    _streamRawText += text;
    var cur = _streamDiv.querySelector('.stream-cursor');
    if (cur) _streamDiv.insertBefore(document.createTextNode(text), cur);
    else     _streamDiv.appendChild(document.createTextNode(text));
    scrollBottom();
}

function finishChatStreamB64(b64) {
    try {
        _finalizeStream(JSON.parse(atob(b64)));
    } catch(e) {
        console.error('finishChatStreamB64:', e);
        if (_streamDiv) _streamDiv.classList.remove('streaming');
        _streamDiv = null; isSending = false;
    }
}

function _finalizeStream(data) {
    if (!_streamDiv) { isSending = false; return; }
    var cur = _streamDiv.querySelector('.stream-cursor');
    if (cur) cur.remove();
    _streamDiv.classList.remove('streaming');

    if (data.response_type === 'confirm' && data.pending_confirmation) {
        var _row = _streamDiv.parentElement;
        if (_row) _row.remove();
        _streamDiv = null; isSending = false;
        addConfirmation(data.text, data.pending_confirmation);
        return;
    }

    var finalText = data.text || _streamRawText || '';
    if (finalText) _streamDiv.innerHTML = renderMarkdown(finalText);
    _streamRawText = '';

    if (data.response_type === 'success') _streamDiv.classList.add('success');
    else if (data.response_type === 'warning') _streamDiv.classList.add('warning');
    else if (data.response_type === 'error')   _streamDiv.classList.add('error');

    _streamDiv = null; isSending = false;
}

// ── Send ──────────────────────────────────────────────────────────────────
async function sendChat() {
    if (isSending) return;
    var inp = document.getElementById('chat-input');
    var msg = inp.value.trim();
    if (!msg) return;
    inp.value = '';
    addChat('user', msg);
    isSending = true;
    _streamDiv = _createStreamBubble();
    try {
        var raw = await pywebview.api.start_chat_stream(msg);
        var r   = JSON.parse(raw);
        if (r.status !== 'streaming') {
            if (_streamDiv) {
                var cur2 = _streamDiv.querySelector('.stream-cursor');
                if (cur2) cur2.remove();
                _streamDiv.classList.remove('streaming');
                _streamDiv.innerHTML = renderMarkdown(r.response || '');
            }
            _streamDiv = null; isSending = false;
        }
    } catch(e) {
        if (_streamDiv) { _streamDiv.classList.remove('streaming'); _streamDiv.textContent = 'Hata: ' + e.message; }
        _streamDiv = null; isSending = false;
    }
}

// ── Mic ───────────────────────────────────────────────────────────────────
async function listenMic() {
    if (isSending) return;
    var btn = document.getElementById('mic-btn');
    btn.classList.add('listening');
    isSending = true;

    // placeholder listening row
    var box = document.getElementById('chat-messages');
    var lRow = document.createElement('div');
    lRow.className = 'msg-row user'; lRow.id = 'mic-listening';
    var lAv = document.createElement('div');
    lAv.className = 'msg-avatar user-av'; lAv.textContent = '👤';
    var lBub = document.createElement('div');
    lBub.className = 'chat-bubble user'; lBub.style.opacity = '0.5';
    lBub.textContent = '🎤 Dinleniyor...';
    lRow.appendChild(lAv); lRow.appendChild(lBub);
    box.appendChild(lRow); scrollBottom();

    try {
        var raw = await pywebview.api.listen_voice();
        var r   = JSON.parse(raw);
        if (r.status === 'recording') return;  // async — wait for receiveVoiceResult
        _handleVoiceResult(r);
    } catch(e) {
        var ml = document.getElementById('mic-listening');
        if (ml) ml.remove();
        addChat('ai', 'Ses hatası: ' + (e.message || e), 'warning');
        _resetMic();
    }
}

function receiveVoiceResult(raw) {
    try { _handleVoiceResult(JSON.parse(raw)); }
    catch(e) { addChat('ai', 'Sonuç alınamadı: ' + e, 'warning'); _resetMic(); }
}

function _handleVoiceResult(r) {
    var mlr = document.getElementById('mic-listening');
    if (mlr) mlr.remove();
    if (r.recognized_text) addChat('user', r.recognized_text);
    else if (!r.response || r.type !== 'warning') addChat('user', '🎤 (Anlaşılamadı)');
    if (r.type === 'confirm' && r.pending_confirmation)
        addConfirmation(r.response, r.pending_confirmation);
    else if (r.response) addChat('ai', r.response, r.type);
    _resetMic();
}

function _resetMic() {
    isSending = false;
    var mb = document.getElementById('mic-btn');
    if (mb) mb.classList.remove('listening');
}

// ── Confirmations ──────────────────────────────────────────────────────────
function addConfirmation(message, confirmation) {
    hideWelcome();
    var box  = document.getElementById('chat-messages');
    var row  = document.createElement('div');
    row.className = 'msg-row ai';
    var av   = document.createElement('div');
    av.className = 'msg-avatar ai-av'; av.textContent = '✦';
    var bub  = document.createElement('div');
    bub.className = 'chat-bubble ai confirm';
    var msgHtml = message.split('\n').join('<br>');
    bub.innerHTML =
        '<div style="margin-bottom:0.5rem">' + msgHtml + '</div>' +
        '<div class="confirm-btns">' +
          '<button class="confirm-btn yes" onclick="handleConfirm(\'' + confirmation.tool_name + '\',true,this)">✓ Evet, yap</button>' +
          '<button class="confirm-btn no"  onclick="handleConfirm(\'' + confirmation.tool_name + '\',false,this)">✗ Hayır, iptal</button>' +
        '</div>';
    row.appendChild(av); row.appendChild(bub);
    box.appendChild(row); scrollBottom();
}

async function handleConfirm(toolName, approved, btn) {
    var btns = btn.parentElement.querySelectorAll('button');
    for (var i = 0; i < btns.length; i++) btns[i].disabled = true;
    try {
        var raw = await pywebview.api.confirm_action(toolName, approved);
        var r   = JSON.parse(raw);
        addChat('ai', r.response, r.type);
    } catch(e) {
        addChat('ai', 'Hata: ' + (e.message || e), 'warning');
    }
}

// ── LLM status ────────────────────────────────────────────────────────────
async function checkLLMStatus() {
    try {
        var raw = await pywebview.api.get_llm_status();
        var r   = JSON.parse(raw);
        var pill  = document.getElementById('llm-status');
        var label = document.getElementById('llm-label');
        var mname = document.getElementById('model-name');
        if (r.available) {
            pill.className = 'status-pill online';
            label.textContent = 'Bağlı';
            if (mname) mname.textContent = r.active_model || 'gemma3:1b';
        } else {
            pill.className = 'status-pill offline';
            label.textContent = 'Offline';
            if (mname) mname.textContent = 'Ollama kapalı';
        }
    } catch(e) {
        var mn = document.getElementById('model-name');
        if (mn) mn.textContent = 'Bağlanıyor...';
    }
}

// ── Push-to-Talk (Boşluk tuşu: bas → kaydet, bırak → tanı) ──────────────
var _pttActive    = false;
var _pttReady     = false;  // stream gerçekten açıldı mı
var _spaceUpPending = false; // start tamamlanmadan bırakıldı mı

document.addEventListener('keydown', function(e) {
    if (e.code === 'Space' && !_pttActive && !isSending) {
        var tag = (document.activeElement || {}).tagName;
        if (tag && tag.toLowerCase() !== 'input' && tag.toLowerCase() !== 'textarea') {
            e.preventDefault();
            _pttActive = true;
            _pttReady  = false;
            _spaceUpPending = false;
            _startPTT();
        }
    }
});

document.addEventListener('keyup', function(e) {
    if (e.code === 'Space' && _pttActive) {
        if (!_pttReady) {
            _spaceUpPending = true;  // start bitmeden bırakıldı — start bitince stop çağır
        } else {
            _pttActive = false;
            _stopPTT();
        }
    }
});

async function _startPTT() {
    hideWelcome();
    var btn = document.getElementById('mic-btn');
    if (btn) btn.classList.add('listening');

    var box = document.getElementById('chat-messages');
    var lRow = document.createElement('div');
    lRow.className = 'msg-row user'; lRow.id = 'mic-listening';
    var lAv = document.createElement('div');
    lAv.className = 'msg-avatar user-av'; lAv.textContent = '👤';
    var lBub = document.createElement('div');
    lBub.className = 'chat-bubble user'; lBub.style.opacity = '0.55';
    lBub.textContent = '⏳ Hazırlanıyor...';
    lRow.appendChild(lAv); lRow.appendChild(lBub);
    box.appendChild(lRow); scrollBottom();

    try {
        await pywebview.api.start_voice_ptt();  // stream açılana kadar bekler
        _pttReady = true;
        // Metni güncelle
        var b = document.querySelector('#mic-listening .chat-bubble');
        if (b) b.textContent = '🎤 Konuşun... (bırakınca gönderilir)';
        // Eğer kullanıcı start tamamlanmadan bıraktıysa hemen stop çağır
        if (_spaceUpPending) {
            _pttActive = false;
            _stopPTT();
        }
    } catch(e) {
        console.error('[PTT] start error:', e);
        var ml = document.getElementById('mic-listening');
        if (ml) ml.remove();
        _pttActive = false;
        _resetMic();
    }
}

async function _stopPTT() {
    isSending = true;
    var lBub = document.querySelector('#mic-listening .chat-bubble');
    if (lBub) lBub.textContent = '🎤 İşleniyor...';

    try {
        var raw = await pywebview.api.stop_voice_ptt();
        var r   = JSON.parse(raw);
        if (r.status === 'processing') return; // async — receiveVoiceResult bekle
        _handleVoiceResult(r);
    } catch(e) {
        var ml = document.getElementById('mic-listening');
        if (ml) ml.remove();
        addChat('ai', 'PTT hatası: ' + (e.message || e), 'warning');
        _resetMic();
    }
}

// ── Init ──────────────────────────────────────────────────────────────────
window.addEventListener('pywebviewready', function() {
    checkLLMStatus();
    setInterval(checkLLMStatus, 15000);
    // Sayfa yüklenince input'a fokus ver
    var inp = document.getElementById('chat-input');
    if (inp) inp.focus();
});

window.onerror = function(msg, src, line) {
    var box = document.getElementById('chat-messages');
    if (box) {
        var err = document.createElement('div');
        err.style.cssText = 'color:#f87171;font-size:0.75rem;padding:0.5rem;text-align:center;opacity:0.7';
        err.textContent = 'JS Hata: ' + msg + ' (' + line + ')';
        box.appendChild(err);
    }
};
</script>
</body>
</html>'''


def start_proactive(window):
    from blue_ai.core.proactive import ProactiveMonitor
    monitor = ProactiveMonitor(window)
    monitor.start()

def main():
    backend = BlueAIBackend()
    window = webview.create_window(
        title='BLUE_AI',
        html=get_html(),
        js_api=backend,
        width=1280,
        height=800,
        min_size=(900, 600),
        background_color='#0a0e1a',
        text_select=True,
    )
    # Backend'in window referansi olsun (async JS push icin)
    backend._window = window

    webview.start(start_proactive, window, debug=False)


if __name__ == '__main__':
    main()
