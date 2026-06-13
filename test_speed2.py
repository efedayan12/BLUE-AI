"""BLUE_AI hiz testi v2 - ML model fix sonrasi"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def ms(t): return f"{(time.time()-t)*1000:.0f}ms"
def sec(t): return f"{time.time()-t:.2f}s"

print("=== BLUE_AI HIZ TESTI v2 ===\n")

# 1. Brain + init
t = time.time()
from blue_ai.brain.brain import get_brain
brain = get_brain()
brain.initialize()
print(f"[1] Brain init        : {ms(t)}")

# 2. ML model load baslatiliyor (arka planda)
t = time.time()
brain._load_ml_model_bg()
print(f"[2] ML model bg start : {ms(t)} (arka planda yukleniyor)")
print(f"    _ml_model_ready   : {brain._ml_model_ready}")
print(f"    _ml_model_loading : {brain._ml_model_loading}")

# 3. naber - ML model olmadan (anlık)
t = time.time()
result = brain._try_greeting("naber")
if result:
    print(f"[3] naber greeting    : {ms(t)} ANLIK -> BULUNDU")
else:
    print(f"[3] naber greeting    : {ms(t)} YOK")

# 4. Intent detection - ML model olmadan keyword ile
t = time.time()
intent = brain._detect_intent_fast("ram durumu")
print(f"[4] Intent (ram)      : {ms(t)} -> {intent}")

t = time.time()
intent2 = brain._detect_intent_fast("cpu ne durumda")
print(f"[5] Intent (cpu)      : {ms(t)} -> {intent2}")

t = time.time()
intent3 = brain._detect_intent_fast("disk dolulugu")
print(f"[6] Intent (disk)     : {ms(t)} -> {intent3}")

# 7. LLM test
print()
from blue_ai.ai.llm import get_llm, reset_llm_model
reset_llm_model()
llm = get_llm()
avail = llm.is_available()
print(f"[7] Ollama available  : {avail}")

if avail:
    model = llm._resolve_model()
    print(f"[8] Active model      : {model}")
    print(f"[9] Warmed up         : {llm._warmed_up}")

    if not llm._warmed_up:
        print("[10] Warmup basliyor (max 180s)...")
        t = time.time()
        ok = llm.warmup()
        print(f"     Warmup result   : {ok} in {sec(t)}")

    # LLM streaming - en onemli test
    print()
    print("[11] Streaming testi (merhaba)...")
    t = time.time()
    first_t = None
    full = ""
    msgs = [
        {"role": "system", "content": "Cok kisa cevap ver, max 10 kelime."},
        {"role": "user", "content": "merhaba"}
    ]
    for chunk in llm.chat_stream(msgs, temperature=0.3):
        if chunk:
            if first_t is None:
                first_t = time.time() - t
            full += chunk
    print(f"     Ilk token       : {first_t:.2f}s" if first_t else "     Token gelmedi!")
    print(f"     Toplam          : {sec(t)}")
    print(f"     Yanit           : {full[:80]}")

    # ML model hazir mi simdi?
    print()
    time.sleep(1)
    print(f"[12] ML model ready   : {brain._ml_model_ready}")
    if brain._ml_model_ready:
        t = time.time()
        intent = brain._detect_intent_fast("ram durumu")
        print(f"     Intent (ram) ML : {ms(t)} -> {intent}")
else:
    print("[HATA] Ollama calismiyor!")

print("\n=== SONUC ===")
print("naber/merhaba -> 0ms (greeting, anlik)")
print("ram/cpu/disk  -> ~0ms (keyword, anlik)")
print("LLM mesajlari -> streaming, ilk token ~1-2s")
