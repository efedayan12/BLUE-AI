"""
BLUE_AI — Proaktif Davranış (Proactive Monitor)

Sistemi arka planda sürekli izler ve anormal durumlarda (örn. RAM veya CPU %95'in üzerine çıkarsa)
kullanıcıyı manuel komut almadan uyarır.
"""

import threading
import time
import psutil

class ProactiveMonitor:
    def __init__(self, window):
        self.window = window
        self.running = False
        self.checking_interval = 20  # Her 20 saniyede bir kontrol et
        
        # Hatirlatmama sureleri (art arda cok fazla bildirim atmamak icin)
        self.cooldowns = {
            'ram': 0,
            'cpu': 0,
            'disk': 0
        }
        self.cooldown_period = 300  # 5 dakika icinde ayni uyariyi tekrar etme

    def start(self):
        self.running = True
        t = threading.Thread(target=self._monitor_loop, daemon=True)
        t.start()

    def stop(self):
        self.running = False

    def _monitor_loop(self):
        # Window load olana kadar bekle
        time.sleep(5)
        
        while self.running:
            current_time = time.time()
            
            # RAM Kontrolü (Sınır %90)
            ram = psutil.virtual_memory()
            if ram.percent >= 90.0 and (current_time - self.cooldowns['ram'] > self.cooldown_period):
                msg = f"⚠️ Proaktif Uyari: Bellek (RAM) kullanimi cok yuksek (%{ram.percent:.1f}). Performans kaybi yasanabilir. Isterseniz 'temizle' veya 'RAM'i rahatlat' diyebilirsiniz."
                self._send_notification(msg)
                self.cooldowns['ram'] = current_time
                
            # CPU Kontrolü (Sınır %95)
            cpu = psutil.cpu_percent(interval=1)
            if cpu >= 95.0 and (current_time - self.cooldowns['cpu'] > self.cooldown_period):
                msg = f"⚠️ Proaktif Uyari: İslemci (CPU) kullanimi cok yuksek (%{cpu:.1f}). Görev Yöneticisine ('süreçler' diyerek) goz atabilirsiniz."
                self._send_notification(msg)
                self.cooldowns['cpu'] = current_time
                
            # Disk Kontrolü (Sınır %95 C Surucusu icin)
            try:
                disk = psutil.disk_usage('C:\\')
                if disk.percent >= 95.0 and (current_time - self.cooldowns['disk'] > self.cooldown_period * 2):
                    msg = f"⚠️ Proaktif Uyari: C: surucusunde yer azalıyor (Doluluk: %{disk.percent:.1f}). Temizliğe ihiyaciniz olabilir."
                    self._send_notification(msg)
                    self.cooldowns['disk'] = current_time
            except Exception:
                pass
                
            time.sleep(self.checking_interval)

    def _send_notification(self, message: str):
        """Webview'e JS uzerinden mesaj gonderir ve eger aciksa sese cevirir."""
        import json
        escaped_msg = json.dumps(message)[1:-1]  # tirnaklardan kurtul, safe string
        js_code = f"addChat('ai', '{escaped_msg}', 'warning');"
        
        try:
            self.window.evaluate_js(js_code)
            
            # Sesli asistan aktifse sesi de oku
            try:
                from blue_ai.voice.tts import get_tts
                from blue_ai.brain.response_formatter import ResponseFormatter
                voice_text = ResponseFormatter.format_for_voice(message)
                get_tts().speak(voice_text)
            except Exception:
                pass
            
        except Exception as e:
            print(f"Proaktif mesaj gonderilemedi: {e}")
