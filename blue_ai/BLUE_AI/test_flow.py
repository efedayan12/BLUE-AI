"""start_chat_stream'in tam akisini simule eder — PyWebView olmadan."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def ms(t): return f"{(time.time()-t)*1000:.0f}ms"
def sec(t): return f"{time.time()-t:.2f}s"
def p(s): print(s)

p("=== AKIS TESTI ===\n")

# Tam olarak start_chat_stream'in yaptigi seyleri adim adim olcuyoruz

t0 = time.time()

# Adim 1: _get_brain
t = time.time()
from blue_ai.brain.brain import get_brain
brain = get_brain()
p(f"[A] get_brain()                   : {ms(t)}")

# Adim 2: brain.initialize
t = time.time()
brain.initialize()
p(f"[B] brain.initialize()            : {ms(t)}")

# Adim 3: ML model bg
t = time.time()
brain._load_ml_model_bg()
p(f"[C] _load_ml_model_bg()           : {ms(t)} (background)")

# Adim 4: dil tespiti
t = time.time()
brain._context.auto_detect_and_set_language("naber")
p(f"[D] auto_detect_language(naber)   : {ms(t)}")

# Adim 5: selamlama
t = time.time()
greeting = brain._try_greeting("naber")
p(f"[E] _try_greeting(naber)          : {ms(t)} -> {'BULUNDU' if greeting else 'YOK'}")

# Adim 6: context add
t = time.time()
brain._context.add_user_message("naber")
brain._context.add_assistant_message(greeting.message if greeting else "test")
p(f"[F] add_messages()                : {ms(t)}")

# Adim 7: _speak_if_enabled — bu TTS cagiriyor, yavas olabilir!
p(f"\n[G] _speak_if_enabled testi:")

# Onu simule edelim — voice enabled mi?
config_path = os.path.join(os.path.dirname(__file__), "config", "blue_ai.toml")
voice_enabled = False
if os.path.exists(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    in_voice = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == '[voice]':
            in_voice = True
        elif stripped.startswith('[') and in_voice:
            in_voice = False
        elif in_voice and stripped.startswith('enabled'):
            voice_enabled = 'true' in stripped.lower()
            break

p(f"    voice enabled                 : {voice_enabled}")

if voice_enabled:
    t = time.time()
    try:
        from blue_ai.voice.tts import get_tts
        tts = get_tts()
        p(f"    TTS import                    : {ms(t)}")
        p(f"    TTS tipi                      : {type(tts).__name__}")
        # TTS speak cagirma (thread'de mi calisiyor kontrol et)
        import inspect
        speak_src = inspect.getsource(tts.speak)
        if 'thread' in speak_src.lower() or 'Thread' in speak_src:
            p("    TTS.speak THREAD kullanıyor  : EVET (non-blocking)")
        else:
            p("    TTS.speak THREAD kullanıyor  : HAYIR - BLOCKING OLABILIR!")
    except Exception as e:
        p(f"    TTS hata: {e}")

# Adim 8: memory modulu
p(f"\n[H] Memory modulu testi:")
t = time.time()
try:
    from blue_ai.memory.manager import get_memory
    mem = get_memory()
    p(f"    get_memory()                  : {ms(t)}")
    t = time.time()
    ctx = mem.generate_context_string()
    p(f"    generate_context_string()     : {ms(t)}")
    p(f"    Icerik                        : {str(ctx)[:60]}")
except Exception as e:
    p(f"    Memory hata: {e}")

# Adim 9: build_system_prompt
p(f"\n[I] System prompt build:")
t = time.time()
prompt = brain._context.build_system_prompt()
p(f"    build_system_prompt()          : {ms(t)} -> {len(prompt)} chars")

# Toplam
p(f"\n[TOPLAM] Naber icin toplam sure  : {ms(t0)}")
p("(Bu sure PyWebView overhead'i olmadan)")

p("\n=== YAVASLAYAN ADIMI BULDUK MU? ===")
