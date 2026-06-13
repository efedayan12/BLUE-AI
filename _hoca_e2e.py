# -*- coding: utf-8 -*-
"""Tam zincir: Brain.process('notepad ac') -> Notepad gercekten acilmali."""
import sys, io, time, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r'C:\BLUE_AI')

from blue_ai.brain.brain import Brain

b = Brain(); b.initialize()

def running(exe):
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {exe}"],
                         capture_output=True, text=True).stdout.lower()
    return exe.lower() in out

print("=== Brain.process('notepad ac') ===")
r = b.process("notepad ac")
print(f"  type={r.response_type}  msg={r.message!r}")
time.sleep(1.2)
print(f"  Notepad calisiyor mu? {running('notepad.exe')}")
subprocess.run(["taskkill", "/IM", "notepad.exe", "/F"], capture_output=True)

print()
print("=== Brain.process('not defterine merhaba hocam yaz') ===")
r = b.process("not defterine merhaba hocam yaz")
print(f"  type={r.response_type}  msg={r.message!r}")
time.sleep(1.2)
print(f"  Notepad calisiyor mu? {running('notepad.exe')}")
subprocess.run(["taskkill", "/IM", "notepad.exe", "/F"], capture_output=True)
