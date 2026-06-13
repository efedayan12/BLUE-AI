"""
BLUE_AI — Ekran İzleme ve Müdahale (Screen Vision & Control)

Üç katman:
  1) YAKALAMA   — mss ile çok hızlı ekran yakalama (canlı izleme), PIL ile küçült/encode
  2) ANLAMA     — Windows yerleşik OCR (winsdk) ile ekrandaki metni + konumlarını oku;
                  win32 ile aktif pencere bilgisi
  3) MÜDAHALE   — ctypes SendInput ile fare/klavye kontrolü (tıkla, yaz, kaydır, kısayol)

Tasarım ilkesi: ağır/oynak bağımlılıklar (mss, winsdk, win32) OPSİYONELDİR.
Yoksa modül ÇÖKMEZ; sadece o özellik devre dışı kalır. Fare/klavye müdahalesi
sadece ctypes kullanır (standart Windows API) → her zaman çalışır.

Koordinat sistemi: yakalama fiziksel piksel; tıklama da fiziksel piksel bekler.
Süreç DPI-aware yapılır (WebView2 zaten DPI-aware'dir) → koordinatlar birebir eşleşir.
"""

from __future__ import annotations

import io
import time
import base64
import threading
import ctypes
from ctypes import wintypes
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════
#  0. DPI farkındalığı — yakalama ile tıklama koordinatları eşleşsin
# ═══════════════════════════════════════════════════════════════════════════
def _ensure_dpi_aware() -> None:
    """Süreci DPI-aware yap (fiziksel piksel = koordinat). Birden fazla çağrı zararsız."""
    try:
        # Per-Monitor v2 (en doğru)
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


_ensure_dpi_aware()


# ═══════════════════════════════════════════════════════════════════════════
#  1. EKRAN YAKALAMA  (mss + PIL)
# ═══════════════════════════════════════════════════════════════════════════
_thread_local = threading.local()


def _get_sct():
    """Thread'e özel mss örneği (mss thread-safe değildir → her thread kendi örneği)."""
    sct = getattr(_thread_local, "sct", None)
    if sct is None:
        import mss
        sct = mss.MSS()
        _thread_local.sct = sct
    return sct


def capture_image(monitor: int = 1, region: Optional[dict] = None):
    """Ekranı yakala → (PIL.Image, offset_left, offset_top).

    monitor=1 birincil ekran. region verilirse {left,top,width,height} (mutlak px).
    """
    from PIL import Image
    sct = _get_sct()
    if region:
        mon = {"left": int(region["left"]), "top": int(region["top"]),
               "width": int(region["width"]), "height": int(region["height"])}
    else:
        mons = sct.monitors
        idx = monitor if 0 <= monitor < len(mons) else 1
        mon = mons[idx]
    shot = sct.grab(mon)
    img = Image.frombytes("RGB", shot.size, shot.rgb)
    return img, int(mon["left"]), int(mon["top"])


def capture_png(monitor: int = 1, region: Optional[dict] = None) -> bytes:
    """Ekranı PNG byte dizisi olarak yakala (OCR için kayıpsız)."""
    img, _, _ = capture_image(monitor, region)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def capture_base64(max_width: int = 900, monitor: int = 1, quality: int = 60) -> str:
    """Canlı önizleme için küçültülmüş JPEG data-URL (UI'da <img src> olarak kullanılır)."""
    img, _, _ = capture_image(monitor)
    w, h = img.size
    if max_width and w > max_width:
        nh = int(h * max_width / w)
        img = img.resize((max_width, nh))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=quality)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return "data:image/jpeg;base64," + b64


def screen_size() -> tuple[int, int]:
    """Birincil ekran çözünürlüğü (fiziksel px)."""
    try:
        sct = _get_sct()
        mon = sct.monitors[1]
        return int(mon["width"]), int(mon["height"])
    except Exception:
        u = ctypes.windll.user32
        return int(u.GetSystemMetrics(0)), int(u.GetSystemMetrics(1))


# ═══════════════════════════════════════════════════════════════════════════
#  2. ANLAMA — Windows OCR (winsdk) + aktif pencere (win32)
# ═══════════════════════════════════════════════════════════════════════════
def ocr_available() -> bool:
    try:
        import winsdk.windows.media.ocr  # noqa: F401
        return True
    except Exception:
        return False


def _run_async(coro):
    """winsdk async op'unu senkron çalıştır (kendi event loop'unda)."""
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    except Exception:
        return asyncio.run(coro)


async def _ocr_png_async(png_bytes: bytes, lang: str = "tr"):
    from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.globalization import Language

    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream.get_output_stream_at(0))
    writer.write_bytes(png_bytes)
    await writer.store_async()
    await writer.flush_async()
    stream.seek(0)

    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()

    engine = None
    try:
        if Language.is_well_formed(lang):
            engine = OcrEngine.try_create_from_language(Language(lang))
    except Exception:
        engine = None
    if engine is None:
        engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        return None
    return await engine.recognize_async(bitmap)


def ocr_words(monitor: int = 1, region: Optional[dict] = None, lang: str = "tr") -> dict:
    """Ekrandaki metni OCR ile oku.

    Döndürür: {ok, text, words:[{text,x,y,w,h,cx,cy}], lines:[...], count}
    Koordinatlar MUTLAK ekran pikselidir (tıklama için doğrudan kullanılabilir).
    """
    if not ocr_available():
        return {"ok": False, "error": "OCR mevcut değil (winsdk yok).",
                "text": "", "words": [], "lines": [], "count": 0}
    try:
        # OCR'ı kayıpsız PNG üzerinde yap, ama offset'i bilmek için region/monitor kullan
        if region:
            off_l, off_t = int(region["left"]), int(region["top"])
        else:
            sct = _get_sct()
            mon = sct.monitors[monitor if 0 <= monitor < len(sct.monitors) else 1]
            off_l, off_t = int(mon["left"]), int(mon["top"])
        png = capture_png(monitor, region)
        result = _run_async(_ocr_png_async(png, lang))
        if result is None:
            return {"ok": False, "error": "OCR motoru oluşturulamadı.",
                    "text": "", "words": [], "lines": [], "count": 0}
        words, lines = [], []
        for line in result.lines:
            line_words = []
            for w in line.words:
                r = w.bounding_rect
                wx, wy = int(r.x) + off_l, int(r.y) + off_t
                ww, wh = int(r.width), int(r.height)
                entry = {"text": w.text, "x": wx, "y": wy, "w": ww, "h": wh,
                         "cx": wx + ww // 2, "cy": wy + wh // 2}
                words.append(entry)
                line_words.append(w.text)
            if line_words:
                lines.append(" ".join(line_words))
        return {"ok": True, "text": result.text or "\n".join(lines),
                "words": words, "lines": lines, "count": len(words)}
    except Exception as e:
        return {"ok": False, "error": f"OCR hatası: {e}",
                "text": "", "words": [], "lines": [], "count": 0}


def _norm_tr(s: str) -> str:
    tr = {"ı": "i", " İ": "i", "İ": "i", "ş": "s", "ç": "c", "ğ": "g", "ü": "u", "ö": "o"}
    s = (s or "").lower()
    for a, b in tr.items():
        s = s.replace(a, b)
    return s.strip()


def find_text(query: str, monitor: int = 1, lang: str = "tr") -> dict:
    """Ekranda bir metni bul → en iyi eşleşen kelimenin/öbeğin merkez koordinatı.

    Döndürür: {ok, x, y, matched, candidates:[...]}
    Önce tam kelime, sonra çok-kelimeli öbek, sonra 'içeren' eşleşmesi denenir.
    """
    res = ocr_words(monitor=monitor, lang=lang)
    if not res["ok"]:
        return {"ok": False, "error": res.get("error", "OCR başarısız"), "candidates": []}

    q = _norm_tr(query)
    q_tokens = q.split()
    words = res["words"]

    # 1) Tek kelime tam eşleşme
    for w in words:
        if _norm_tr(w["text"]) == q:
            return {"ok": True, "x": w["cx"], "y": w["cy"], "matched": w["text"], "candidates": []}

    # 2) Çok kelimeli öbek — ardışık kelimeleri birleştirip ara
    if len(q_tokens) > 1:
        n = len(q_tokens)
        for i in range(len(words) - n + 1):
            window = words[i:i + n]
            joined = _norm_tr(" ".join(x["text"] for x in window))
            if joined == q or q in joined:
                xs = [x["cx"] for x in window]
                ys = [x["cy"] for x in window]
                return {"ok": True, "x": sum(xs) // len(xs), "y": sum(ys) // len(ys),
                        "matched": " ".join(x["text"] for x in window), "candidates": []}

    # 3) 'İçeren' eşleşmesi (kısmi)
    partial = [w for w in words if q and q in _norm_tr(w["text"])]
    if not partial and q_tokens:
        partial = [w for w in words if any(t in _norm_tr(w["text"]) for t in q_tokens if len(t) > 2)]
    if partial:
        best = min(partial, key=lambda w: len(_norm_tr(w["text"])))
        return {"ok": True, "x": best["cx"], "y": best["cy"], "matched": best["text"],
                "candidates": [w["text"] for w in partial[:5]]}

    return {"ok": False, "error": f"'{query}' ekranda bulunamadı.",
            "candidates": [w["text"] for w in words[:12]]}


def active_window() -> dict:
    """Öndeki (aktif) pencere bilgisi: başlık, işlem adı, konum."""
    info = {"title": "", "process": "", "rect": None}
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        info["title"] = win32gui.GetWindowText(hwnd) or ""
        try:
            l, t, r, b = win32gui.GetWindowRect(hwnd)
            info["rect"] = {"left": l, "top": t, "right": r, "bottom": b}
        except Exception:
            pass
        try:
            import win32process
            import psutil
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            info["process"] = psutil.Process(pid).name()
        except Exception:
            pass
    except Exception:
        # win32 yoksa en azından başlığı GetForegroundWindow + ctypes ile al
        try:
            u = ctypes.windll.user32
            hwnd = u.GetForegroundWindow()
            length = u.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            u.GetWindowTextW(hwnd, buf, length + 1)
            info["title"] = buf.value
        except Exception:
            pass
    return info


def _force_foreground(hwnd) -> None:
    """Bir pencereyi güvenilir şekilde öne getir (AttachThreadInput tekniği).

    Windows, arka plan sürecinin SetForegroundWindow çağrısını engeller; bu teknik
    hedef pencerenin giriş thread'ine bağlanarak kısıtlamayı aşar.
    """
    u = ctypes.windll.user32
    k = ctypes.windll.kernel32
    try:
        fg = u.GetForegroundWindow()
        t_fg = u.GetWindowThreadProcessId(fg, None)
        t_tg = u.GetWindowThreadProcessId(hwnd, None)
        cur = k.GetCurrentThreadId()
        u.AttachThreadInput(t_fg, cur, True)
        u.AttachThreadInput(t_tg, cur, True)
        try:
            u.ShowWindow(hwnd, 9)        # SW_RESTORE
            u.BringWindowToTop(hwnd)
            u.SetForegroundWindow(hwnd)
        finally:
            u.AttachThreadInput(t_fg, cur, False)
            u.AttachThreadInput(t_tg, cur, False)
    except Exception:
        try:
            u.SetForegroundWindow(hwnd)
        except Exception:
            pass


def focus_window(title_substr: str) -> bool:
    """Başlığında verilen metni geçen görünür pencereyi bul ve öne getir."""
    title_substr = (title_substr or "").lower()
    matches = []
    try:
        import win32gui
        def cb(h, _):
            t = win32gui.GetWindowText(h) or ""
            if title_substr in t.lower() and win32gui.IsWindowVisible(h):
                matches.append(h)
            return True
        win32gui.EnumWindows(cb, None)
    except Exception:
        # win32gui yoksa ctypes ile dene
        EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        u = ctypes.windll.user32
        def cb2(h, _):
            n = u.GetWindowTextLengthW(h)
            buf = ctypes.create_unicode_buffer(n + 1)
            u.GetWindowTextW(h, buf, n + 1)
            if title_substr in (buf.value or "").lower() and u.IsWindowVisible(h):
                matches.append(h)
            return True
        u.EnumWindows(EnumProc(cb2), 0)
    if matches:
        _force_foreground(matches[0])
        time.sleep(0.25)
        return True
    return False


def describe_screen(monitor: int = 1, max_lines: int = 12, lang: str = "tr") -> dict:
    """Ekranda ne olduğunu özetle: aktif pencere + OCR metin özeti.

    'ekranda ne var / ekranı oku' komutları bunu kullanır.
    """
    win = active_window()
    summary_parts = []
    if win.get("title"):
        proc = f" ({win['process']})" if win.get("process") else ""
        summary_parts.append(f"Aktif pencere: {win['title']}{proc}")

    ocr = ocr_words(monitor=monitor, lang=lang)
    lines = []
    if ocr["ok"]:
        lines = [ln for ln in ocr["lines"] if ln.strip()][:max_lines]
        if lines:
            summary_parts.append("Ekranda okunan metin:")
            summary_parts.extend(f"  • {ln}" for ln in lines)
        summary_parts.append(f"(Toplam {ocr['count']} kelime okundu)")
    else:
        summary_parts.append("Ekrandaki metin okunamadı (OCR kapalı).")

    return {
        "ok": True,
        "active_window": win,
        "lines": lines,
        "word_count": ocr.get("count", 0),
        "ocr_ok": ocr["ok"],
        "summary": "\n".join(summary_parts),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  3. MÜDAHALE — ctypes SendInput (fare + klavye). Bağımlılık yok.
# ═══════════════════════════════════════════════════════════════════════════
_user32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120

ULONG_PTR = ctypes.c_size_t  # 64-bit'te 8 byte — dwExtraInfo için DOĞRU tip


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def _send(*inputs) -> None:
    n = len(inputs)
    arr = (_INPUT * n)(*inputs)
    _user32.SendInput(n, arr, ctypes.sizeof(_INPUT))


def _mouse_input(flags: int, data: int = 0) -> _INPUT:
    mi = _MOUSEINPUT(0, 0, data & 0xFFFFFFFF, flags, 0, 0)
    return _INPUT(INPUT_MOUSE, _INPUTUNION(mi=mi))


def _key_vk(vk: int, up: bool = False) -> _INPUT:
    ki = _KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, 0)
    return _INPUT(INPUT_KEYBOARD, _INPUTUNION(ki=ki))


def _key_unicode(code_unit: int, up: bool = False) -> _INPUT:
    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0)
    ki = _KEYBDINPUT(0, code_unit, flags, 0, 0)
    return _INPUT(INPUT_KEYBOARD, _INPUTUNION(ki=ki))


def get_cursor_pos() -> tuple[int, int]:
    pt = wintypes.POINT()
    _user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def move_to(x: int, y: int) -> dict:
    """İmleci mutlak (x, y) ekran konumuna taşı."""
    try:
        _user32.SetCursorPos(int(x), int(y))
        return {"success": True, "message": f"İmleç ({x}, {y}) konumuna taşındı."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def click(x: Optional[int] = None, y: Optional[int] = None,
          button: str = "left", clicks: int = 1) -> dict:
    """Belirtilen konuma (veya mevcut konuma) tıkla."""
    try:
        if x is not None and y is not None:
            _user32.SetCursorPos(int(x), int(y))
            time.sleep(0.03)
        down, up = {
            "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
            "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
            "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
        }.get(button, (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP))
        for _ in range(max(1, clicks)):
            _send(_mouse_input(down), _mouse_input(up))
            time.sleep(0.02)
        where = f"({x}, {y})" if x is not None else "mevcut konum"
        return {"success": True, "message": f"{button} tık × {clicks} → {where}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def double_click(x: Optional[int] = None, y: Optional[int] = None) -> dict:
    return click(x, y, "left", clicks=2)


def right_click(x: Optional[int] = None, y: Optional[int] = None) -> dict:
    return click(x, y, "right", clicks=1)


def scroll(amount: int = -3) -> dict:
    """Dikey kaydır. Pozitif=yukarı, negatif=aşağı (her birim bir 'notch')."""
    try:
        _send(_mouse_input(MOUSEEVENTF_WHEEL, int(amount) * WHEEL_DELTA))
        yon = "yukarı" if amount > 0 else "aşağı"
        return {"success": True, "message": f"{abs(amount)} adım {yon} kaydırıldı."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def type_text(text: str, per_char_delay: float = 0.0) -> dict:
    """Verilen metni (Türkçe dahil) klavyeden yazıyormuş gibi gönder (odaklı pencereye)."""
    try:
        text = text or ""
        inputs = []
        for ch in text:
            if ch in ("\n", "\r"):
                inputs.append(_key_vk(0x0D))       # Enter down
                inputs.append(_key_vk(0x0D, True))  # Enter up
                continue
            if ch == "\t":
                inputs.append(_key_vk(0x09))
                inputs.append(_key_vk(0x09, True))
                continue
            # UTF-16 kod birimlerine ayır (BMP dışı karakterler için surrogate pair)
            for cu in _utf16_units(ch):
                inputs.append(_key_unicode(cu))
                inputs.append(_key_unicode(cu, True))
        if per_char_delay > 0:
            for i in range(0, len(inputs), 2):
                _send(inputs[i], inputs[i + 1])
                time.sleep(per_char_delay)
        elif inputs:
            # Tek seferde göndermek hızlıdır; çok uzun metni parçala
            CHUNK = 200
            for i in range(0, len(inputs), CHUNK):
                _send(*inputs[i:i + CHUNK])
        return {"success": True, "message": f"{len(text)} karakter yazıldı."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _utf16_units(ch: str) -> list[int]:
    """Bir karakteri UTF-16 kod birimlerine çevir (emoji vb. için surrogate pair)."""
    data = ch.encode("utf-16-le")
    return [int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data), 2)]


# Virtual-Key kodları (yaygın tuşlar)
_VK = {
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B,
    "space": 0x20, "bosluk": 0x20, "backspace": 0x08, "geri": 0x08,
    "delete": 0x2E, "del": 0x2E, "sil": 0x2E, "insert": 0x2D,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "yukari": 0x26, "asagi": 0x28, "sol": 0x25, "sag": 0x27,
    "ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10,
    "win": 0x5B, "windows": 0x5B, "capslock": 0x14, "printscreen": 0x2C,
}
for _i in range(1, 13):
    _VK[f"f{_i}"] = 0x70 + (_i - 1)
for _c in range(ord("a"), ord("z") + 1):
    _VK[chr(_c)] = 0x41 + (_c - ord("a"))
for _d in range(0, 10):
    _VK[str(_d)] = 0x30 + _d


def press_key(key: str) -> dict:
    """Tek bir tuşa bas (ör: 'enter', 'esc', 'f5')."""
    vk = _VK.get((key or "").strip().lower())
    if vk is None:
        return {"success": False, "error": f"Bilinmeyen tuş: {key}"}
    try:
        _send(_key_vk(vk), _key_vk(vk, True))
        return {"success": True, "message": f"'{key}' tuşuna basıldı."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def hotkey(*keys: str) -> dict:
    """Tuş kombinasyonu (ör: hotkey('ctrl','s') → kaydet)."""
    vks = []
    for k in keys:
        vk = _VK.get((k or "").strip().lower())
        if vk is None:
            return {"success": False, "error": f"Bilinmeyen tuş: {k}"}
        vks.append(vk)
    try:
        seq = [_key_vk(vk) for vk in vks] + [_key_vk(vk, True) for vk in reversed(vks)]
        _send(*seq)
        return {"success": True, "message": f"Kısayol: {'+'.join(keys)}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def click_text(query: str, monitor: int = 1, button: str = "left",
               double: bool = False, lang: str = "tr") -> dict:
    """Ekranda bir metni OCR ile bul ve üzerine tıkla."""
    found = find_text(query, monitor=monitor, lang=lang)
    if not found.get("ok"):
        return {"success": False, "error": found.get("error", "Bulunamadı."),
                "candidates": found.get("candidates", [])}
    x, y = found["x"], found["y"]
    res = double_click(x, y) if double else click(x, y, button)
    if res.get("success"):
        return {"success": True,
                "message": f"'{found['matched']}' bulundu ({x},{y}) ve tıklandı."}
    return res


# ═══════════════════════════════════════════════════════════════════════════
#  4. CANLI İZLEYİCİ — arka planda sürekli yakalama (UI önizleme için)
# ═══════════════════════════════════════════════════════════════════════════
class ScreenWatcher:
    """Arka planda ekranı sürekli yakalar; en son kareyi base64 olarak tutar.

    UI bu kareyi periyodik olarak çeker (canlı izleme paneli). Hafif ve performanslı:
    sadece küçültülmüş JPEG tutar, OCR yapmaz (OCR isteğe bağlı/analizde çalışır).
    """

    def __init__(self, interval: float = 0.4, max_width: int = 900):
        self.interval = interval
        self.max_width = max_width
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._latest_b64: Optional[str] = None
        self._latest_ts: float = 0.0
        self._active = False
        self._frames = 0

    def start(self, interval: Optional[float] = None) -> bool:
        if self._active:
            return False
        if interval:
            self.interval = max(0.1, float(interval))
        self._stop.clear()
        self._active = True
        self._thread = threading.Thread(target=self._loop, name="ScreenWatcher", daemon=True)
        self._thread.start()
        return True

    def _loop(self) -> None:
        # Bu thread'in kendi mss örneği olur (_get_sct thread-local)
        while not self._stop.is_set():
            t0 = time.time()
            try:
                b64 = capture_base64(max_width=self.max_width)
                with self._lock:
                    self._latest_b64 = b64
                    self._latest_ts = time.time()
                    self._frames += 1
            except Exception:
                pass
            dt = time.time() - t0
            self._stop.wait(max(0.05, self.interval - dt))
        # Temizlik
        sct = getattr(_thread_local, "sct", None)
        if sct is not None:
            try:
                sct.close()
            except Exception:
                pass
            _thread_local.sct = None

    def stop(self) -> bool:
        if not self._active:
            return False
        self._stop.set()
        self._active = False
        return True

    def is_active(self) -> bool:
        return self._active

    def latest_frame(self) -> dict:
        with self._lock:
            return {
                "active": self._active,
                "frame": self._latest_b64,
                "ts": self._latest_ts,
                "age": (time.time() - self._latest_ts) if self._latest_ts else None,
                "frames": self._frames,
            }


_watcher: Optional[ScreenWatcher] = None


def get_watcher() -> ScreenWatcher:
    global _watcher
    if _watcher is None:
        _watcher = ScreenWatcher()
    return _watcher
