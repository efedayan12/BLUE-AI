"""
BLUE_AI Memory — Hafıza Sistemi (.txt tabanlı)

Kullanıcı bilgilerini ve notları okunabilir düz metin dosyasında saklar.
Konum: %LOCALAPPDATA%\\BLUE_AI\\memory\\hafiza.txt  (her Windows kullanıcısına ÖZEL,
       her zaman yazılabilir — uygulama Program Files'a kurulsa bile kalıcıdır).
Format:
  # BLUE AI Hafıza
  isim: Ahmet
  sehir: Ankara
  meslek: Ogrenci
  ---NOT---
  2024-01-01: Kullanıcı Python öğreniyor
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def get_user_data_dir() -> Path:
    """Kullanıcıya özel, yazılabilir veri dizinini döndür.

    Öncelik sırası: %LOCALAPPDATA%\\BLUE_AI → %APPDATA%\\BLUE_AI → ~/.blue_ai → exe yanı
    Bu dizin her Windows kullanıcısı için AYRIDIR → hafıza otomatik olarak "kişiye özel".
    Uygulama Program Files'a kurulsa bile buraya yazma HER ZAMAN mümkündür
    (Program Files standart kullanıcı için salt-okunurdur — bu yüzden exe yanına yazmıyoruz).
    """
    candidates: list[Path] = []
    for env in ("LOCALAPPDATA", "APPDATA"):
        val = os.environ.get(env)
        if val:
            candidates.append(Path(val) / "BLUE_AI")
    candidates.append(Path.home() / ".blue_ai")
    # Son çare — exe/script yanı (yazılamazsa zaten elenecek)
    try:
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).parent / "data")
        else:
            candidates.append(Path(__file__).resolve().parent.parent.parent / "data")
    except Exception:
        pass

    for base in candidates:
        try:
            base.mkdir(parents=True, exist_ok=True)
            # Gerçekten yazılabilir mi? (Program Files'ta mkdir başarılı olup yazma başarısız olabilir)
            probe = base / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return base
        except Exception:
            continue

    # Hiçbiri olmadıysa geçici dizin — yine de çalışsın (asla çökme)
    import tempfile
    fallback = Path(tempfile.gettempdir()) / "BLUE_AI"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _legacy_memory_paths() -> list[Path]:
    """Eski sürümlerin hafıza dosyası konumları — yükseltmede taşıma için."""
    paths: list[Path] = []
    try:
        if getattr(sys, "frozen", False):
            paths.append(Path(sys.executable).parent / "data" / "memory" / "hafiza.txt")
        paths.append(Path(__file__).resolve().parent.parent.parent / "data" / "memory" / "hafiza.txt")
    except Exception:
        pass
    return paths


def _atomic_write(path: Path, text: str) -> bool:
    """Atomik yazma — önce .tmp'ye yaz sonra yer değiştir. Yarıda kesilse bile dosya bozulmaz."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)  # aynı disk içinde atomiktir
        return True
    except Exception as e:
        # Son çare: doğrudan yaz (yine de veri kaybı olmasın)
        try:
            path.write_text(text, encoding="utf-8")
            return True
        except Exception:
            print(f"[Memory] Yazma hatasi: {e}")
            return False


def _get_memory_path() -> Path:
    """Hafıza dosyasının yolu — kullanıcıya özel kalıcı konum + eski dosyadan taşıma.

    EXE veya kaynak modda fark etmez; her zaman %LOCALAPPDATA%\\BLUE_AI\\memory altında.
    Eski sürümden (exe yanı) yükseltiliyorsa eski hafıza otomatik taşınır → kayıp olmaz.
    """
    mem_dir = get_user_data_dir() / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    target = mem_dir / "hafiza.txt"

    # Yeni konumda dosya yoksa eski konumdan taşı (veri kaybını önle)
    if not target.exists():
        for legacy in _legacy_memory_paths():
            try:
                if legacy.exists() and legacy.resolve() != target.resolve():
                    target.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")
                    print(f"[Memory] Eski hafiza tasindi: {legacy} -> {target}")
                    break
            except Exception:
                continue
    return target


class MemoryManager:
    """Düz metin tabanlı kalıcı hafıza yöneticisi."""

    def __init__(self, file_path: str = None):
        if file_path:
            self._path = Path(file_path)
        else:
            self._path = _get_memory_path()
        self._ensure_file()

    def _ensure_file(self):
        """Dosya yoksa başlık ile oluştur."""
        if not self._path.exists():
            _atomic_write(
                self._path,
                "# BLUE AI Hafiza Dosyasi\n"
                "# Her satir: anahtar: deger seklinde\n"
                "# Notlar --- isaretinden sonra gelir\n\n",
            )

    # ── Okuma ─────────────────────────────────────────────────────────────
    def _read_all(self) -> str:
        try:
            return self._path.read_text(encoding="utf-8")
        except Exception:
            return ""

    def _parse_facts(self) -> dict:
        """anahtar: deger satırlarını dict olarak döndür."""
        facts = {}
        content = self._read_all()
        in_notes = False
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            if line.startswith("---"):
                in_notes = True
                continue
            if not in_notes and ":" in line:
                key, _, val = line.partition(":")
                key = key.strip()
                val = val.strip()
                if key:
                    facts[key] = val
        return facts

    def _parse_notes(self) -> list[str]:
        """Not satırlarını liste olarak döndür."""
        notes = []
        content = self._read_all()
        in_notes = False
        for line in content.splitlines():
            if line.strip().startswith("---"):
                in_notes = True
                continue
            if in_notes and line.strip() and not line.strip().startswith("#"):
                notes.append(line.strip())
        return notes

    # ── Yazma ─────────────────────────────────────────────────────────────
    def set_fact(self, key: str, value: str, category: str = "general") -> bool:
        """Bir anahtar-değer bilgisini kaydet veya güncelle."""
        try:
            key = key.strip().lower().replace(" ", "_")
            value = value.strip()
            content = self._read_all()
            lines = content.splitlines()

            # Varsa güncelle
            updated = False
            new_lines = []
            in_notes = False
            for line in lines:
                if line.strip().startswith("---"):
                    in_notes = True
                if not in_notes and ":" in line and not line.strip().startswith("#"):
                    k, _, _ = line.partition(":")
                    if k.strip().lower().replace(" ", "_") == key:
                        new_lines.append(f"{key}: {value}")
                        updated = True
                        continue
                new_lines.append(line)

            if not updated:
                # Not bölümünden önce ekle
                insert_idx = len(new_lines)
                for i, l in enumerate(new_lines):
                    if l.strip().startswith("---"):
                        insert_idx = i
                        break
                new_lines.insert(insert_idx, f"{key}: {value}")

            _atomic_write(self._path, "\n".join(new_lines) + "\n")
            return True
        except Exception as e:
            print(f"[Memory] Kayıt hatası: {e}")
            return False

    def get_fact(self, key: str) -> str:
        """Bir anahtarın değerini döndür."""
        key = key.strip().lower().replace(" ", "_")
        return self._parse_facts().get(key, "")

    def get_all_facts(self) -> dict:
        """Tüm anahtar-değer çiftlerini döndür."""
        return self._parse_facts()

    def add_note(self, content: str, tags: str = "") -> int:
        """Hafızaya tarihli not ekle."""
        try:
            text = self._read_all()
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            note_line = f"{date_str}: {content}"
            if tags:
                note_line += f" [{tags}]"

            if "---" not in text:
                text = text.rstrip() + "\n\n---NOTLAR---\n"
            text = text.rstrip() + f"\n{note_line}\n"
            _atomic_write(self._path, text)
            return 1
        except Exception as e:
            print(f"[Memory] Not ekleme hatası: {e}")
            return -1

    def delete_fact(self, key: str) -> bool:
        """Bir anahtarı sil."""
        try:
            key = key.strip().lower().replace(" ", "_")
            content = self._read_all()
            lines = content.splitlines()
            new_lines = []
            in_notes = False
            for line in lines:
                if line.strip().startswith("---"):
                    in_notes = True
                if not in_notes and ":" in line and not line.strip().startswith("#"):
                    k, _, _ = line.partition(":")
                    if k.strip().lower().replace(" ", "_") == key:
                        continue
                new_lines.append(line)
            _atomic_write(self._path, "\n".join(new_lines) + "\n")
            return True
        except Exception:
            return False

    def clear_all(self) -> bool:
        """Tüm hafızayı temizle."""
        try:
            _atomic_write(self._path, "# BLUE AI Hafiza Dosyasi\n\n")
            return True
        except Exception:
            return False

    def generate_context_string(self) -> str:
        """LLM system prompt'una eklenecek hafıza bağlamını oluştur."""
        facts = self.get_all_facts()
        notes = self._parse_notes()

        if not facts and not notes:
            return ""

        lines = ["[Kullanici Hafizasi]"]
        for k, v in facts.items():
            lines.append(f"- {k}: {v}")
        if notes:
            lines.append("Son notlar:")
            for n in notes[-3:]:   # Son 3 not
                lines.append(f"  • {n}")

        return "\n".join(lines)

    def get_file_path(self) -> str:
        """Hafıza dosyasının tam yolunu döndür."""
        return str(self._path)


# ── Singleton ──────────────────────────────────────────────────────────────
_memory: Optional[MemoryManager] = None


def get_memory() -> MemoryManager:
    global _memory
    if _memory is None:
        _memory = MemoryManager()
    return _memory


# ═══════════════════════════════════════════════════════════════════════════
#  GEÇİCİ OTURUM BELLEĞİ — RAM'de, kapanınca gider
# ═══════════════════════════════════════════════════════════════════════════

class SessionMemory:
    """Oturum boyunca öğrenilen bilgileri RAM'de tutar.

    Kapanınca tamamen silinir. Önemli olanlar kalıcı belleğe aktarılır.
    """

    def __init__(self, max_entries: int = 100):
        self._entries: list[dict] = []   # {"text", "ts", "pinned"}
        self._max = max_entries
        self._learned_facts: dict[str, str] = {}  # Bu oturumda öğrenilen geçici bilgiler

    def add(self, text: str, pinned: bool = False) -> None:
        """Oturum notuna giriş ekle."""
        from datetime import datetime
        if len(self._entries) >= self._max:
            # En eski pin'siz girdiyi sil
            for i, e in enumerate(self._entries):
                if not e.get("pinned"):
                    self._entries.pop(i)
                    break
            else:
                self._entries.pop(0)
        self._entries.append({
            "text": text,
            "ts": datetime.now().strftime("%H:%M"),
            "pinned": pinned,
        })

    def set_temp_fact(self, key: str, value: str) -> None:
        """Bu oturuma özel geçici bilgi kaydet (kalıcıya yazmaz)."""
        self._learned_facts[key] = value

    def get_temp_fact(self, key: str) -> str:
        return self._learned_facts.get(key, "")

    def get_recent(self, n: int = 6) -> list[str]:
        recent = self._entries[-n:]
        return [f"[{e['ts']}] {'📌 ' if e['pinned'] else ''}{e['text']}" for e in recent]

    def generate_context(self) -> str:
        """LLM system prompt'una eklenecek oturum bağlamı."""
        lines = []
        # Pinlenmiş (önemli) girişler her zaman göster
        pinned = [e for e in self._entries if e.get("pinned")]
        if pinned:
            lines.append("[Bu Oturumda Öğrenilenler]")
            for e in pinned[-8:]:
                lines.append(f"  📌 {e['text']}")
        # Son birkaç genel not
        unpinned = [e for e in self._entries if not e.get("pinned")]
        if unpinned:
            if not lines:
                lines.append("[Bu Oturum Notları]")
            for e in unpinned[-3:]:
                lines.append(f"  • [{e['ts']}] {e['text']}")
        return "\n".join(lines) if lines else ""

    def clear(self) -> None:
        self._entries.clear()
        self._learned_facts.clear()

    @property
    def entry_count(self) -> int:
        return len(self._entries)


# ── SessionMemory Singleton ─────────────────────────────────────────────────
_session: Optional[SessionMemory] = None


def get_session_memory() -> SessionMemory:
    """Singleton oturum belleği döndür."""
    global _session
    if _session is None:
        _session = SessionMemory()
    return _session
