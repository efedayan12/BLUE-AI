"""
BLUE_AI — Komut Yurutucu (Executor)

Intent'e gore dogru araci cagirir ve sonuc dondurur.
"""

import json
import psutil
import os
from pathlib import Path

from blue_ai.ai.intent import detect_intent, IntentType, Intent
from blue_ai.ai.llm import get_llm
from blue_ai.utils.helpers import bytes_to_human, seconds_to_human
from blue_ai.utils.win_api import get_system_power_status, set_power_scheme
from blue_ai.core.config import get_profile


class Executor:
    """Komut yurutucu — intent'e gore islem yapar."""

    def __init__(self):
        self._current_profile = "balanced"

    def execute(self, message: str) -> dict:
        """Mesaji isle ve sonuc dondur."""
        intent = detect_intent(message)
        handler = self._get_handler(intent.type)
        try:
            result = handler(intent)
            return result
        except Exception as e:
            return {"response": f"Hata: {str(e)}", "type": "error"}

    def _get_handler(self, intent_type: IntentType):
        """Intent turune gore handler dondur."""
        handlers = {
            IntentType.SYSTEM_STATUS: self._handle_system_status,
            IntentType.PROCESS_LIST: self._handle_process_list,
            IntentType.PROCESS_KILL: self._handle_process_kill,
            IntentType.CLEAN: self._handle_clean,
            IntentType.OPTIMIZE: self._handle_optimize,
            IntentType.PROFILE_CHANGE: self._handle_profile_change,
            IntentType.DISK_INFO: self._handle_disk_info,
            IntentType.NETWORK_INFO: self._handle_network_info,
            IntentType.BATTERY_INFO: self._handle_battery_info,
            IntentType.RAM_INFO: self._handle_ram_info,
            IntentType.HELP: self._handle_help,
            IntentType.CREATE_DOCUMENT: self._handle_create_document,
            IntentType.CREATE_SPREADSHEET: self._handle_create_spreadsheet,
            IntentType.CREATE_PRESENTATION: self._handle_create_presentation,
            IntentType.FILE_OPERATION: self._handle_file_operation,
            IntentType.OPEN_APP: self._handle_open_app,
            IntentType.WEB_SEARCH: self._handle_web_search,
            IntentType.GENERAL_QUESTION: self._handle_general_question,
            IntentType.UNKNOWN: self._handle_general_question,
        }
        return handlers.get(intent_type, self._handle_general_question)

    # ===== SISTEM =====

    def _handle_system_status(self, intent: Intent) -> dict:
        import time
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        boot = time.time() - psutil.boot_time()
        return {
            "response": f"Sistem Durumu:\n"
                       f"  CPU: %{cpu:.1f}\n"
                       f"  RAM: %{ram.percent:.1f} ({bytes_to_human(ram.used)} / {bytes_to_human(ram.total)})\n"
                       f"  Disk: %{disk.percent:.1f} ({bytes_to_human(disk.free)} bos)\n"
                       f"  Uptime: {seconds_to_human(boot)}\n"
                       f"  Profil: {self._current_profile}",
            "type": "info"
        }

    def _handle_process_list(self, intent: Intent) -> dict:
        procs = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
            try:
                info = proc.info
                mem = info.get("memory_info")
                procs.append({"name": info["name"], "cpu": info.get("cpu_percent", 0) or 0,
                              "ram": mem.rss if mem else 0, "pid": info["pid"]})
            except:
                continue
        procs.sort(key=lambda p: p["cpu"], reverse=True)
        lines = "En cok CPU kullanan surecler:\n"
        for i, p in enumerate(procs[:8], 1):
            lines += f"  {i}. {p['name']} (PID:{p['pid']}) - CPU: %{p['cpu']:.1f}, RAM: {bytes_to_human(p['ram'])}\n"
        return {"response": lines, "type": "info"}

    def _handle_process_kill(self, intent: Intent) -> dict:
        return {"response": "Surec sonlandirma icin surec tablosundan X butonunu kullanin.", "type": "info"}

    def _handle_clean(self, intent: Intent) -> dict:
        import tempfile
        temp_dir = tempfile.gettempdir()
        count, total = 0, 0
        for f in os.listdir(temp_dir):
            fp = os.path.join(temp_dir, f)
            try:
                if os.path.isfile(fp):
                    total += os.path.getsize(fp)
                    os.remove(fp)
                    count += 1
            except:
                continue
        return {"response": f"Temizlik tamamlandi!\n  {count} dosya silindi\n  {bytes_to_human(total)} alan kazanildi", "type": "success"}

    def _handle_optimize(self, intent: Intent) -> dict:
        ram = psutil.virtual_memory()
        return {"response": f"Optimizasyon durumu:\n  RAM: %{ram.percent:.1f}\n  Kullanilabilir: {bytes_to_human(ram.available)}\n  Profil: {self._current_profile}", "type": "info"}

    def _handle_profile_change(self, intent: Intent) -> dict:
        profile_name = intent.params.get("profile", "balanced")
        try:
            profile = get_profile(profile_name)
            if profile:
                power_plan = profile.get("power_plan", "balanced")
                set_power_scheme(power_plan)
                self._current_profile = profile_name
                names = {"gaming": "Oyun", "work": "Is", "power_saver": "Tasarruf", "balanced": "Dengeli"}
                return {"response": f"{names.get(profile_name, profile_name)} moduna gecildi!", "type": "success"}
        except:
            pass
        return {"response": f"Profil degistirildi: {profile_name}", "type": "success"}

    def _handle_disk_info(self, intent: Intent) -> dict:
        lines = "Disk Bilgileri:\n"
        for part in psutil.disk_partitions():
            try:
                u = psutil.disk_usage(part.mountpoint)
                lines += f"  {part.device}: %{u.percent:.0f} ({bytes_to_human(u.free)} bos / {bytes_to_human(u.total)})\n"
            except:
                continue
        return {"response": lines, "type": "info"}

    def _handle_network_info(self, intent: Intent) -> dict:
        c = psutil.net_io_counters()
        conns = len(psutil.net_connections(kind='inet'))
        return {"response": f"Ag Durumu:\n  Gonderilen: {bytes_to_human(c.bytes_sent)}\n  Alinan: {bytes_to_human(c.bytes_recv)}\n  Aktif baglanti: {conns}", "type": "info"}

    def _handle_battery_info(self, intent: Intent) -> dict:
        power = get_system_power_status()
        if power.get("has_battery"):
            ac = "Sarjda" if power["ac_plugged"] else "Pilde"
            return {"response": f"Pil: %{power['battery_percent']} ({ac})", "type": "info"}
        return {"response": "Bu cihazda pil bulunmuyor.", "type": "info"}

    def _handle_ram_info(self, intent: Intent) -> dict:
        ram = psutil.virtual_memory()
        return {"response": f"RAM Durumu:\n  Kullanim: %{ram.percent:.1f}\n  Kullanilan: {bytes_to_human(ram.used)}\n  Toplam: {bytes_to_human(ram.total)}\n  Kullanilabilir: {bytes_to_human(ram.available)}", "type": "info"}

    def _handle_help(self, intent: Intent) -> dict:
        return {
            "response": "BLUE_AI Komutlari:\n"
                       "  Sistem: 'durum', 'surecler', 'disk', 'ag', 'ram', 'pil'\n"
                       "  Islem: 'temizle', 'optimize'\n"
                       "  Profil: 'oyun modu', 'is modu', 'tasarruf', 'dengeli'\n"
                       "  Belge: 'word belgesi hazirla', 'excel tablosu yap', 'sunum hazirla'\n"
                       "  Dosya: 'dosya bul', 'buyuk dosyalar'\n"
                       "  Uygulama: 'chrome ac', 'notepad ac'\n"
                       "  Genel: Herhangi bir soru sorabilirsiniz",
            "type": "info"
        }

    # ===== AI YETENEKLERI =====

    def _handle_create_document(self, intent: Intent) -> dict:
        from blue_ai.tools.document import create_word_document
        topic = intent.params.get("topic", intent.raw_message)
        result = create_word_document(topic)
        if result["success"]:
            return {"response": f"Word belgesi olusturuldu!\nDosya: {result['path']}", "type": "success"}
        return {"response": f"Hata: {result.get('error', 'Bilinmeyen hata')}", "type": "error"}

    def _handle_create_spreadsheet(self, intent: Intent) -> dict:
        from blue_ai.tools.document import create_excel_spreadsheet
        topic = intent.params.get("topic", intent.raw_message)
        result = create_excel_spreadsheet(topic)
        if result["success"]:
            return {"response": f"Excel tablosu olusturuldu!\nDosya: {result['path']}", "type": "success"}
        return {"response": f"Hata: {result.get('error', 'Bilinmeyen hata')}", "type": "error"}

    def _handle_create_presentation(self, intent: Intent) -> dict:
        from blue_ai.tools.document import create_presentation
        topic = intent.params.get("topic", intent.raw_message)
        result = create_presentation(topic)
        if result["success"]:
            return {"response": f"PowerPoint sunumu olusturuldu!\nDosya: {result['path']}", "type": "success"}
        return {"response": f"Hata: {result.get('error', 'Bilinmeyen hata')}", "type": "error"}

    def _handle_file_operation(self, intent: Intent) -> dict:
        from blue_ai.tools.file_ops import find_files, get_large_files
        msg = intent.raw_message.lower()
        if "buyuk" in msg or "large" in msg:
            files = get_large_files()
            if files:
                lines = "Buyuk dosyalar:\n"
                for f in files[:10]:
                    lines += f"  {f['name']} - {f['size']} ({f['path']})\n"
                return {"response": lines, "type": "info"}
            return {"response": "100MB ustu dosya bulunamadi.", "type": "info"}
        else:
            # Aranacak kelimeyi cikar
            words = msg.replace("dosya", "").replace("bul", "").replace("ara", "").strip()
            if words:
                files = find_files(words)
                if files:
                    lines = f"'{words}' icin {len(files)} sonuc:\n"
                    for f in files[:10]:
                        lines += f"  {f['name']} - {f['size']} ({f['path']})\n"
                    return {"response": lines, "type": "info"}
                return {"response": f"'{words}' ile eslesen dosya bulunamadi.", "type": "info"}
        return {"response": "Ne aramami istersiniz? Ornek: 'rapor dosyasi bul'", "type": "info"}

    def _handle_open_app(self, intent: Intent) -> dict:
        from blue_ai.tools.app_control import open_application
        app = intent.params.get("app", "")
        if app:
            result = open_application(app)
            return {"response": result["message"] if result["success"] else result.get("error", "Hata"), "type": "success" if result["success"] else "error"}
        return {"response": "Hangi uygulamayi acmami istersiniz?", "type": "info"}

    def _handle_web_search(self, intent: Intent) -> dict:
        from blue_ai.tools.app_control import open_url
        topic = intent.raw_message
        # Arama kelimelerini cikar
        for w in ["ara", "arastir", "internette", "webde", "google", "bul"]:
            topic = topic.replace(w, "")
        topic = topic.strip()
        if topic:
            url = f"https://www.google.com/search?q={topic.replace(' ', '+')}"
            open_url(url)
            return {"response": f"Google'da aranıyor: {topic}", "type": "success"}
        return {"response": "Ne aramami istersiniz?", "type": "info"}

    def _handle_general_question(self, intent: Intent) -> dict:
        llm = get_llm()
        if llm.is_available():
            system = """Sen BLUE_AI yapay zeka asistanisin. Bilgisayar yonetimi ve genel konularda 
yardimci olursun. Kisa ve net cevaplar ver. Turkce yaz."""
            response = llm.generate(intent.raw_message, system=system)
            return {"response": response, "type": "info"}
        return {"response": "Bu soruyu cevaplayabilmek icin Ollama'nin calisiyor olmasi gerekiyor.\n'ollama serve' komutuyla baslatin.", "type": "warning"}
