"""
BLUE_AI — System Tools

Sistem yönetim araçları — LLM'nin çağırabileceği tool'lar.
Mevcut plugin/executor fonksiyonlarını BaseTool arayüzüne taşır.
"""

from __future__ import annotations

import os
import time
import tempfile
from pathlib import Path

import psutil

from blue_ai.brain.tool_registry import (
    BaseTool, ToolParameter, ToolResult, PermissionLevel,
)
from blue_ai.utils.helpers import bytes_to_human, seconds_to_human


# ═══════════════════════════════════════════════════
#  SISTEM DURUM SORGULAMA
# ═══════════════════════════════════════════════════

class SystemStatusTool(BaseTool):
    """Sistem durum bilgisi (CPU, RAM, Disk, GPU, Uptime)."""

    name = "system_status"
    description = "Sistemin CPU, RAM, Disk kullanımını ve genel durumunu gösterir"
    description_en = "Shows system CPU, RAM, Disk usage and general status"
    permission_level = PermissionLevel.AUTO
    parameters = [
        ToolParameter(
            name="detail_level",
            type="string",
            description="Detay seviyesi: 'brief' kısa özet, 'detailed' detaylı",
            required=False,
            enum=["brief", "detailed"],
            default="brief",
        ),
    ]

    def execute(self, detail_level: str = "brief", **kwargs) -> ToolResult:
        cpu = psutil.cpu_percent(interval=0.5)
        cpu_per_core = psutil.cpu_percent(percpu=True)
        cpu_freq = psutil.cpu_freq()
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        boot = time.time() - psutil.boot_time()

        data = {
            "cpu_percent": round(cpu, 1),
            "cpu_cores": psutil.cpu_count(),
            "cpu_freq_mhz": round(cpu_freq.current, 0) if cpu_freq else 0,
            "ram_percent": round(ram.percent, 1),
            "ram_used": bytes_to_human(ram.used),
            "ram_total": bytes_to_human(ram.total),
            "ram_available": bytes_to_human(ram.available),
            "disk_percent": round(disk.percent, 1),
            "disk_free": bytes_to_human(disk.free),
            "disk_total": bytes_to_human(disk.total),
            "uptime": seconds_to_human(boot),
        }

        if detail_level == "detailed":
            data["cpu_per_core"] = [round(c, 1) for c in cpu_per_core]
            # Disk partitions
            disks = []
            for part in psutil.disk_partitions():
                try:
                    u = psutil.disk_usage(part.mountpoint)
                    disks.append({
                        "device": part.device,
                        "fstype": part.fstype,
                        "percent": round(u.percent, 1),
                        "free": bytes_to_human(u.free),
                        "total": bytes_to_human(u.total),
                    })
                except (PermissionError, OSError):
                    continue
            data["disk_partitions"] = disks

        message = (
            f"CPU: %{cpu:.1f} | RAM: %{ram.percent:.1f} ({bytes_to_human(ram.used)}/{bytes_to_human(ram.total)}) | "
            f"Disk: %{disk.percent:.1f} (Boş: {bytes_to_human(disk.free)}) | "
            f"Uptime: {seconds_to_human(boot)}"
        )

        return ToolResult(success=True, data=data, message=message)


# ═══════════════════════════════════════════════════
#  SÜREÇ YÖNETİMİ
# ═══════════════════════════════════════════════════

class ProcessListTool(BaseTool):
    """Çalışan süreçleri listele."""

    name = "process_list"
    description = "Çalışan süreçleri CPU ve RAM kullanımına göre listeler"
    description_en = "Lists running processes sorted by CPU and RAM usage"
    permission_level = PermissionLevel.AUTO
    parameters = [
        ToolParameter(
            name="sort_by",
            type="string",
            description="Sıralama kriteri: 'cpu' veya 'ram'",
            required=False,
            enum=["cpu", "ram"],
            default="cpu",
        ),
        ToolParameter(
            name="limit",
            type="integer",
            description="Gösterilecek süreç sayısı (max 30)",
            required=False,
            default=10,
        ),
    ]

    def execute(self, sort_by: str = "cpu", limit: int = 10, **kwargs) -> ToolResult:
        procs = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "status"]):
            try:
                info = proc.info
                mem = info.get("memory_info")
                procs.append({
                    "pid": info["pid"],
                    "name": info["name"] or "Unknown",
                    "cpu": round(info.get("cpu_percent", 0) or 0, 1),
                    "ram_bytes": mem.rss if mem else 0,
                    "ram": bytes_to_human(mem.rss) if mem else "0 B",
                    "status": info.get("status", ""),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        key = "cpu" if sort_by == "cpu" else "ram_bytes"
        procs.sort(key=lambda p: p.get(key, 0), reverse=True)
        limited = procs[:min(limit, 30)]

        lines = []
        for i, p in enumerate(limited, 1):
            lines.append(f"{i}. {p['name']} (PID:{p['pid']}) — CPU: %{p['cpu']}, RAM: {p['ram']}")

        return ToolResult(
            success=True,
            data={"processes": limited, "total_count": len(procs)},
            message="\n".join(lines),
        )


class ProcessKillTool(BaseTool):
    """Süreç sonlandır."""

    name = "process_kill"
    description = "Belirtilen süreci PID veya isimle sonlandırır"
    description_en = "Terminates a process by PID or name"
    permission_level = PermissionLevel.CONFIRM
    parameters = [
        ToolParameter(
            name="pid",
            type="integer",
            description="Sonlandırılacak sürecin PID numarası",
            required=False,
        ),
        ToolParameter(
            name="name",
            type="string",
            description="Sonlandırılacak sürecin adı (ör: chrome.exe)",
            required=False,
        ),
    ]

    def get_confirmation_message(self, **kwargs) -> str:
        pid = kwargs.get("pid")
        name = kwargs.get("name", "")
        if pid:
            try:
                proc = psutil.Process(int(pid))
                return f"'{proc.name()}' (PID: {pid}) sürecini sonlandırmak istediğinize emin misiniz?"
            except Exception:
                pass
        return f"'{name or pid}' sürecini sonlandırmak istediğinize emin misiniz?"

    def execute(self, pid: int = None, name: str = None, **kwargs) -> ToolResult:
        if pid:
            try:
                proc = psutil.Process(int(pid))
                proc_name = proc.name()
                proc.terminate()
                return ToolResult(
                    success=True,
                    message=f"'{proc_name}' (PID: {pid}) sonlandırıldı.",
                    data={"pid": pid, "name": proc_name},
                )
            except psutil.NoSuchProcess:
                return ToolResult(success=False, error=f"PID {pid} bulunamadı.")
            except psutil.AccessDenied:
                return ToolResult(success=False, error=f"PID {pid} için yetki yok.")
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        if name:
            killed = 0
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    if proc.info["name"] and proc.info["name"].lower() == name.lower():
                        proc.terminate()
                        killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if killed > 0:
                return ToolResult(
                    success=True,
                    message=f"'{name}' — {killed} süreç sonlandırıldı.",
                    data={"name": name, "killed_count": killed},
                )
            return ToolResult(success=False, error=f"'{name}' süreç bulunamadı.")

        return ToolResult(success=False, error="PID veya süreç adı belirtilmeli.")


# ═══════════════════════════════════════════════════
#  TEMİZLİK
# ═══════════════════════════════════════════════════

class CleanerTool(BaseTool):
    """Temp dosya temizliği."""

    name = "clean_temp"
    description = "Temp/geçici dosyaları temizleyerek disk alanı kazandırır"
    description_en = "Cleans temporary files to free up disk space"
    permission_level = PermissionLevel.CONFIRM
    parameters = [
        ToolParameter(
            name="mode",
            type="string",
            description="Temizlik modu: 'scan' sadece tara, 'clean' temizle",
            required=False,
            enum=["scan", "clean"],
            default="scan",
        ),
    ]

    def get_confirmation_message(self, **kwargs) -> str:
        return "Temp dosyaları temizlemek istediğinize emin misiniz?"

    def execute(self, mode: str = "scan", **kwargs) -> ToolResult:
        temp_dir = tempfile.gettempdir()
        files_found = 0
        total_size = 0
        cleaned = 0
        cleaned_size = 0

        for f in os.listdir(temp_dir):
            fp = os.path.join(temp_dir, f)
            try:
                if os.path.isfile(fp):
                    size = os.path.getsize(fp)
                    files_found += 1
                    total_size += size
                    if mode == "clean":
                        os.remove(fp)
                        cleaned += 1
                        cleaned_size += size
            except (PermissionError, OSError):
                continue

        data = {
            "temp_dir": temp_dir,
            "files_found": files_found,
            "total_size": bytes_to_human(total_size),
            "cleaned": cleaned,
            "cleaned_size": bytes_to_human(cleaned_size),
        }

        if mode == "scan":
            message = f"Temp dizininde {files_found} dosya bulundu ({bytes_to_human(total_size)}). Temizlemek için 'clean' modunu kullanın."
        else:
            message = f"Temizlik tamamlandı! {cleaned} dosya silindi, {bytes_to_human(cleaned_size)} alan kazanıldı."

        return ToolResult(success=True, data=data, message=message)


# ═══════════════════════════════════════════════════
#  PROFİL DEĞİŞTİRME
# ═══════════════════════════════════════════════════

class ProfileChangeTool(BaseTool):
    """Sistem profilini değiştir."""

    name = "change_profile"
    description = "Sistem profilini değiştirir (dengeli, oyun, iş, tasarruf)"
    description_en = "Changes system profile (balanced, gaming, work, power saver)"
    permission_level = PermissionLevel.NOTIFY
    parameters = [
        ToolParameter(
            name="profile",
            type="string",
            description="Hedef profil adı",
            required=True,
            enum=["balanced", "gaming", "work", "power_saver"],
        ),
    ]

    def execute(self, profile: str = "balanced", **kwargs) -> ToolResult:
        from blue_ai.core.config import get_profile
        from blue_ai.utils.win_api import set_power_scheme

        profile_data = get_profile(profile)
        if not profile_data:
            return ToolResult(success=False, error=f"Profil bulunamadı: {profile}")

        try:
            power_plan = profile_data.get("power_plan", "balanced")
            set_power_scheme(power_plan)
        except Exception:
            pass

        names = {
            "gaming": "🎮 Oyun Modu", "work": "💼 İş Modu",
            "power_saver": "🔋 Tasarruf Modu", "balanced": "⚖️ Dengeli Mod"
        }
        return ToolResult(
            success=True,
            message=f"{names.get(profile, profile)} aktif edildi!",
            data={"profile": profile, "settings": profile_data},
        )


# ═══════════════════════════════════════════════════
#  AĞ BİLGİSİ
# ═══════════════════════════════════════════════════

class NetworkInfoTool(BaseTool):
    """Ağ durumu bilgisi."""

    name = "network_info"
    description = "Ağ bağlantı durumunu, gönderilen/alınan veri miktarını gösterir"
    description_en = "Shows network connection status, sent/received data amounts"
    permission_level = PermissionLevel.AUTO
    parameters = []

    def execute(self, **kwargs) -> ToolResult:
        try:
            counters = psutil.net_io_counters()
            connections = len(psutil.net_connections(kind='inet'))
            data = {
                "bytes_sent": bytes_to_human(counters.bytes_sent),
                "bytes_recv": bytes_to_human(counters.bytes_recv),
                "packets_sent": counters.packets_sent,
                "packets_recv": counters.packets_recv,
                "active_connections": connections,
            }
            message = (
                f"Ağ Durumu:\n"
                f"  Gönderilen: {data['bytes_sent']} | Alınan: {data['bytes_recv']}\n"
                f"  Aktif Bağlantı: {connections}"
            )
            return ToolResult(success=True, data=data, message=message)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


# ═══════════════════════════════════════════════════
#  PİL BİLGİSİ
# ═══════════════════════════════════════════════════

class BatteryInfoTool(BaseTool):
    """Pil durumu."""

    name = "battery_info"
    description = "Pil durumunu ve şarj bilgisini gösterir"
    description_en = "Shows battery status and charging information"
    permission_level = PermissionLevel.AUTO
    parameters = []

    def execute(self, **kwargs) -> ToolResult:
        from blue_ai.utils.win_api import get_system_power_status
        power = get_system_power_status()
        if power.get("has_battery"):
            ac = "Şarjda" if power["ac_plugged"] else "Pilde"
            return ToolResult(
                success=True,
                data=power,
                message=f"Pil: %{power['battery_percent']} ({ac})",
            )
        return ToolResult(
            success=True,
            data={"has_battery": False},
            message="Bu cihazda pil bulunmuyor (masaüstü bilgisayar).",
        )


# ═══════════════════════════════════════════════════
#  DİSK BİLGİSİ
# ═══════════════════════════════════════════════════

class DiskInfoTool(BaseTool):
    """Disk kullanım bilgisi."""

    name = "disk_info"
    description = "Tüm disk bölümlerinin kullanım bilgisini gösterir"
    description_en = "Shows usage information for all disk partitions"
    permission_level = PermissionLevel.AUTO
    parameters = []

    def execute(self, **kwargs) -> ToolResult:
        disks = []
        lines = []
        for part in psutil.disk_partitions():
            try:
                u = psutil.disk_usage(part.mountpoint)
                disk_data = {
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "percent": round(u.percent, 1),
                    "used": bytes_to_human(u.used),
                    "total": bytes_to_human(u.total),
                    "free": bytes_to_human(u.free),
                }
                disks.append(disk_data)
                lines.append(
                    f"  {part.device}: %{u.percent:.0f} (Boş: {bytes_to_human(u.free)} / Toplam: {bytes_to_human(u.total)})"
                )
            except (PermissionError, OSError):
                continue

        return ToolResult(
            success=True,
            data={"disks": disks},
            message="Disk Bilgileri:\n" + "\n".join(lines),
        )


# ═══════════════════════════════════════════════════
#  RAM BİLGİSİ
# ═══════════════════════════════════════════════════

class RAMInfoTool(BaseTool):
    """Detaylı RAM bilgisi."""

    name = "ram_info"
    description = "Detaylı bellek (RAM) kullanım bilgisini gösterir"
    description_en = "Shows detailed memory (RAM) usage information"
    permission_level = PermissionLevel.AUTO
    parameters = []

    def execute(self, **kwargs) -> ToolResult:
        ram = psutil.virtual_memory()
        data = {
            "percent": round(ram.percent, 1),
            "used": bytes_to_human(ram.used),
            "total": bytes_to_human(ram.total),
            "available": bytes_to_human(ram.available),
            "cached": bytes_to_human(getattr(ram, 'cached', 0)),
        }
        return ToolResult(
            success=True,
            data=data,
            message=(
                f"RAM Durumu:\n"
                f"  Kullanım: %{ram.percent:.1f}\n"
                f"  Kullanılan: {data['used']} / Toplam: {data['total']}\n"
                f"  Kullanılabilir: {data['available']}"
            ),
        )


# ═══════════════════════════════════════════════════
#  UYGULAMA KONTROLÜ
# ═══════════════════════════════════════════════════

class OpenAppTool(BaseTool):
    """Uygulama aç."""

    name = "open_app"
    description = "Bilgisayardaki bir uygulamayı açar (chrome, notepad, explorer vb.)"
    description_en = "Opens an application on the computer (chrome, notepad, explorer, etc.)"
    permission_level = PermissionLevel.NOTIFY
    parameters = [
        ToolParameter(
            name="app_name",
            type="string",
            description="Açılacak uygulama adı (ör: chrome, notepad, word, excel, vscode, calculator, paint, explorer)",
            required=True,
        ),
        ToolParameter(
            name="args",
            type="string",
            description="Uygulamaya geçirilecek argümanlar (opsiyonel)",
            required=False,
            default="",
        ),
    ]

    def execute(self, app_name: str = "", args: str = "", **kwargs) -> ToolResult:
        from blue_ai.tools.app_control import open_application
        result = open_application(app_name, args)
        if result["success"]:
            return ToolResult(success=True, message=result["message"])
        return ToolResult(success=False, error=result.get("error", "Uygulama açılamadı"))


class CloseAppTool(BaseTool):
    """Uygulama kapat."""

    name = "close_app"
    description = "Çalışan bir uygulamayı kapatır"
    description_en = "Closes a running application"
    permission_level = PermissionLevel.CONFIRM
    parameters = [
        ToolParameter(
            name="app_name",
            type="string",
            description="Kapatılacak uygulama adı",
            required=True,
        ),
    ]

    def get_confirmation_message(self, **kwargs) -> str:
        return f"'{kwargs.get('app_name', '')}' uygulamasını kapatmak istediğinize emin misiniz?"

    def execute(self, app_name: str = "", **kwargs) -> ToolResult:
        from blue_ai.tools.app_control import close_application
        result = close_application(app_name)
        if result["success"]:
            return ToolResult(success=True, message=result["message"])
        return ToolResult(success=False, error=result.get("error", "Uygulama kapatılamadı"))


# ═══════════════════════════════════════════════════
#  WEB ARAMA
# ═══════════════════════════════════════════════════

class WebSearchTool(BaseTool):
    """Web'de arama yap."""

    name = "web_search"
    description = "Google'da arama yaparak sonuçları tarayıcıda açar"
    description_en = "Searches Google and opens results in browser"
    permission_level = PermissionLevel.NOTIFY
    parameters = [
        ToolParameter(
            name="query",
            type="string",
            description="Aranacak metin/konu",
            required=True,
        ),
    ]

    def execute(self, query: str = "", **kwargs) -> ToolResult:
        from blue_ai.tools.app_control import open_url
        if not query:
            return ToolResult(success=False, error="Arama sorgusu belirtilmeli.")
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        open_url(url)
        return ToolResult(
            success=True,
            message=f"Google'da aranıyor: '{query}'",
            data={"query": query, "url": url},
        )


# ═══════════════════════════════════════════════════
#  URL AÇ
# ═══════════════════════════════════════════════════

class OpenURLTool(BaseTool):
    """URL aç."""

    name = "open_url"
    description = "Belirtilen URL'yi varsayılan tarayıcıda açar"
    description_en = "Opens the specified URL in default browser"
    permission_level = PermissionLevel.NOTIFY
    parameters = [
        ToolParameter(
            name="url",
            type="string",
            description="Açılacak URL adresi",
            required=True,
        ),
    ]

    def execute(self, url: str = "", **kwargs) -> ToolResult:
        from blue_ai.tools.app_control import open_url
        if not url:
            return ToolResult(success=False, error="URL belirtilmeli.")
        result = open_url(url)
        if result["success"]:
            return ToolResult(success=True, message=result["message"])
        return ToolResult(success=False, error=result.get("error", "URL açılamadı"))


# ═══════════════════════════════════════════════════
#  DOSYA ARAMA
# ═══════════════════════════════════════════════════

class FileSearchTool(BaseTool):
    """Dosya arama."""

    name = "file_search"
    description = "Bilgisayarda dosya arar (isim, uzantı veya boyuta göre)"
    description_en = "Searches for files on the computer (by name, extension, or size)"
    permission_level = PermissionLevel.AUTO
    parameters = [
        ToolParameter(
            name="query",
            type="string",
            description="Aranacak dosya adı veya anahtar kelime",
            required=True,
        ),
        ToolParameter(
            name="search_dir",
            type="string",
            description="Aranacak dizin yolu (varsayılan: Kullanıcı dizini)",
            required=False,
        ),
        ToolParameter(
            name="max_results",
            type="integer",
            description="Maksimum sonuç sayısı",
            required=False,
            default=10,
        ),
    ]

    def execute(self, query: str = "", search_dir: str = None, max_results: int = 10, **kwargs) -> ToolResult:
        from blue_ai.tools.file_ops import find_files
        files = find_files(query, search_dir, max_results)
        if files:
            lines = [f"'{query}' için {len(files)} sonuç:"]
            for f in files:
                lines.append(f"  📄 {f['name']} — {f['size']} ({f['path']})")
            return ToolResult(
                success=True,
                data={"files": files, "count": len(files)},
                message="\n".join(lines),
            )
        return ToolResult(
            success=True,
            data={"files": [], "count": 0},
            message=f"'{query}' ile eşleşen dosya bulunamadı.",
        )


class LargeFilesTool(BaseTool):
    """Büyük dosyaları bul."""

    name = "find_large_files"
    description = "Büyük dosyaları bularak disk alanı kazanmaya yardımcı olur"
    description_en = "Finds large files to help free up disk space"
    permission_level = PermissionLevel.AUTO
    parameters = [
        ToolParameter(
            name="min_size_mb",
            type="integer",
            description="Minimum dosya boyutu (MB)",
            required=False,
            default=100,
        ),
        ToolParameter(
            name="directory",
            type="string",
            description="Aranacak dizin (varsayılan: Kullanıcı dizini)",
            required=False,
        ),
    ]

    def execute(self, min_size_mb: int = 100, directory: str = None, **kwargs) -> ToolResult:
        from blue_ai.tools.file_ops import get_large_files
        files = get_large_files(directory, min_size_mb)
        if files:
            lines = [f"{min_size_mb}MB üstü dosyalar:"]
            for f in files[:15]:
                lines.append(f"  📦 {f['name']} — {f['size']} ({f['path']})")
            return ToolResult(
                success=True,
                data={"files": files},
                message="\n".join(lines),
            )
        return ToolResult(
            success=True,
            data={"files": []},
            message=f"{min_size_mb}MB üstü dosya bulunamadı.",
        )


# ═══════════════════════════════════════════════════
#  BELGE OLUŞTURMA
# ═══════════════════════════════════════════════════

class CreateDocumentTool(BaseTool):
    """Word belgesi oluştur."""

    name = "create_document"
    description = "Belirtilen konuda Word belgesi (docx) oluşturur"
    description_en = "Creates a Word document (docx) on the specified topic"
    permission_level = PermissionLevel.NOTIFY
    parameters = [
        ToolParameter(
            name="topic",
            type="string",
            description="Belgenin konusu (ör: 'Proje raporu', 'Toplantı notları')",
            required=True,
        ),
    ]

    def execute(self, topic: str = "", **kwargs) -> ToolResult:
        from blue_ai.tools.document import create_word_document
        result = create_word_document(topic)
        if result["success"]:
            return ToolResult(
                success=True,
                message=f"Word belgesi oluşturuldu!\nDosya: {result['path']}",
                data=result,
            )
        return ToolResult(success=False, error=result.get("error", "Belge oluşturulamadı"))


class CreateSpreadsheetTool(BaseTool):
    """Excel tablosu oluştur."""

    name = "create_spreadsheet"
    description = "Belirtilen konuda Excel tablosu (xlsx) oluşturur"
    description_en = "Creates an Excel spreadsheet (xlsx) on the specified topic"
    permission_level = PermissionLevel.NOTIFY
    parameters = [
        ToolParameter(
            name="topic",
            type="string",
            description="Tablonun konusu",
            required=True,
        ),
    ]

    def execute(self, topic: str = "", **kwargs) -> ToolResult:
        from blue_ai.tools.document import create_excel_spreadsheet
        result = create_excel_spreadsheet(topic)
        if result["success"]:
            return ToolResult(
                success=True,
                message=f"Excel tablosu oluşturuldu!\nDosya: {result['path']}",
                data=result,
            )
        return ToolResult(success=False, error=result.get("error", "Tablo oluşturulamadı"))


class CreatePresentationTool(BaseTool):
    """PowerPoint sunumu oluştur."""

    name = "create_presentation"
    description = "Belirtilen konuda PowerPoint sunumu (pptx) oluşturur"
    description_en = "Creates a PowerPoint presentation (pptx) on the specified topic"
    permission_level = PermissionLevel.NOTIFY
    parameters = [
        ToolParameter(
            name="topic",
            type="string",
            description="Sunumun konusu",
            required=True,
        ),
    ]

    def execute(self, topic: str = "", **kwargs) -> ToolResult:
        from blue_ai.tools.document import create_presentation
        result = create_presentation(topic)
        if result["success"]:
            return ToolResult(
                success=True,
                message=f"PowerPoint sunumu oluşturuldu!\nDosya: {result['path']}",
                data=result,
            )
        return ToolResult(success=False, error=result.get("error", "Sunum oluşturulamadı"))


# ═══════════════════════════════════════════════════
#  YARDIM VE HAFIZA
# ═══════════════════════════════════════════════════

class MemorySaveTool(BaseTool):
    """Kullaniciyla alakali bir bilgiyi hafizaya kaydet."""

    name = "save_memory"
    description = "Kullanici hakkinda ogrenilen bir kisisel gercegi, tercihi veya bilgiyi uzun donem hafizaya kaydeder"
    description_en = "Saves a personal fact, preference or info learned about the user to long-term memory"
    permission_level = PermissionLevel.AUTO
    parameters = [
        ToolParameter(
            name="key",
            type="string",
            description="Bilginin kisa, tanimlayici anahtari (orn: 'Kullanici Adi', 'Dogum Tarihi', 'Favori Rengi')",
            required=True,
        ),
        ToolParameter(
            name="value",
            type="string",
            description="Kaydedilecek bilgi",
            required=True,
        ),
    ]

    def execute(self, key: str = "", value: str = "", **kwargs) -> ToolResult:
        from blue_ai.memory.manager import get_memory
        if not key or not value:
            return ToolResult(success=False, error="Key ve value bos olamaz.")
        success = get_memory().set_fact(key, value)
        if success:
            return ToolResult(
                success=True, 
                message=f"Hafizaya eklendi: {key} = {value}",
                data={"key": key, "value": value}
            )
        return ToolResult(success=False, error="Hafizaya kaydedilemedi.")

class HelpTool(BaseTool):
    """Yardım ve komut listesi."""

    name = "help"
    description = "BLUE AI'ın yapabileceklerini ve kullanılabilir komutları gösterir"
    description_en = "Shows what BLUE AI can do and available commands"
    permission_level = PermissionLevel.AUTO
    parameters = []

    def execute(self, **kwargs) -> ToolResult:
        from blue_ai.brain.tool_registry import get_registry
        registry = get_registry()
        return ToolResult(
            success=True,
            message=(
                "🔵 BLUE AI — Yapabileceklerim:\n\n"
                "📊 Sistem: 'Sistem durumu', 'CPU/RAM/Disk bilgisi'\n"
                "⚙️ Süreçler: 'Çalışan süreçler', 'Chrome'u kapat'\n"
                "🧹 Temizlik: 'Temp dosyaları temizle', 'Büyük dosyaları bul'\n"
                "🎮 Profil: 'Oyun moduna geç', 'Tasarruf modu'\n"
                "📁 Dosya: 'Rapor dosyasını bul', 'Masaüstünü listele'\n"
                "📄 Belge: 'Word belgesi hazırla', 'Excel tablosu oluştur'\n"
                "🚀 Uygulama: 'Chrome aç', 'Notepad aç'\n"
                "🌐 Web: 'Hava durumunu ara', 'Python öğren'\n"
                "🔋 Pil: 'Pil durumu'\n"
                "💬 Genel: Herhangi bir sorunuzu sorabilirsiniz!\n"
                f"\nToplam {registry.count} araç kullanılabilir."
            ),
        )


# ═══════════════════════════════════════════════════
#  KAYIT FONKSİYONU
# ═══════════════════════════════════════════════════

class VolumeControlTool(BaseTool):
    """Sistem ses seviyesini ayarlar."""

    name = "change_volume"
    description = "Bilgisayarin ana ses seviyesini ayarlar (0 ile 100 arasinda)"
    description_en = "Adjusts the main system volume (between 0 and 100)"
    permission_level = PermissionLevel.NOTIFY
    parameters = [
        ToolParameter(
            name="level",
            type="integer",
            description="Ses seviyesi yuzdesi (1 ile 100 arasinda)",
            required=True,
        ),
    ]

    def execute(self, level: int = 50, **kwargs) -> ToolResult:
        try:
            import pythoncom
            from pycaw.pycaw import AudioUtilities

            pythoncom.CoInitialize()
            devices = AudioUtilities.GetSpeakers()
            volume = devices.EndpointVolume

            if isinstance(level, str):
                level = level.replace('%', '').strip()

            level = max(0, min(100, int(level)))
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)

            return ToolResult(
                success=True,
                message=f"Ses seviyesi %{level} olarak ayarlandı.",
                data={"volume": level}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


# ═══════════════════════════════════════════════════
#  STT MOTOR DEGISTİRICİ
# ═══════════════════════════════════════════════════

class SwitchSTTTool(BaseTool):
    """Ses tanıma motorunu Vosk veya Whisper olarak değiştirir."""

    name = "switch_stt_engine"
    description = "Ses tanıma motorunu değiştirir: vosk (offline, hızlı) veya whisper (yüksek doğruluk)"
    description_en = "Switch speech recognition engine: vosk (offline, fast) or whisper (high accuracy)"
    permission_level = PermissionLevel.NOTIFY
    parameters = [
        ToolParameter(
            name="engine",
            type="string",
            description="Kullanılacak motor: 'vosk' veya 'whisper'",
            required=True,
            enum=["vosk", "whisper"],
        ),
    ]

    def execute(self, engine: str = "vosk", **kwargs) -> ToolResult:
        engine = engine.lower().strip()
        if engine not in ("vosk", "whisper"):
            return ToolResult(success=False, error=f"Geçersiz motor: '{engine}'. 'vosk' veya 'whisper' olmalı.")

        try:
            import os, re
            cfg_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "config", "blue_ai.toml"
            )
            # Config dosyasını oku ve stt_engine satırını değiştir
            with open(cfg_path, "r", encoding="utf-8") as f:
                content = f.read()

            new_content = re.sub(
                r'(stt_engine\s*=\s*)"[^"]*"',
                f'stt_engine = "{engine}"',
                content
            )
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            # STT singleton'ı sıfırla — bir sonraki kullanımda yeni motor yüklenecek
            try:
                import blue_ai.voice.stt as stt_module
                stt_module._stt = None
            except Exception:
                pass

            engine_name = "Vosk (offline, hızlı)" if engine == "vosk" else "Whisper (yüksek doğruluk)"
            return ToolResult(
                success=True,
                message=f"Ses tanıma motoru '{engine_name}' olarak değiştirildi. Mikrofon düğmesine bir sonraki basışta aktif olacak.",
                data={"engine": engine}
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Motor değiştirilemedi: {str(e)}")


# ═══════════════════════════════════════════════════
#  EKRAN GÖRÜNTÜSÜ
# ═══════════════════════════════════════════════════

class ScreenshotTool(BaseTool):
    """Ekran görüntüsü al."""

    name = "take_screenshot"
    description = "Ekran görüntüsü alır ve masaüstüne kaydeder"
    description_en = "Takes a screenshot and saves to desktop"
    permission_level = PermissionLevel.NOTIFY
    parameters = []

    def execute(self, **kwargs) -> ToolResult:
        try:
            import subprocess
            from datetime import datetime
            desktop = Path.home() / "Desktop"
            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = desktop / filename

            # PowerShell ile ekran görüntüsü al
            ps_cmd = f"""
Add-Type -AssemblyName System.Windows.Forms
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
$bitmap.Save('{filepath}')
$graphics.Dispose()
$bitmap.Dispose()
"""
            subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, timeout=10)
            return ToolResult(
                success=True,
                message=f"Ekran görüntüsü kaydedildi: {filepath}",
                data={"path": str(filepath)},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


# ═══════════════════════════════════════════════════
#  SİSTEM KAPATMA / YENİDEN BAŞLATMA
# ═══════════════════════════════════════════════════

class ShutdownTool(BaseTool):
    """Bilgisayarı kapat."""

    name = "shutdown_pc"
    description = "Bilgisayarı kapatır (30 saniye gecikmeli)"
    description_en = "Shuts down the computer (30 second delay)"
    permission_level = PermissionLevel.CONFIRM
    parameters = [
        ToolParameter(
            name="delay",
            type="integer",
            description="Kapanmadan önceki gecikme (saniye, varsayılan 30)",
            required=False,
            default=30,
        ),
    ]

    def get_confirmation_message(self, **kwargs) -> str:
        delay = kwargs.get("delay", 30)
        return f"Bilgisayar {delay} saniye sonra kapanacak. Emin misiniz?"

    def execute(self, delay: int = 30, **kwargs) -> ToolResult:
        try:
            os.system(f"shutdown /s /t {delay}")
            return ToolResult(
                success=True,
                message=f"Bilgisayar {delay} saniye sonra kapanacak. İptal: 'shutdown /a'",
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class RestartTool(BaseTool):
    """Bilgisayarı yeniden başlat."""

    name = "restart_pc"
    description = "Bilgisayarı yeniden başlatır (30 saniye gecikmeli)"
    description_en = "Restarts the computer (30 second delay)"
    permission_level = PermissionLevel.CONFIRM
    parameters = [
        ToolParameter(
            name="delay",
            type="integer",
            description="Yeniden başlatmadan önceki gecikme (saniye, varsayılan 30)",
            required=False,
            default=30,
        ),
    ]

    def get_confirmation_message(self, **kwargs) -> str:
        delay = kwargs.get("delay", 30)
        return f"Bilgisayar {delay} saniye sonra yeniden başlayacak. Emin misiniz?"

    def execute(self, delay: int = 30, **kwargs) -> ToolResult:
        try:
            os.system(f"shutdown /r /t {delay}")
            return ToolResult(
                success=True,
                message=f"Bilgisayar {delay} saniye sonra yeniden başlayacak. İptal: 'shutdown /a'",
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class LockScreenTool(BaseTool):
    """Ekranı kilitle."""

    name = "lock_screen"
    description = "Bilgisayar ekranını kilitler"
    description_en = "Locks the computer screen"
    permission_level = PermissionLevel.NOTIFY
    parameters = []

    def execute(self, **kwargs) -> ToolResult:
        try:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return ToolResult(success=True, message="Ekran kilitlendi.")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


# ═══════════════════════════════════════════════════
#  SAAT / HATIRLATICI
# ═══════════════════════════════════════════════════

class ShowTimeTool(BaseTool):
    """Tarih ve saat göster."""

    name = "show_time"
    description = "Güncel tarih ve saati gösterir"
    description_en = "Shows current date and time"
    permission_level = PermissionLevel.AUTO
    parameters = []

    def execute(self, **kwargs) -> ToolResult:
        from datetime import datetime
        now = datetime.now()
        gun_isimleri = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        ay_isimleri = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                       "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        gun = gun_isimleri[now.weekday()]
        ay = ay_isimleri[now.month]
        return ToolResult(
            success=True,
            message=f"🕐 Saat: {now.strftime('%H:%M:%S')}\n📅 Tarih: {now.day} {ay} {now.year}, {gun}",
            data={"time": now.strftime("%H:%M:%S"), "date": now.strftime("%d.%m.%Y"), "day": gun},
        )


class SetReminderTool(BaseTool):
    """Hatırlatıcı kur."""

    name = "set_reminder"
    description = "Belirtilen süre sonra hatırlatıcı kurar (dakika cinsinden)"
    description_en = "Sets a reminder after specified minutes"
    permission_level = PermissionLevel.NOTIFY
    parameters = [
        ToolParameter(
            name="message",
            type="string",
            description="Hatırlatılacak mesaj",
            required=True,
        ),
        ToolParameter(
            name="minutes",
            type="integer",
            description="Kaç dakika sonra hatırlatılsın (varsayılan 5)",
            required=False,
            default=5,
        ),
    ]

    def execute(self, message: str = "", minutes: int = 5, **kwargs) -> ToolResult:
        import threading
        if not message:
            return ToolResult(success=False, error="Hatırlatma mesajı belirtilmeli.")

        def _remind():
            import time as _time
            _time.sleep(minutes * 60)
            # Windows toast bildirimi
            try:
                from ctypes import windll
                windll.user32.MessageBoxW(0, message, "BLUE AI Hatırlatıcı", 0x40)
            except Exception:
                print(f"\n🔔 HATIRLATMA: {message}")

        t = threading.Thread(target=_remind, daemon=True)
        t.start()

        return ToolResult(
            success=True,
            message=f"✅ Hatırlatıcı kuruldu! {minutes} dakika sonra: '{message}'",
            data={"message": message, "minutes": minutes},
        )


# ═══════════════════════════════════════════════════
#  WHATSAPP (Web üzerinden)
# ═══════════════════════════════════════════════════

class WhatsAppSendTool(BaseTool):
    """WhatsApp Web üzerinden mesaj gönder."""

    name = "whatsapp_send"
    description = "WhatsApp Web üzerinden belirtilen kişiye mesaj gönderir"
    description_en = "Sends a message via WhatsApp Web to the specified contact"
    permission_level = PermissionLevel.CONFIRM
    parameters = [
        ToolParameter(
            name="phone",
            type="string",
            description="Telefon numarası (ülke kodu ile, ör: 905551234567) veya kişi adı",
            required=True,
        ),
        ToolParameter(
            name="message",
            type="string",
            description="Gönderilecek mesaj",
            required=True,
        ),
    ]

    def get_confirmation_message(self, **kwargs) -> str:
        phone = kwargs.get("phone", "")
        msg = kwargs.get("message", "")[:50]
        return f"WhatsApp ile '{phone}' kişisine mesaj göndermek istediğinize emin misiniz?\nMesaj: {msg}..."

    def execute(self, phone: str = "", message: str = "", **kwargs) -> ToolResult:
        from blue_ai.tools.app_control import open_url
        from urllib.parse import quote

        if not phone or not message:
            return ToolResult(success=False, error="Telefon numarası ve mesaj gerekli.")

        # Sadece rakam bırak
        phone_clean = "".join(c for c in phone if c.isdigit())
        if not phone_clean:
            # Kişi adı girilmiş olabilir — direkt WhatsApp Web aç
            open_url("https://web.whatsapp.com")
            return ToolResult(
                success=True,
                message=f"WhatsApp Web açıldı. '{phone}' kişisini bulup mesajı gönderebilirsiniz.",
            )

        # wa.me linki ile mesaj gönder
        wa_url = f"https://wa.me/{phone_clean}?text={quote(message)}"
        open_url(wa_url)
        return ToolResult(
            success=True,
            message=f"WhatsApp Web açıldı — '{phone_clean}' kişisine mesaj hazırlandı.",
            data={"phone": phone_clean, "message": message[:100]},
        )


# ═══════════════════════════════════════════════════
#  GMAIL (Web üzerinden)
# ═══════════════════════════════════════════════════

class GmailSendTool(BaseTool):
    """Gmail üzerinden e-posta gönder."""

    name = "gmail_send"
    description = "Gmail üzerinden e-posta hazırlar ve tarayıcıda açar"
    description_en = "Prepares an email via Gmail and opens in browser"
    permission_level = PermissionLevel.CONFIRM
    parameters = [
        ToolParameter(
            name="to",
            type="string",
            description="Alıcı e-posta adresi",
            required=True,
        ),
        ToolParameter(
            name="subject",
            type="string",
            description="E-posta konusu",
            required=True,
        ),
        ToolParameter(
            name="body",
            type="string",
            description="E-posta içeriği",
            required=False,
            default="",
        ),
    ]

    def get_confirmation_message(self, **kwargs) -> str:
        to = kwargs.get("to", "")
        subj = kwargs.get("subject", "")
        return f"Gmail'de '{to}' adresine '{subj}' konulu e-posta hazırlanacak. Emin misiniz?"

    def execute(self, to: str = "", subject: str = "", body: str = "", **kwargs) -> ToolResult:
        from blue_ai.tools.app_control import open_url
        from urllib.parse import quote

        if not to:
            return ToolResult(success=False, error="Alıcı e-posta adresi gerekli.")

        gmail_url = f"https://mail.google.com/mail/?view=cm&to={quote(to)}&su={quote(subject)}&body={quote(body)}"
        open_url(gmail_url)
        return ToolResult(
            success=True,
            message=f"Gmail açıldı — '{to}' adresine e-posta hazırlandı.",
            data={"to": to, "subject": subject},
        )


class GmailReadTool(BaseTool):
    """Gmail gelen kutusunu aç."""

    name = "gmail_read"
    description = "Gmail gelen kutusunu tarayıcıda açar"
    description_en = "Opens Gmail inbox in browser"
    permission_level = PermissionLevel.NOTIFY
    parameters = []

    def execute(self, **kwargs) -> ToolResult:
        from blue_ai.tools.app_control import open_url
        open_url("https://mail.google.com/mail/u/0/#inbox")
        return ToolResult(
            success=True,
            message="Gmail gelen kutusu açıldı.",
        )


# ═══════════════════════════════════════════════════
#  GELİŞMİŞ WEB ARAMA (gerçek scraping)
# ═══════════════════════════════════════════════════

class WeatherTool(BaseTool):
    """Hava durumu sorgulama — wttr.in üzerinden, API key gerekmez."""

    name = "get_weather"
    description = "Belirtilen şehrin hava durumunu internet üzerinden getirir"
    description_en = "Fetches current weather for a city from the internet"
    permission_level = PermissionLevel.AUTO
    parameters = [
        ToolParameter(
            name="city",
            type="string",
            description="Şehir adı (Türkçe veya İngilizce, örn: Istanbul, Ankara)",
            required=True,
        ),
    ]

    # Hava durumu açıklamaları (İngilizce → Türkçe)
    _WEATHER_DESC_TR = {
        "Sunny": "Güneşli", "Clear": "Açık", "Partly cloudy": "Parçalı bulutlu",
        "Cloudy": "Bulutlu", "Overcast": "Kapalı", "Mist": "Sisli",
        "Fog": "Yoğun sis", "Light rain": "Hafif yağmurlu",
        "Moderate rain": "Orta yağmurlu", "Heavy rain": "Yoğun yağmurlu",
        "Light snow": "Hafif karlı", "Moderate snow": "Orta karlı",
        "Heavy snow": "Yoğun karlı", "Thundery outbreaks": "Gök gürültülü",
        "Blizzard": "Tipi", "Sleet": "Karla karışık yağmur",
        "Patchy rain": "Dağınık yağmurlu", "Patchy snow": "Dağınık karlı",
        "Light drizzle": "Hafif çisenti", "Freezing drizzle": "Dondurucu çisenti",
        "Light sleet": "Hafif karla karışık", "Thunder": "Gök gürültüsü",
    }

    def _tr_desc(self, en: str) -> str:
        """İngilizce hava durumunu Türkçeye çevir."""
        for key, val in self._WEATHER_DESC_TR.items():
            if key.lower() in en.lower():
                return val
        return en

    def execute(self, city: str = "Istanbul", **kwargs) -> ToolResult:
        if not city or len(city.strip()) < 2:
            city = "Istanbul"
        city_clean = (city.strip()
                      .replace("İ", "I").replace("ı", "i")
                      .replace("ğ", "g").replace("Ğ", "G")
                      .replace("ü", "u").replace("Ü", "U")
                      .replace("ş", "s").replace("Ş", "S")
                      .replace("ö", "o").replace("Ö", "O")
                      .replace("ç", "c").replace("Ç", "C"))
        try:
            import requests
            headers = {"User-Agent": "curl/7.68.0"}  # lang=tr bazen 500 verir → kaldırıldı

            # İlk deneme: lang=tr ile
            url = f"https://wttr.in/{city_clean}?format=j1&lang=tr"
            resp = requests.get(url, timeout=10, headers=headers)

            # lang=tr 500 verirse dil parametresiz tekrar dene
            if resp.status_code == 500:
                url = f"https://wttr.in/{city_clean}?format=j1"
                resp = requests.get(url, timeout=10, headers=headers)

            if resp.status_code != 200:
                return ToolResult(
                    success=False,
                    error=f"'{city}' için hava durumu bulunamadı. Şehir adını kontrol edin."
                )

            data = resp.json()
            current = data["current_condition"][0]
            area = data["nearest_area"][0]
            area_name = area["areaName"][0]["value"]
            country = area["country"][0]["value"]
            temp_c = current["temp_C"]
            feels = current["FeelsLikeC"]
            humidity = current["humidity"]
            wind_kmph = current["windspeedKmph"]

            # Açıklama: lang_tr varsa kullan, yoksa İngilizce'yi çevir
            desc_list = current.get("lang_tr") or current.get("weatherDesc", [{}])
            en_desc = (current.get("weatherDesc") or [{}])[0].get("value", "")
            raw_desc = desc_list[0].get("value", en_desc) if desc_list else en_desc
            desc = raw_desc if raw_desc else self._tr_desc(en_desc)

            forecast_lines = []
            for day in data.get("weather", [])[:3]:
                date = day["date"]
                max_c = day["maxtempC"]
                min_c = day["mintempC"]
                hourly = day.get("hourly", [{}])
                day_desc = ""
                if hourly:
                    mid = hourly[len(hourly) // 2]
                    dl = mid.get("lang_tr") or mid.get("weatherDesc", [{}])
                    en_d = (mid.get("weatherDesc") or [{}])[0].get("value", "")
                    raw_d = dl[0].get("value", en_d) if dl else en_d
                    day_desc = raw_d if raw_d else self._tr_desc(en_d)
                forecast_lines.append(f"  {date}: {min_c}°C – {max_c}°C  {day_desc}")

            msg = (
                f"🌍 {area_name}, {country}\n"
                f"🌡️ Sıcaklık: {temp_c}°C  (Hissedilen: {feels}°C)\n"
                f"☁️ Durum: {desc}\n"
                f"💧 Nem: {humidity}%  |  💨 Rüzgar: {wind_kmph} km/s\n\n"
                f"📅 3 Günlük Tahmin:\n" + "\n".join(forecast_lines)
            )
            return ToolResult(
                success=True, message=msg,
                data={"city": area_name, "temp": temp_c, "desc": desc}
            )
        except Exception as e:
            if "Timeout" in type(e).__name__ or "timeout" in str(e).lower():
                return ToolResult(success=False, error="Hava durumu sunucusu yanıt vermedi.")
            if "Connection" in type(e).__name__:
                return ToolResult(success=False, error="İnternet bağlantısı yok.")
            return ToolResult(success=False, error=f"Hava durumu hatası: {str(e)}")


class SmartWebSearchTool(BaseTool):
    """Gelişmiş web araması — sonuçları doğrudan gösterir."""

    name = "smart_web_search"
    description = "İnternette arama yapar ve sonuçları doğrudan metin olarak gösterir (tarayıcı açmadan)"
    description_en = "Searches the web and shows results as text (without opening browser)"
    permission_level = PermissionLevel.AUTO
    parameters = [
        ToolParameter(
            name="query",
            type="string",
            description="Aranacak konu veya soru",
            required=True,
        ),
        ToolParameter(
            name="max_results",
            type="integer",
            description="Maksimum sonuç sayısı (varsayılan 5)",
            required=False,
            default=5,
        ),
    ]

    def execute(self, query: str = "", max_results: int = 5, **kwargs) -> ToolResult:
        if not query:
            return ToolResult(success=False, error="Arama sorgusu belirtilmeli.")

        try:
            from blue_ai.tools.web_search import search_web
            results = search_web(query, max_results)

            if not results or (len(results) == 1 and results[0].get("title") == "Hata"):
                error_msg = results[0].get("snippet", "") if results else "Sonuç bulunamadı"
                return ToolResult(success=False, error=error_msg)

            lines = []
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. {r['title']}")
                if r.get("snippet"):
                    lines.append(f"   {r['snippet']}")
                if r.get("url"):
                    lines.append(f"   🔗 {r['url']}")
                lines.append("")

            return ToolResult(
                success=True,
                data={"results": results, "query": query},
                message=f"'{query}' için {len(results)} sonuç:\n\n" + "\n".join(lines),
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Arama hatası: {str(e)}")


# ═══════════════════════════════════════════════════
#  KAYIT FONKSİYONU
# ═══════════════════════════════════════════════════

def register_all_tools() -> None:
    """Tüm sistem tool'larını registry'e kaydet."""
    from blue_ai.brain.tool_registry import get_registry
    registry = get_registry()

    tools = [
        # Sistem bilgi
        SystemStatusTool(),
        ProcessListTool(),
        ProcessKillTool(),
        CleanerTool(),
        ProfileChangeTool(),
        NetworkInfoTool(),
        BatteryInfoTool(),
        DiskInfoTool(),
        RAMInfoTool(),
        # Uygulama kontrolü
        OpenAppTool(),
        CloseAppTool(),
        # Web & Hava durumu
        WeatherTool(),
        WebSearchTool(),
        SmartWebSearchTool(),
        OpenURLTool(),
        # Dosya
        FileSearchTool(),
        LargeFilesTool(),
        # Belge
        CreateDocumentTool(),
        CreateSpreadsheetTool(),
        CreatePresentationTool(),
        # Hafıza & yardım
        MemorySaveTool(),
        HelpTool(),
        # Sistem kontrol
        VolumeControlTool(),
        SwitchSTTTool(),
        ScreenshotTool(),
        ShutdownTool(),
        RestartTool(),
        LockScreenTool(),
        # Zaman
        ShowTimeTool(),
        SetReminderTool(),
        # İletişim
        WhatsAppSendTool(),
        GmailSendTool(),
        GmailReadTool(),
    ]

    for tool in tools:
        registry.register(tool)

