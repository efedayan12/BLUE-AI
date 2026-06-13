# -*- coding: utf-8 -*-
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\BLUE_AI")

from blue_ai.brain.brain import get_brain
brain = get_brain()
brain.initialize()

print("===== PC MUDAHALE: gercek execute (uctan uca) =====")

# 1. Klavye mudahale katmani (ctypes SendInput) - zararsiz 'esc'
r = brain._registry.execute_tool("press_keys", keys="esc")
print(f"1) press_keys(esc)   -> success={r.success} | {r.message or r.error}")

# 2. Ekrani anlama (Windows OCR) - zararsiz okuma
r = brain._registry.execute_tool("analyze_screen")
print(f"2) analyze_screen    -> success={r.success} | {(r.message or r.error)[:70]!r}")

# 3. Uygulama acma - hesap makinesi ac, sonra kapat
r = brain._registry.execute_tool("open_app", app_name="calc")
print(f"3) open_app(calc)    -> success={r.success} | {r.message or r.error}")
time.sleep(1.5)
import subprocess
subprocess.run(["taskkill", "/IM", "CalculatorApp.exe", "/F"],
               capture_output=True)
subprocess.run(["taskkill", "/IM", "Calculator.exe", "/F"], capture_output=True)
print("   (hesap makinesi kapatildi)")
