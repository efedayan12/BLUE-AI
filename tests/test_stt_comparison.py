"""
BLUE_AI — STT Motor Karşılaştırma Testi

Whisper ve Vosk STT motorlarını karşılaştırır:
 - Model yükleme süresi
 - Çözümleme (transkripsiyon) süresi
 - Bellek kullanımı
 - Canlı karşılaştırma (mikrofon testi)

Kullanım:
    python tests/test_stt_comparison.py
    python tests/test_stt_comparison.py --live    # Canlı mikrofon testi
"""

import os
import sys
import time
import argparse
import tempfile

# Proje kökünü path'e ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


def get_memory_mb() -> float:
    """Mevcut sürecin bellek kullanımını döndür (MB)."""
    if PSUTIL_AVAILABLE:
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    return 0.0


def test_whisper():
    """Whisper STT motorunu test et."""
    print("\n" + "=" * 60)
    print("🎙️  WHISPER (Faster-Whisper) TESTİ")
    print("=" * 60)

    results = {
        "engine": "Whisper (faster-whisper)",
        "load_time": 0,
        "memory_before": 0,
        "memory_after": 0,
        "memory_delta": 0,
        "available": False,
    }

    try:
        from blue_ai.voice.stt import STTEngine
    except ImportError as e:
        print(f"❌ Import hatası: {e}")
        return results

    # Model yükleme testi
    mem_before = get_memory_mb()
    results["memory_before"] = round(mem_before, 1)

    engine = STTEngine(model_size="tiny", device="cpu", compute_type="int8")

    print(f"  Model: tiny | Device: cpu | Compute: int8")
    print(f"  Bellek (önce): {mem_before:.1f} MB")

    start = time.perf_counter()
    success = engine.load_model()
    load_time = time.perf_counter() - start

    results["load_time"] = round(load_time, 3)
    results["available"] = success

    if success:
        mem_after = get_memory_mb()
        results["memory_after"] = round(mem_after, 1)
        results["memory_delta"] = round(mem_after - mem_before, 1)

        print(f"  ✅ Model yüklendi: {load_time:.3f}s")
        print(f"  Bellek (sonra): {mem_after:.1f} MB (+{mem_after - mem_before:.1f} MB)")
    else:
        print(f"  ❌ Model yüklenemedi")

    return results


def test_vosk():
    """Vosk STT motorunu test et."""
    print("\n" + "=" * 60)
    print("🎙️  VOSK (Vosk-API) TESTİ")
    print("=" * 60)

    results = {
        "engine": "Vosk (vosk-api)",
        "load_time": 0,
        "memory_before": 0,
        "memory_after": 0,
        "memory_delta": 0,
        "available": False,
    }

    try:
        from blue_ai.voice.stt_vosk import VoskSTTEngine
    except ImportError as e:
        print(f"❌ Import hatası: {e}")
        return results

    # Model yükleme testi
    mem_before = get_memory_mb()
    results["memory_before"] = round(mem_before, 1)

    engine = VoskSTTEngine(model_size="small")

    print(f"  Model: small | Tamamen CPU")
    print(f"  Bellek (önce): {mem_before:.1f} MB")

    start = time.perf_counter()
    success = engine.load_model()
    load_time = time.perf_counter() - start

    results["load_time"] = round(load_time, 3)
    results["available"] = success

    if success:
        mem_after = get_memory_mb()
        results["memory_after"] = round(mem_after, 1)
        results["memory_delta"] = round(mem_after - mem_before, 1)

        print(f"  ✅ Model yüklendi: {load_time:.3f}s")
        print(f"  Bellek (sonra): {mem_after:.1f} MB (+{mem_after - mem_before:.1f} MB)")
    else:
        print(f"  ❌ Model yüklenemedi (model indirmek gerekiyor olabilir)")

    return results


def test_live_comparison():
    """Canlı mikrofon ile her iki motoru karşılaştır."""
    print("\n" + "=" * 60)
    print("🎤  CANLI MİKROFON KARŞILAŞTIRMASI")
    print("=" * 60)

    import sounddevice as sd
    import soundfile as sf
    import numpy as np

    print("\n  5 saniye konuşun. Kayıt başlıyor...")
    print("  3...", end=" ", flush=True)
    time.sleep(1)
    print("2...", end=" ", flush=True)
    time.sleep(1)
    print("1...", end=" ", flush=True)
    time.sleep(1)
    print("🔴 KAYIT!")

    samplerate = 16000
    duration = 5
    audio = sd.rec(
        int(duration * samplerate),
        samplerate=samplerate,
        channels=1,
        dtype='float32'
    )
    sd.wait()
    print("  ✅ Kayıt tamamlandı!\n")

    # Geçici dosyaya kaydet
    temp_dir = tempfile.gettempdir()
    wav_file = os.path.join(temp_dir, "blue_ai_stt_benchmark.wav")
    sf.write(wav_file, audio, samplerate)

    # Whisper testi
    print("  --- Whisper ile çözümleme ---")
    try:
        from blue_ai.voice.stt import STTEngine
        whisper_engine = STTEngine(model_size="tiny", device="cpu", compute_type="int8")
        whisper_engine.load_model()

        start = time.perf_counter()
        whisper_text = whisper_engine.transcribe_file(wav_file)
        whisper_time = time.perf_counter() - start

        print(f"  Sonuç: \"{whisper_text}\"")
        print(f"  Süre: {whisper_time:.3f}s")
    except Exception as e:
        print(f"  ❌ Whisper hatası: {e}")
        whisper_text = ""
        whisper_time = 0

    # Vosk testi
    print("\n  --- Vosk ile çözümleme ---")
    try:
        from blue_ai.voice.stt_vosk import VoskSTTEngine

        # Vosk int16 formatı bekler — yeniden kaydet
        audio_int16 = (audio * 32767).astype(np.int16)
        wav_file_16 = os.path.join(temp_dir, "blue_ai_stt_benchmark_16.wav")
        sf.write(wav_file_16, audio_int16, samplerate, subtype='PCM_16')

        vosk_engine = VoskSTTEngine(model_size="small")
        vosk_engine.load_model()

        start = time.perf_counter()
        vosk_text = vosk_engine.transcribe_file(wav_file_16)
        vosk_time = time.perf_counter() - start

        print(f"  Sonuç: \"{vosk_text}\"")
        print(f"  Süre: {vosk_time:.3f}s")
    except Exception as e:
        print(f"  ❌ Vosk hatası: {e}")
        vosk_text = ""
        vosk_time = 0

    print("\n  --- KARŞILAŞTIRMA ---")
    print(f"  {'Metrik':<25} {'Whisper':<25} {'Vosk':<25}")
    print(f"  {'-'*75}")
    print(f"  {'Çözümleme süresi':<25} {whisper_time:.3f}s{'':<20} {vosk_time:.3f}s")
    print(f"  {'Tanınan metin':<25} {whisper_text[:22]:<25} {vosk_text[:22]:<25}")

    if whisper_time > 0 and vosk_time > 0:
        faster = "Vosk" if vosk_time < whisper_time else "Whisper"
        ratio = max(whisper_time, vosk_time) / max(min(whisper_time, vosk_time), 0.001)
        print(f"\n  🏆 Daha hızlı: {faster} ({ratio:.1f}x)")


def print_summary(whisper_results, vosk_results):
    """Özet tablo yazdır."""
    print("\n" + "=" * 60)
    print("📊  ÖZET KARŞILAŞTIRMA")
    print("=" * 60)

    print(f"\n  {'Metrik':<25} {'Whisper':<20} {'Vosk':<20}")
    print(f"  {'-'*65}")
    print(f"  {'Durum':<25} {'✅ Hazır' if whisper_results['available'] else '❌ Yok':<20} {'✅ Hazır' if vosk_results['available'] else '❌ Yok':<20}")
    print(f"  {'Model yükleme':<25} {whisper_results['load_time']:.3f}s{'':<14} {vosk_results['load_time']:.3f}s")
    print(f"  {'Bellek kullanımı':<25} +{whisper_results['memory_delta']:.0f} MB{'':<12} +{vosk_results['memory_delta']:.0f} MB")
    print(f"  {'Çalışma modu':<25} {'CPU/GPU':<20} {'Sadece CPU':<20}")
    print(f"  {'Offline destek':<25} {'✅ Evet':<20} {'✅ Evet':<20}")
    print(f"  {'Gerçek zamanlı':<25} {'❌ Hayır':<20} {'✅ Evet':<20}")
    print(f"  {'Model boyutu (tiny/sm)':<25} {'~75 MB':<20} {'~45 MB':<20}")
    print(f"  {'Doğruluk (genel)':<25} {'⭐⭐⭐⭐⭐':<20} {'⭐⭐⭐':<20}")

    print(f"\n  📝 Sonuç:")
    if whisper_results['available'] and vosk_results['available']:
        if whisper_results['load_time'] > vosk_results['load_time']:
            print(f"     Vosk {whisper_results['load_time']/max(vosk_results['load_time'], 0.001):.1f}x daha hızlı yükleniyor")
        else:
            print(f"     Whisper {vosk_results['load_time']/max(whisper_results['load_time'], 0.001):.1f}x daha hızlı yükleniyor")
        print(f"     Whisper genellikle daha doğru sonuç verir")
        print(f"     Vosk gerçek zamanlı streaming yapabilir (Whisper yapamaz)")
    elif whisper_results['available']:
        print(f"     Sadece Whisper kullanılabilir. Vosk için: pip install vosk")
    elif vosk_results['available']:
        print(f"     Sadece Vosk kullanılabilir. Whisper için: pip install faster-whisper")
    else:
        print(f"     Hiçbir STT motoru kullanılamıyor!")
        print(f"     pip install faster-whisper vosk")


def main():
    parser = argparse.ArgumentParser(description="BLUE_AI STT Motor Karşılaştırması")
    parser.add_argument("--live", action="store_true", help="Canlı mikrofon testi")
    args = parser.parse_args()

    print("🔵 BLUE_AI — STT Motor Karşılaştırma Testi")
    print("=" * 60)

    # Motor testleri
    whisper_results = test_whisper()
    vosk_results = test_vosk()

    # Özet
    print_summary(whisper_results, vosk_results)

    # Canlı test
    if args.live:
        try:
            test_live_comparison()
        except Exception as e:
            print(f"\n❌ Canlı test hatası: {e}")
            print("   Mikrofon bağlı olduğundan emin olun.")

    print("\n✅ Test tamamlandı!")


if __name__ == "__main__":
    main()
