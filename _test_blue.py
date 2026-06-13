# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\BLUE_AI")

import blue_ai.memory.manager as mm
from blue_ai.brain.brain import get_brain
brain = get_brain()
brain.initialize()

def mem(msg):
    r = brain._try_memory_operation(msg)
    return r.message if r else "<<None>>"

print("===== ISIM KAYDETME (yeni kaliplar) =====")
for m in ["ismin hasan olsun", "adin hasan olsun", "adin hasan",
          "bana hasan de", "beni hasan olarak kaydet", "ismimi hasan yap",
          "benim adim hasan", "adim hasan benim"]:
    # her testten once temizle ki bagimsiz olsun
    mm.get_memory().clear_all()
    print(f"  {m!r:35} -> {mem(m)}")

print("\n===== YANLIS POZITIF KONTROL (isim OLMAMALI) =====")
for m in ["nasilsin", "ben iyiyim", "hava nasil", "bugun ne yapsak"]:
    mm.get_memory().clear_all()
    r = brain._try_memory_operation(m)
    print(f"  {m!r:25} -> {(r.message if r else '<<None - dogru>>')}")

print("\n===== KALICILIK: kapanip acilsa da hatirla =====")
mm.get_memory().clear_all()
print("  kayit:", mem("ismin hasan olsun"))
mm._memory = None                      # uygulamayi kapat-ac simulasyonu
fresh = mm.get_memory()                # diskten yeniden olusur
print("  diskten okunan isim:", repr(fresh.get_fact("isim")))
print("  sorgu:", mem("adim ne"))

print("\n===== PC KONTROL: parametre cikarimi (app.py artik buna delege ediyor) =====")
for intent, m in [("type_on_screen", "ekrana merhaba dunya yaz"),
                  ("click_on_screen", "kaydet butonuna tikla"),
                  ("press_keys", "enter'a bas"),
                  ("write_to_notepad", "not defterine alisveris listesi yaz"),
                  ("scroll_screen", "asagi kaydir")]:
    print(f"  {intent:18} <- {m!r:38} => {brain._extract_fast_path_args(intent, m)}")
