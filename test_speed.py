"""BLUE_AI hiz testi"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Force ASCII output for Windows terminal
sys.stdout.reconfigure(encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'reconfigure') else None

def ms(t): return f"{(time.time()-t)*1000:.0f}ms"
def sec(t): return f"{time.time()-t:.2f}s"
def p(s): print(s.encode('ascii', errors='replace').decode())

p("=== BLUE_AI HIZ TESTI ===\n")

# 1. Brain import
t = time.time()
from blue_ai.brain.brain import get_brain
p(f"[1] Brain import      : {ms(t)}  <-- 1.5s ise burasi sorun!")

# 2. Brain init (tools register)
t = time.time()
brain = get_brain()
brain.initialize()
p(f"[2] Brain init+tools  : {ms(t)}")

# 3. naber
t = time.time()
result = brain._try_greeting("naber")
msg = result.message if result else "YOK - LLM gidecek!"
p(f"[3] naber greeting    : {ms(t)} -> {msg[:40].encode('ascii','replace').decode()}")

# 4. merhaba
t = time.time()
result2 = brain._try_greeting("merhaba")
p(f"[4] merhaba greeting  : {ms(t)} -> {'BULUNDU' if result2 else 'YOK'}")

# 5. ML model
t = time.time()
ml = brain._predict_with_ml_model("sistem durumu")
p(f"[5] ML model          : {ms(t)} -> {ml}")

# 6. Intent detection
t = time.time()
intent = brain._detect_intent_fast("ram durumu")
p(f"[6] Intent (ram)      : {ms(t)} -> {intent}")

# 7. System prompt build
t = time.time()
prompt = brain._context.build_system_prompt()
p(f"[7] System prompt     : {ms(t)} -> {len(prompt)} chars")

# 8. LLM
p("\n--- LLM TESTI ---")
t = time.time()
from blue_ai.ai.llm import get_llm, reset_llm_model
reset_llm_model()
llm = get_llm()
avail = llm.is_available()
p(f"[8] LLM available     : {ms(t)} -> {avail}")

if avail:
    t = time.time()
    model = llm._resolve_model()
    p(f"[9] Active model      : {ms(t)} -> {model}")
    p(f"[10] Warmed up        : {llm._warmed_up}")

    p("\n[11] LLM warmup testi...")
    t = time.time()
    llm.warmup()
    p(f"     Warmup           : {sec(t)}")

    p("\n[12] LLM chat testi (naber)...")
    t = time.time()
    msgs = [
        {"role": "system", "content": "Cok kisa cevap ver."},
        {"role": "user", "content": "naber"}
    ]
    resp = llm.chat(msgs, temperature=0.3)
    p(f"     LLM yanit        : {sec(t)} -- {resp[:60].encode('ascii','replace').decode()}")

    p("\n[13] Streaming testi...")
    t = time.time()
    first_t = None
    full = ""
    for chunk in llm.chat_stream(msgs, temperature=0.3):
        if chunk:
            if first_t is None:
                first_t = time.time() - t
            full += chunk
    p(f"     Ilk token        : {first_t:.2f}s" if first_t else "     Hicbir token gelmedi!")
    p(f"     Toplam streaming : {sec(t)}")
    p(f"     Karakter sayisi  : {len(full)}")
else:
    p("[HATA] Ollama calismiyor!")
    p(f"       URL: {llm.base_url}")
    p("       Cozum: 'ollama serve' komutunu calistirin")

p("\n=== TEST BITTI ===")
