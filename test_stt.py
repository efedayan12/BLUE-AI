"""
BLUE_AI — STT Motor Testi

Kullanım:
  python test_stt.py           # Config'deki motoru test et
  python test_stt.py vosk      # Vosk'u test et
  python test_stt.py whisper   # Whisper'ı test et
  python test_stt.py her_ikisi # Her ikisini sırayla test et
"""

import sys
import time

def test_engine(engine_name: str):
    print(f"\n{'='*50}")
    print(f"  Motor: {engine_name.upper()}")
    print(f"{'='*50}")

    # Singleton'ı sıfırla — her test temiz başlasın
    import blue_ai.voice.stt as stt_mod
    stt_mod._stt = None

    start = time.time()
    stt = stt_mod.get_stt(engine=engine_name)
    load_ok = stt.load_model()
    load_time = time.time() - start

    if not load_ok:
        print(f"[HATA] {engine_name} modeli yüklenemedi!")
        return

    print(f"[OK] Model yükleme: {load_time:.2f}s")
    print("Konuşun... (sessizlikte otomatik durur)")

    rec_start = time.time()
    text = stt.record_until_silence(max_duration=10)
    rec_time = time.time() - rec_start

    if text:
        print(f"[OK] Tanınan ({rec_time:.2f}s): '{text}'")
    else:
        print(f"[!] Ses algılanamadı ({rec_time:.2f}s)")

    # Singleton'ı temizle
    stt_mod._stt = None


def main():
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else "config"

    if arg in ("her_ikisi", "both", "all"):
        test_engine("vosk")
        test_engine("whisper")
    elif arg in ("vosk", "whisper"):
        test_engine(arg)
    else:
        # Config'den oku
        import blue_ai.voice.stt as stt_mod
        stt_mod._stt = None
        stt = stt_mod.get_stt()
        engine_name = type(stt).__name__
        print(f"\nConfig'deki motor: {engine_name}")
        stt_mod._stt = None
        if "Vosk" in engine_name:
            test_engine("vosk")
        else:
            test_engine("whisper")


if __name__ == "__main__":
    main()
