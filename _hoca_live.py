# -*- coding: utf-8 -*-
"""Canli dogrulama: Word/Excel yolu cozumleniyor mu + Notepad gercekten aciliyor mu."""
import sys, io, os, time, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r'C:\BLUE_AI')

from blue_ai.tools.app_control import _resolve_via_app_paths, write_to_notepad

print("=== WORD / EXCEL KURULU MU (yol cozumu) ===")
for exe, label in [("WINWORD.EXE", "Word"), ("EXCEL.EXE", "Excel"),
                   ("POWERPNT.EXE", "PowerPoint")]:
    path = _resolve_via_app_paths(exe)
    print(f"  {label:11}: {path or 'BULUNAMADI (App Paths)'}")

print()
print("=== NOTEPAD'E YAZMA (gercek dosya + Notepad acilir) ===")
res = write_to_notepad("HOCA TESTI: bu satir BLUE_AI tarafindan yazildi.",
                       append=False, open_after=True)
print(f"  sonuc: {res}")
time.sleep(1.0)
# Dosya gercekten yazildi mi?
p = res.get("path", "")
if p and os.path.exists(p):
    content = open(p, encoding="utf-8").read()
    print(f"  DOSYA ICERIGI: {content!r}")
# Acilan notepad'i kapat (demo ekranini kirletmesin)
subprocess.run(["taskkill", "/IM", "notepad.exe", "/F"],
               capture_output=True)
print("  (test notepad penceresi kapatildi)")
