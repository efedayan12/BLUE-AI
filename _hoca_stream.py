# -*- coding: utf-8 -*-
"""GUI streaming yolu: _detect_intent_fast + _extract_tool_params (open_app)."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r'C:\BLUE_AI')

from blue_ai.app import BlueAIBackend
from blue_ai.brain.brain import get_brain

# Prewarm thread'ini tetiklemeden nesne olustur
api = object.__new__(BlueAIBackend)
api._brain = None

b = get_brain(); b.initialize()

print("=== GUI streaming yolu — open_app (start_chat_stream) ===")
cases = ["word aç", "excel aç", "excel'i aç", "notepad aç",
         "not defterini aç", "powerpoint aç", "hesap makinesi aç",
         "chrome aç", "wordü aç"]
ok = True
for msg in cases:
    intent = b._detect_intent_fast(msg)
    params = api._extract_tool_params(intent, msg) if intent else {}
    name = params.get("app_name", "")
    good = bool(name)
    ok = ok and good
    flag = "OK " if good else "!! "
    print(f"  {flag}{msg!r:22} -> intent={intent!r:10} app_name={name!r}")

print()
print("TUMU GECTI" if ok else "BASARISIZ — bos app_name var!")
