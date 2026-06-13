# -*- coding: utf-8 -*-
"""HOCANIN SENARYOSU: 'adın hasan olsun' -> yeniden acilis -> 'adın ne?'"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r'C:\BLUE_AI')

from blue_ai.brain.brain import Brain

print("=== ADIM 1: Isim ver ===")
b = Brain(); b.initialize()
r = b.process("adın hasan olsun")
print(f"  'adın hasan olsun'  -> {r.message!r}")

print()
print("=== ADIM 2: YENIDEN ACILIS (taze Brain, kalici dosyadan okur) ===")
b2 = Brain(); b2.initialize()
tests = ["adın ne", "adın ne?", "ismin ne", "senin adın ne",
         "adını söyle", "adın neydi"]
for q in tests:
    r = b2.process(q)
    ok = "hasan" in r.message.lower()
    print(f"  {'OK ' if ok else '!! '}{q!r:18} -> {r.message!r}")

print()
print("=== ADIM 3: Diger kaliplar hala calisiyor mu ===")
r = b2.process("benim adım ne")
print(f"  'benim adım ne'     -> {r.message!r}")
r = b2.process("ismin ayşe olsun")
print(f"  'ismin ayşe olsun'  -> {r.message!r}")
b3 = Brain(); b3.initialize()
r = b3.process("adın ne")
print(f"  (yeni acilis) 'adın ne' -> {r.message!r}")
r = b3.process("benim adım Dayan")
print(f"  'benim adım Dayan'  -> {r.message!r}")
b4 = Brain(); b4.initialize()
r = b4.process("benim adım ne?")
print(f"  (yeni acilis) 'benim adım ne?' -> {r.message!r}")

from blue_ai.memory.manager import get_memory
print()
print(f"  Hafiza dosyasi: {get_memory().get_file_path()}")
print(f"  Kayitli: {get_memory().get_all_facts()}")
