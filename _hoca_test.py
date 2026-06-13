# -*- coding: utf-8 -*-
"""Hoca gereksinimleri — tespit/cikarim katmani testi (uygulama ACMADAN)."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r'C:\BLUE_AI')

from blue_ai.brain.brain import Brain

b = Brain()
b.initialize()

print("=" * 60)
print("1) UYGULAMA ACMA — intent + app_name cikarimi")
print("=" * 60)
for msg in ["word ac", "word aç", "excel aç", "excel'i aç",
            "notepad aç", "not defterini aç", "wordü aç",
            "powerpoint aç", "hesap makinesi aç", "chrome aç"]:
    intent = b._detect_intent_fast(msg)
    args = b._extract_fast_path_args(intent, msg) if intent else {}
    print(f"  {msg!r:28} -> intent={intent!r:12} args={args}")

print()
print("=" * 60)
print("2) NOTEPAD'E YAZMA — intent + metin cikarimi")
print("=" * 60)
for msg in ["not defterine merhaba dünya yaz",
            "notepada bugün hava güzel ekle",
            "deftere alışveriş listesi yaz",
            "yeni not defterine test yaz"]:
    intent = b._detect_intent_fast(msg)
    args = b._extract_fast_path_args(intent, msg) if intent else {}
    print(f"  {msg!r:38} -> intent={intent!r:16} args={args}")

print()
print("=" * 60)
print("3) HAFIZA — isim kaydet + yeniden okuyarak hatirla")
print("=" * 60)
# Yeni bir Brain örneği = uygulamanin yeniden acilmasini simule eder
save = b.process("benim adım Dayan")
print(f"  KAYDET   : {save.message!r}")

# Yeni instance (uygulama yeniden acildi gibi) — kalici dosyadan okumali
b2 = Brain(); b2.initialize()
recall = b2.process("benim adım ne?")
print(f"  HATIRLA  : {recall.message!r}")

from blue_ai.memory.manager import get_memory
print(f"  DOSYA    : {get_memory().get_file_path()}")
print(f"  TUM BILGI: {get_memory().get_all_facts()}")
