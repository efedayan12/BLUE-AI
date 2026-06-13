"""
BLUE_AI — Uygulama Kontrolu

Uygulamalari acma, kapatma ve yonetme.
Bilinen uygulamalar + otomatik arama (Start Menu, Program Files, Registry, PATH).
"""

import subprocess
import os
import glob
from pathlib import Path


# Bilinen uygulamalar — hizli erişim
APP_MAP = {
    "chrome": {"exe": "chrome.exe", "path": r"C:\Program Files\Google\Chrome\Application\chrome.exe"},
    "firefox": {"exe": "firefox.exe", "path": r"C:\Program Files\Mozilla Firefox\firefox.exe"},
    "edge": {"exe": "msedge.exe", "path": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"},
    "opera": {"exe": "opera.exe", "path": None},
    "brave": {"exe": "brave.exe", "path": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"},
    "word": {"exe": "WINWORD.EXE", "path": None},
    "winword": {"exe": "WINWORD.EXE", "path": None},
    "excel": {"exe": "EXCEL.EXE", "path": None},
    "powerpoint": {"exe": "POWERPNT.EXE", "path": None},
    "outlook": {"exe": "OUTLOOK.EXE", "path": None},
    "notepad": {"exe": "notepad.exe", "path": r"C:\Windows\notepad.exe"},
    "not defteri": {"exe": "notepad.exe", "path": r"C:\Windows\notepad.exe"},
    "notdefteri": {"exe": "notepad.exe", "path": r"C:\Windows\notepad.exe"},
    "notepad++": {"exe": "notepad++.exe", "path": r"C:\Program Files\Notepad++\notepad++.exe"},
    "calc": {"exe": "calc.exe", "path": r"C:\Windows\System32\calc.exe"},
    "hesap makinesi": {"exe": "calc.exe", "path": r"C:\Windows\System32\calc.exe"},
    "explorer": {"exe": "explorer.exe", "path": r"C:\Windows\explorer.exe"},
    "dosya gezgini": {"exe": "explorer.exe", "path": r"C:\Windows\explorer.exe"},
    "cmd": {"exe": "cmd.exe", "path": r"C:\Windows\System32\cmd.exe"},
    "powershell": {"exe": "powershell.exe", "path": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"},
    "paint": {"exe": "mspaint.exe", "path": r"C:\Windows\System32\mspaint.exe"},
    "vscode": {"exe": "Code.exe", "path": None},
    "vs code": {"exe": "Code.exe", "path": None},
    "visual studio code": {"exe": "Code.exe", "path": None},
    "spotify": {"exe": "Spotify.exe", "path": None},
    "discord": {"exe": "Discord.exe", "path": None},
    "steam": {"exe": "steam.exe", "path": r"C:\Program Files (x86)\Steam\steam.exe"},
    "whatsapp": {"exe": "WhatsApp.exe", "path": None},
    "telegram": {"exe": "Telegram.exe", "path": None},
    "vlc": {"exe": "vlc.exe", "path": r"C:\Program Files\VideoLAN\VLC\vlc.exe"},
    "task manager": {"exe": "Taskmgr.exe", "path": r"C:\Windows\System32\Taskmgr.exe"},
    "görev yöneticisi": {"exe": "Taskmgr.exe", "path": r"C:\Windows\System32\Taskmgr.exe"},
    "settings": {"exe": "ms-settings:", "path": None},
    "ayarlar": {"exe": "ms-settings:", "path": None},
    "snipping tool": {"exe": "SnippingTool.exe", "path": None},
    "ekran alıntısı": {"exe": "SnippingTool.exe", "path": None},
}


def _resolve_via_app_paths(exe_name: str) -> str | None:
    """Windows 'App Paths' registry'sinden exe'nin tam yolunu çöz.

    Office (WINWORD.EXE, EXCEL.EXE), tarayıcılar vb. genelde PATH'te DEĞİLDİR ama
    'App Paths' altında kayıtlıdır. Bu yüzden Word/Excel ilk denemede açılır.
    """
    if not exe_name.lower().endswith(".exe"):
        exe_name += ".exe"
    try:
        import winreg
        sub = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\\" + exe_name
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    key = winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | view)
                    val, _ = winreg.QueryValueEx(key, "")
                    winreg.CloseKey(key)
                    val = (val or "").strip('"')
                    if val and os.path.exists(val):
                        return val
                except (FileNotFoundError, OSError):
                    continue
    except Exception:
        pass
    return None


def _find_app_smart(app_name: str) -> str | None:
    """
    Uygulamayı akıllı arama ile bul.
    Sıra: PATH → Registry → Start Menu → Program Files
    """
    name_lower = app_name.lower().strip()
    # .exe uzantısı yoksa ekle (arama için)
    search_name = name_lower if name_lower.endswith(".exe") else name_lower + ".exe"
    display_name = name_lower.replace(".exe", "")

    # 1. PATH'de ara (where komutu)
    try:
        result = subprocess.run(
            ["where", search_name], capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            path = result.stdout.strip().splitlines()[0]
            if os.path.exists(path):
                return path
    except Exception:
        pass

    # 2. Windows Registry — App Paths
    try:
        import winreg
        reg_paths = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths",
        ]
        for reg_path in reg_paths:
            for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                try:
                    key = winreg.OpenKey(hive, reg_path)
                    count = winreg.QueryInfoKey(key)[0]
                    for i in range(count):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            if display_name in subkey_name.lower():
                                subkey = winreg.OpenKey(key, subkey_name)
                                exe_path, _ = winreg.QueryValueEx(subkey, "")
                                exe_path = exe_path.strip('"')
                                if os.path.exists(exe_path):
                                    return exe_path
                        except Exception:
                            continue
                    winreg.CloseKey(key)
                except Exception:
                    pass
    except Exception:
        pass

    # 3. Start Menu kısayolları — .lnk dosyaları
    start_menu_dirs = [
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu"),
    ]
    for smd in start_menu_dirs:
        if not os.path.exists(smd):
            continue
        for lnk in glob.glob(os.path.join(smd, "**", "*.lnk"), recursive=True):
            lnk_lower = os.path.basename(lnk).lower().replace(".lnk", "")
            if display_name in lnk_lower or lnk_lower in display_name:
                # .lnk hedefini çöz
                try:
                    import pythoncom
                    from win32com.client import Dispatch
                    pythoncom.CoInitialize()
                    shell = Dispatch("WScript.Shell")
                    shortcut = shell.CreateShortCut(lnk)
                    target = shortcut.Targetpath
                    if target and os.path.exists(target):
                        return target
                except Exception:
                    # .lnk çözülemediyse .lnk kendisini döndür
                    return lnk

    # 4. Program Files klasörlerinde ara
    pf_dirs = [
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        os.path.expandvars(r"%LOCALAPPDATA%"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs"),
    ]
    for pf in pf_dirs:
        if not os.path.exists(pf):
            continue
        # Önce doğrudan alt klasörlerde ara (çok hızlı)
        try:
            for folder in os.listdir(pf):
                if display_name in folder.lower():
                    folder_path = os.path.join(pf, folder)
                    if os.path.isdir(folder_path):
                        # Bu klasörde exe ara
                        for f in os.listdir(folder_path):
                            if f.lower().endswith(".exe") and display_name in f.lower():
                                return os.path.join(folder_path, f)
                        # İlk .exe bul (büyük ihtimalle ana exe)
                        for f in os.listdir(folder_path):
                            if f.lower().endswith(".exe"):
                                return os.path.join(folder_path, f)
        except Exception:
            pass

    return None


def open_application(app_name: str, args: str = "") -> dict:
    """Uygulama ac — akıllı arama ile."""
    original_name = app_name.strip()
    name_lower = original_name.lower()

    # 1. APP_MAP'te ara
    exe_path = None
    display = original_name

    if name_lower in APP_MAP:
        info = APP_MAP[name_lower]
        candidate = info["path"]
        if candidate and os.path.exists(candidate):
            exe_path = candidate
        else:
            # PATH'te olmayabilir → önce App Paths registry'sinden çöz (Word/Excel için kritik)
            exe_path = _resolve_via_app_paths(info["exe"]) or info["exe"]
        display = name_lower
    else:
        # 2. APP_MAP'te kısmi eşleşme
        for key, info in APP_MAP.items():
            if name_lower in key or key in name_lower:
                candidate = info["path"]
                if candidate and os.path.exists(candidate):
                    exe_path = candidate
                    display = key
                    break
                else:
                    exe_path = _resolve_via_app_paths(info["exe"]) or info["exe"]
                    display = key
                    break

    # 3. Akıllı arama (Registry, Start Menu, Program Files)
    if exe_path is None:
        found = _find_app_smart(name_lower)
        if found:
            exe_path = found
            display = original_name

    # 4. Direkt isimle dene (PATH'de veya .exe ise)
    if exe_path is None:
        exe_path = original_name

    # Aç
    try:
        cmd = [exe_path]
        if args:
            cmd.append(args)
        subprocess.Popen(cmd, shell=True)
        return {"success": True, "message": f"{display} açıldı."}
    except Exception:
        # Windows start komutuyla dene
        try:
            arg_str = f' "{args}"' if args else ""
            os.system(f'start "" "{exe_path}"{arg_str}')
            return {"success": True, "message": f"{display} açıldı."}
        except Exception as e:
            return {
                "success": False,
                "error": f"'{original_name}' bulunamadı veya açılamadı. "
                         f"Uygulama yüklü mü? ({str(e)})"
            }


def open_url(url: str) -> dict:
    """URL ac."""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        os.system(f'start "" "{url}"')
        return {"success": True, "message": f"Acildi: {url}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def close_application(app_name: str) -> dict:
    """Uygulama kapat."""
    name_lower = app_name.lower().strip()
    if name_lower in APP_MAP:
        exe = APP_MAP[name_lower]["exe"]
    else:
        exe = app_name
        if not exe.lower().endswith(".exe"):
            exe = exe + ".exe"

    try:
        result = subprocess.run(
            ["taskkill", "/IM", exe, "/F"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return {"success": True, "message": f"{app_name} kapatıldı."}
        # Process adı ile bulunamadıysa kısmi eşleşme ile dene
        os.system(f'taskkill /IM "*{name_lower}*" /F 2>nul')
        return {"success": True, "message": f"{app_name} kapatıldı."}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Not defterine yazma ──────────────────────────────────────────────────────
def _notes_file() -> Path:
    """Kalıcı not defteri dosyasının yolu (Belgeler/BLUE_AI)."""
    notes_dir = Path.home() / "Documents" / "BLUE_AI"
    notes_dir.mkdir(parents=True, exist_ok=True)
    return notes_dir / "blue_not_defteri.txt"


def write_to_notepad(text: str, append: bool = True, open_after: bool = True) -> dict:
    """Verilen metni bir not dosyasına yazar ve Not Defteri'nde (Notepad) açar.

    append=True  → mevcut nota EKLER (söylenenleri biriktirir, eski not kaybolmaz)
    append=False → temiz/yeni dosya
    Dosya: ~/Documents/BLUE_AI/blue_not_defteri.txt
    """
    try:
        text = (text or "").strip()
        if not text:
            return {"success": False, "error": "Yazılacak metin boş."}

        note_path = _notes_file()

        if append and note_path.exists():
            try:
                existing = note_path.read_text(encoding="utf-8")
            except Exception:
                existing = ""
            new_content = (existing.rstrip() + "\n" + text + "\n") if existing.strip() else (text + "\n")
        else:
            new_content = text + "\n"

        # Atomik yazma — bozulmaya karşı güvenli
        tmp = note_path.with_suffix(".txt.tmp")
        tmp.write_text(new_content, encoding="utf-8")
        os.replace(tmp, note_path)

        if open_after:
            try:
                subprocess.Popen(["notepad.exe", str(note_path)])
            except Exception:
                os.system(f'start "" notepad "{note_path}"')

        return {
            "success": True,
            "path": str(note_path),
            "message": f"Not defterine yazdım ve açtım: \"{text[:60]}\"",
        }
    except Exception as e:
        return {"success": False, "error": f"Not defterine yazılamadı: {e}"}


def open_path(path: str) -> dict:
    """Bir dosyayı veya klasörü varsayılan uygulamasıyla açar (os.startfile)."""
    try:
        p = os.path.expandvars(os.path.expanduser((path or "").strip().strip('"')))
        if not os.path.exists(p):
            return {"success": False, "error": f"Bulunamadı: {path}"}
        os.startfile(p)  # Windows: dosya ilişkilendirmesine göre açar
        return {"success": True, "message": f"Açıldı: {os.path.basename(p) or p}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
