"""
BLUE_AI — Dataset Generator
100.000+ Turkce egitim ornegi uretir.
Temel ornekleri synonym, prefix, suffix, parametre ve karakter degisimleriyle cogaltir.
"""

import json
import random
import itertools
import os
from pathlib import Path
from copy import deepcopy

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "training"


# ============================================================
# TURKCE AUGMENTASYON ARACLARI
# ============================================================

# Onekler — cumle basina eklenir
PREFIXES = [
    "", "lutfen ", "hemen ", "acil ", "bana ", "bir ", "simdi ",
    "hadi ", "canim ", "rica etsem ", "mumkunse ", "olur mu ",
    "yardim et ", "sana zahmet ", "bi ", "abi ", "kardes ",
    "hey blue ", "blue ", "hey ", "selam ", "bak ",
]

# Sonekler — cumle sonuna eklenir
SUFFIXES = [
    "", " yapar misin", " yapabilir misin", " yap", " etsene",
    " eder misin", " bakar misin", " mumkun mu", " olur mu",
    " lazim", " istiyorum", " gerekiyor", " soyle", " goster",
    " lutfen", " hemen", " acil", " bi bakar misin",
]

# Turkce karakter degisimleri (karektersiz yazanlar icin)
CHAR_MAP = {
    "ı": "i", "İ": "I", "ö": "o", "Ö": "O",
    "ü": "u", "Ü": "U", "ş": "s", "Ş": "S",
    "ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G",
}

# Genel esanlamlilar
SYNONYMS = {
    "ac": ["baslat", "calistir", "getir", "yukle"],
    "kapat": ["sonlandir", "bitir", "durdur", "kapa"],
    "goster": ["goruntule", "listele", "yazdir", "sun"],
    "ara": ["bul", "tara", "arat", "kontrol et"],
    "sil": ["kaldir", "temizle", "at", "cikar"],
    "gonder": ["yolla", "ilet", "at", "postalat"],
    "yaz": ["olustur", "hazirla", "kaleme al", "duz"],
    "oku": ["goruntule", "kontrol et", "bak", "incele"],
    "ayarla": ["degistir", "duzenle", "yapistir", "belirle"],
    "hesapla": ["bul", "say", "olc", "cikar"],
    "kaydet": ["sakla", "depola", "yedekle", "tut"],
    "indir": ["yukle", "cek", "al", "getir"],
    "yukle": ["kur", "install et", "ekle"],
    "duzenle": ["edit et", "degistir", "guncelle", "revize et"],
    "bilgi": ["detay", "veri", "data", "info"],
    "yardim": ["destek", "asistanlik", "help"],
    "kontrol": ["check", "denetle", "incele", "tara"],
    "dosya": ["belge", "file", "dokuman"],
    "klasor": ["dizin", "folder", "directory"],
    "uygulama": ["program", "yazilim", "app", "aplikasyon"],
    "bilgisayar": ["pc", "sistem", "makine", "cihaz"],
    "internet": ["web", "net", "ag", "online"],
    "hizli": ["cabuk", "seri", "acil", "ivedi"],
    "buyuk": ["iri", "genis", "kapali", "dev"],
    "kucuk": ["mini", "ufak", "minik"],
}

# Uygulama isimleri (parametre degisimi icin)
APP_NAMES = [
    "chrome", "firefox", "edge", "opera", "brave",
    "word", "excel", "powerpoint", "notepad", "notepad++",
    "vscode", "visual studio", "sublime text",
    "spotify", "vlc", "windows media player",
    "discord", "telegram", "whatsapp", "skype", "zoom", "teams",
    "paint", "photoshop", "gimp",
    "steam", "epic games",
    "cmd", "terminal", "powershell",
    "dosya yoneticisi", "explorer", "task manager", "gorev yoneticisi",
    "hesap makinesi", "calculator", "takvim", "calendar",
]

# Kisi isimleri
PERSON_NAMES = [
    "Ahmet", "Mehmet", "Ali", "Ayse", "Fatma", "Zeynep",
    "Emre", "Can", "Ece", "Deniz", "Mert", "Selin",
    "Burak", "Kerem", "Elif", "Hakan", "Serkan", "Cem",
    "Berk", "Arda", "Yusuf", "Omer", "Mustafa", "Hasan",
    "Ozge", "Irem", "Merve", "Tugba", "Esra", "Gizem",
    "annem", "babam", "abim", "ablam", "arkadasim", "patronum",
    "ogretmenim", "musterim", "is arkadasim", "komsum",
]

# Konu/Subject listesi
TOPICS = [
    "yapay zeka", "makine ogrenimi", "python programlama", "web gelistirme",
    "veri bilimi", "siber guvenlik", "bulut bilisim", "mobil uygulama",
    "blockchain", "nesnelerin interneti", "robotik", "oyun gelistirme",
    "pazarlama stratejisi", "is plani", "finansal analiz", "proje yonetimi",
    "insan kaynaklari", "dijital pazarlama", "e-ticaret", "sosyal medya",
    "saglıkli beslenme", "egzersiz programi", "stres yonetimi", "meditasyon",
    "turkiye tarihi", "dunya tarihi", "felsefe", "psikoloji", "sosyoloji",
    "fizik", "kimya", "biyoloji", "matematik", "astronomi",
    "ingilizce ogrenmek", "almanca ogrenmek", "fransizca ogrenmek",
    "fotograf cekim teknikleri", "video kurgu", "muzik teorisi",
    "yemek tarifleri", "seyahat planlama", "butce yonetimi",
    "cv hazirlama", "is basvurusu", "mulakat teknikleri",
    "elektrik tasarrufu", "su tasarrufu", "cevre koruma",
]

# Dosya uzantilari
FILE_TYPES = [
    ".docx", ".xlsx", ".pptx", ".pdf", ".txt", ".jpg", ".png",
    ".mp4", ".mp3", ".zip", ".rar", ".csv", ".json", ".html",
    ".py", ".js", ".exe", ".iso", ".psd", ".svg",
]

# URL'ler
URLS = [
    "google.com", "youtube.com", "twitter.com", "instagram.com",
    "facebook.com", "linkedin.com", "github.com", "stackoverflow.com",
    "wikipedia.org", "amazon.com.tr", "hepsiburada.com", "trendyol.com",
    "sahibinden.com", "hurriyet.com.tr", "sozcu.com.tr", "ntv.com.tr",
]

# Sehirler
CITIES = [
    "Istanbul", "Ankara", "Izmir", "Bursa", "Antalya", "Adana",
    "Konya", "Gaziantep", "Trabzon", "Eskisehir", "Samsun", "Mersin",
    "Diyarbakir", "Kayseri", "Mugla", "Bodrum", "Marmaris",
    "Paris", "Londra", "New York", "Tokyo", "Berlin", "Roma",
]

# Diller
LANGUAGES = [
    "Ingilizce", "Almanca", "Fransizca", "Ispanyolca", "Italyanca",
    "Arapca", "Rusca", "Japonca", "Cince", "Korece", "Portekizce",
]


def remove_turkish_chars(text: str) -> str:
    """Turkce karakterleri ASCII'ye cevir."""
    result = text
    for tr_char, en_char in CHAR_MAP.items():
        result = result.replace(tr_char, en_char)
    return result


def apply_synonym(text: str) -> list[str]:
    """Esanlamli kelime degisimi uygula."""
    results = [text]
    words = text.split()
    for i, word in enumerate(words):
        w_lower = word.lower()
        if w_lower in SYNONYMS:
            for syn in SYNONYMS[w_lower]:
                new_words = words.copy()
                new_words[i] = syn
                results.append(" ".join(new_words))
    return results[:5]  # En fazla 5 varyant


def augment_single(text: str, intent: str, target_count: int = 50) -> list[dict]:
    """Tek bir cumleyi cogalt."""
    results = set()
    results.add(text)

    # 1. Turkce karakter kaldirma
    no_tr = remove_turkish_chars(text)
    results.add(no_tr)

    # 2. Esanlamli degisimler
    for syn_text in apply_synonym(text):
        results.add(syn_text)
        results.add(remove_turkish_chars(syn_text))

    # 3. Prefix ekleme
    base_texts = list(results)[:10]
    for bt in base_texts:
        for prefix in random.sample(PREFIXES, min(6, len(PREFIXES))):
            if prefix and not bt.startswith(prefix.strip()):
                results.add(f"{prefix}{bt}")

    # 4. Suffix ekleme
    base_texts = list(results)[:20]
    for bt in base_texts:
        for suffix in random.sample(SUFFIXES, min(4, len(SUFFIXES))):
            if suffix and not bt.endswith(suffix.strip()):
                results.add(f"{bt}{suffix}")

    # 5. Buyuk/kucuk harf varyantlari
    base_texts = list(results)[:15]
    for bt in base_texts:
        results.add(bt.lower())
        results.add(bt.capitalize())
        results.add(bt.upper())

    final = [{"text": r.strip(), "intent": intent} for r in results if r.strip()]
    random.shuffle(final)
    return final[:target_count]


def augment_with_params(template: str, intent: str, param_key: str, param_values: list) -> list[dict]:
    """Sablondaki {param} yerine farkli degerleri koy."""
    results = []
    for val in param_values:
        text = template.replace(f"{{{param_key}}}", val)
        results.append({"text": text, "intent": intent})
        results.append({"text": remove_turkish_chars(text), "intent": intent})
        # Prefix/suffix ekle
        prefix = random.choice(PREFIXES)
        suffix = random.choice(SUFFIXES)
        if prefix:
            results.append({"text": f"{prefix}{text}", "intent": intent})
        if suffix:
            results.append({"text": f"{text}{suffix}", "intent": intent})
    return results


def generate_full_dataset(base_path: str, output_path: str, target_total: int = 100000):
    """Tam veri seti uret."""
    with open(base_path, "r", encoding="utf-8") as f:
        base_data = json.load(f)

    all_examples = []
    intent_counts = {}

    # Her intent icin ornekleri cogalt
    for item in base_data["data"]:
        text = item["text"]
        intent = item["intent"]
        intent_counts[intent] = intent_counts.get(intent, 0) + 1

    num_intents = len(intent_counts)
    per_intent_target = target_total // num_intents

    print(f"Toplam {num_intents} intent kategorisi")
    print(f"Hedef: intent basina ~{per_intent_target} ornek")

    # Intent bazinda grupla
    intent_groups = {}
    for item in base_data["data"]:
        intent = item["intent"]
        if intent not in intent_groups:
            intent_groups[intent] = []
        intent_groups[intent].append(item["text"])

    # Her grubu cogalt
    for intent, texts in intent_groups.items():
        intent_examples = []
        per_text_target = per_intent_target // len(texts) + 1

        for text in texts:
            augmented = augment_single(text, intent, target_count=per_text_target)
            intent_examples.extend(augmented)

        # Benzersiz yap
        seen = set()
        unique = []
        for ex in intent_examples:
            key = ex["text"].lower().strip()
            if key not in seen and len(key) > 2:
                seen.add(key)
                unique.append(ex)

        # Hedefe ulasmak icin ekstra uret
        while len(unique) < per_intent_target:
            base_text = random.choice(texts)
            prefix = random.choice(PREFIXES)
            suffix = random.choice(SUFFIXES)
            new_text = f"{prefix}{base_text}{suffix}".strip()
            key = new_text.lower()
            if key not in seen and len(key) > 2:
                seen.add(key)
                unique.append({"text": new_text, "intent": intent})

        all_examples.extend(unique[:per_intent_target])
        print(f"  {intent}: {len(unique[:per_intent_target])} ornek")

    # Karistir
    random.shuffle(all_examples)

    # Kaydet
    output = {
        "meta": {
            "total_examples": len(all_examples),
            "num_intents": num_intents,
            "intents": list(intent_counts.keys()),
        },
        "data": all_examples,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nToplam {len(all_examples)} ornek uretildi → {output_path}")
    return output


if __name__ == "__main__":
    base_path = str(DATA_DIR / "base_intents.json")
    output_path = str(DATA_DIR / "intent_dataset.json")

    if not os.path.exists(base_path):
        print(f"HATA: {base_path} bulunamadi!")
        print("Once base_intents.json dosyasini olusturun.")
    else:
        generate_full_dataset(base_path, output_path, target_total=100000)
