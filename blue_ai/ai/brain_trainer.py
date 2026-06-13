"""
BLUE_AI — Brain-Aware Model Trainer

Mevcut 123 intent'lik veri setini yeni Brain tool sistemine
uygun şekilde dönüştürür ve ML modelini eğitir.

Eski intent'ler → Yeni tool adları mapping'i yapılır.
Bu model LLM olmadığında (offline fallback) kullanılır.
"""

import json
import time
import sys
import os
from pathlib import Path
from collections import Counter

from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV

try:
    import joblib
except ImportError:
    from sklearn.externals import joblib


# Paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
TRAINING_DIR = DATA_DIR / "training"
MODELS_DIR = DATA_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = MODELS_DIR / "brain_intent_model.joblib"


# ═══════════════════════════════════════════════════
#  INTENT → TOOL MAPPING
# ═══════════════════════════════════════════════════
# Eski 123 intent'i yeni 19 tool + conversation kategorilerine map'le

INTENT_TO_TOOL = {
    # ─── Sistem Durumu ───
    "system_status": "system_status",
    "system_info_detailed": "system_status",
    "cpu_info": "system_status",

    # ─── RAM ───
    "ram_info": "ram_info",

    # ─── Disk ───
    "disk_info": "disk_info",

    # ─── Pil ───
    "battery_info": "battery_info",

    # ─── Ağ ───
    "network_info": "network_info",
    "toggle_wifi": "network_info",
    "toggle_bluetooth": "network_info",

    # ─── Süreç Listesi ───
    "process_list": "process_list",

    # ─── Süreç Sonlandırma ───
    "process_kill": "process_kill",

    # ─── Temizlik ───
    "clean_system": "clean_temp",
    "optimize_system": "clean_temp",

    # ─── Profil Değişikliği ───
    "gaming_mode": "change_profile",
    "work_mode": "change_profile",
    "power_saver_mode": "change_profile",
    "balanced_mode": "change_profile",
    "focus_mode": "change_profile",
    "night_mode": "change_profile",

    # ─── Uygulama Açma ───
    "open_app": "open_app",
    "install_app": "open_app",

    # ─── Uygulama Kapatma ───
    "close_app": "close_app",

    # ─── Web Arama ───
    "web_search": "web_search",
    "web_news": "smart_web_search",
    "web_weather": "smart_web_search",
    "web_download": "web_search",
    "recipe_search": "smart_web_search",
    "find_place": "smart_web_search",
    "get_directions": "smart_web_search",
    "price_compare": "smart_web_search",
    "youtube_search": "web_search",
    "fact_check": "smart_web_search",

    # ─── URL Açma ───
    "open_url": "open_url",
    "youtube_play": "open_url",

    # ─── Dosya Arama ───
    "file_search": "file_search",
    "file_info": "file_search",

    # ─── Belge Oluşturma ───
    "create_document": "create_document",
    "write_letter": "create_document",
    "write_message": "create_document",
    "edit_document": "create_document",

    # ─── Excel ───
    "create_spreadsheet": "create_spreadsheet",

    # ─── Sunum ───
    "create_presentation": "create_presentation",

    # ─── Yardım ───
    "help": "help",
    "who_are_you": "help",

    # ─── Dosya İşlemleri ───
    "file_copy": "file_search",
    "file_move": "file_search",
    "file_delete": "file_search",
    "file_rename": "file_search",
    "file_organize": "file_search",
    "file_compress": "file_search",
    "file_extract": "file_search",
    "folder_create": "file_search",
    "read_pdf": "file_search",
    "print_document": "file_search",

    # ─── Sistem Kontrolü (artık kendi tool'ları var) ───
    "shutdown_pc": "shutdown_pc",
    "restart_pc": "restart_pc",
    "lock_screen": "lock_screen",
    "sleep_mode": "lock_screen",
    "change_brightness": "change_volume",  # Benzer mekanizma
    "change_volume": "change_volume",
    "change_wallpaper": "system_status",
    "take_screenshot": "take_screenshot",
    "screen_record": "take_screenshot",
    "startup_manage": "system_status",
    "clipboard_manage": "system_status",
    "virus_scan": "system_status",
    "privacy_check": "system_status",

    # ─── Zaman ───
    "show_time": "show_time",
    "show_date": "show_time",
    "set_alarm": "set_reminder",
    "set_reminder": "set_reminder",
    "set_timer": "set_reminder",
    "calendar_event": "set_reminder",
    "schedule_meeting": "set_reminder",
    "pomodoro_start": "set_reminder",

    # ─── İletişim (artık kendi tool'ları var) ───
    "gmail_send": "gmail_send",
    "gmail_read": "gmail_read",
    "gmail_draft": "gmail_send",
    "gmail_reply": "gmail_read",
    "gmail_forward": "gmail_read",
    "gmail_search": "gmail_read",
    "sms_send": "whatsapp_send",
    "whatsapp_send": "whatsapp_send",
    "whatsapp_read": "whatsapp_send",
    "whatsapp_call": "whatsapp_send",
    "whatsapp_group": "whatsapp_send",
    "whatsapp_media": "whatsapp_send",

    # ─── Genel Sohbet / LLM Yanıtlayacak ───
    "greeting": "general_question",
    "farewell": "general_question",
    "thanks": "general_question",
    "compliment": "general_question",
    "how_are_you": "general_question",
    "small_talk": "general_question",
    "tell_joke": "general_question",
    "tell_story": "general_question",
    "random_fact": "general_question",
    "general_question": "general_question",
    "explain_topic": "general_question",
    "explain_code": "general_question",
    "define_word": "general_question",
    "give_advice": "general_question",
    "health_tip": "general_question",
    "exercise_suggest": "general_question",
    "calorie_info": "general_question",
    "water_reminder": "general_question",
    "translate_text": "general_question",
    "summarize_text": "general_question",
    "write_code": "general_question",
    "debug_help": "general_question",
    "list_steps": "general_question",
    "compare_things": "general_question",
    "convert_unit": "general_question",
    "currency_convert": "general_question",
    "calculate_math": "general_question",
    "password_generate": "general_question",
    "budget_track": "general_question",
    "travel_plan": "general_question",
    "social_post": "general_question",
    "play_music": "general_question",
    "play_game": "general_question",
    "note_take": "general_question",
    "todo_add": "general_question",
    "todo_list": "general_question",
}


# Türkçe karakter normalizasyonu
_CHAR_MAP = {
    "ı": "i", "İ": "I", "ö": "o", "Ö": "O",
    "ü": "u", "Ü": "U", "ş": "s", "Ş": "S",
    "ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G",
}

def normalize_turkish(text: str) -> str:
    text = text.lower().strip()
    for tr, en in _CHAR_MAP.items():
        text = text.replace(tr, en.lower())
    return text


def transform_dataset():
    """Mevcut dataset'i yeni tool mapping ile dönüştür."""
    # Büyük dataset'i kullan (100K+)
    dataset_path = TRAINING_DIR / "intent_dataset.json"
    if not dataset_path.exists():
        # Yoksa base dataset kullan
        dataset_path = TRAINING_DIR / "base_intents.json"

    if not dataset_path.exists():
        print("HATA: Veri seti bulunamadı!")
        sys.exit(1)

    print(f"Veri seti yükleniyor: {dataset_path}")
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    original_data = data["data"]
    print(f"Orijinal veri sayısı: {len(original_data)}")

    # Dönüştür
    transformed = []
    skipped = 0
    unknown_intents = set()

    for item in original_data:
        old_intent = item["intent"]
        new_tool = INTENT_TO_TOOL.get(old_intent)

        if new_tool:
            transformed.append({
                "text": item["text"],
                "intent": new_tool,
                "original_intent": old_intent,
            })
        else:
            unknown_intents.add(old_intent)
            # Bilinmeyen intent'leri general_question'a yönlendir
            transformed.append({
                "text": item["text"],
                "intent": "general_question",
                "original_intent": old_intent,
            })
            skipped += 1

    if unknown_intents:
        print(f"\n⚠️  Mapping'de olmayan {len(unknown_intents)} intent (general_question'a yönlendirildi):")
        for ui in sorted(unknown_intents):
            print(f"  - {ui}")

    # İstatistikler
    label_counts = Counter(item["intent"] for item in transformed)
    print(f"\nDönüştürülmüş veri sayısı: {len(transformed)}")
    print(f"Tool sınıf sayısı: {len(label_counts)}")
    print(f"\nTool dağılımı:")
    for label, count in label_counts.most_common():
        print(f"  {label:25s}: {count:6d} örnek")

    # Kaydet
    output_path = TRAINING_DIR / "brain_dataset.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "meta": {
                "version": "2.0",
                "type": "brain_tool_classification",
                "total_examples": len(transformed),
                "num_tools": len(label_counts),
                "tools": sorted(label_counts.keys()),
                "mapping_source": "intent_to_tool",
            },
            "data": transformed,
        }, f, ensure_ascii=False, indent=2)

    print(f"\nDönüştürülmüş veri seti kaydedildi: {output_path}")
    return transformed


def train_model(data: list[dict] = None):
    """Brain intent modelini eğit."""
    if data is None:
        dataset_path = TRAINING_DIR / "brain_dataset.json"
        if not dataset_path.exists():
            print("Önce veri seti dönüştürülecek...")
            data = transform_dataset()
        else:
            with open(dataset_path, "r", encoding="utf-8") as f:
                data = json.load(f)["data"]

    texts = [normalize_turkish(item["text"]) for item in data]
    labels = [item["intent"] for item in data]

    print(f"\n{'='*60}")
    print(f"BLUE AI Brain Model Eğitimi")
    print(f"{'='*60}")
    print(f"Toplam örnek: {len(texts)}")
    print(f"Toplam sınıf: {len(set(labels))}")

    # Train/Test ayır
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )

    print(f"Eğitim seti: {len(X_train)}")
    print(f"Test seti: {len(X_test)}")

    # Pipeline oluştur
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=50000,
            ngram_range=(1, 3),
            sublinear_tf=True,
            min_df=2,
            max_df=0.95,
            analyzer="char_wb",  # Türkçe için karakter n-gram
        )),
        ("clf", CalibratedClassifierCV(
            LinearSVC(C=1.0, max_iter=5000, class_weight="balanced"),
            cv=3,
        )),
    ])

    print("\nModel eğitiliyor...")
    start = time.time()
    pipeline.fit(X_train, y_train)
    elapsed = time.time() - start
    print(f"Eğitim tamamlandı! ({elapsed:.1f} saniye)")

    # Test
    print("\nTest ediliyor...")
    y_pred = pipeline.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    print(f"\n{'='*60}")
    print(f"DOĞRULUK: %{accuracy*100:.2f}")
    print(f"{'='*60}")

    # Detaylı rapor
    report = classification_report(y_test, y_pred, zero_division=0)
    print(f"\nDetaylı Rapor:\n{report}")

    # Kaydet
    model_data = {
        "pipeline": pipeline,
        "intent_labels": sorted(set(labels)),
        "version": "2.0",
        "type": "brain_tool_classifier",
        "accuracy": accuracy,
    }
    joblib.dump(model_data, str(MODEL_PATH))
    print(f"\nModel kaydedildi: {MODEL_PATH}")

    # Interaktif test
    print(f"\n{'='*60}")
    print("İnteraktif Test (çıkış için 'q' yazın)")
    print(f"{'='*60}")

    import numpy as np
    while True:
        try:
            text = input("\n> ").strip()
            if text.lower() in ("q", "quit", "exit", "cikis", "çıkış"):
                break
            if not text:
                continue

            normalized = normalize_turkish(text)
            intent = pipeline.predict([normalized])[0]
            proba = pipeline.predict_proba([normalized])[0]
            confidence = float(max(proba))

            top_indices = np.argsort(proba)[-3:][::-1]
            classes = pipeline.classes_

            print(f"  Tool: {intent}")
            print(f"  Güven: %{confidence*100:.1f}")
            print(f"  Top 3:")
            for i in top_indices:
                print(f"    - {classes[i]}: %{proba[i]*100:.1f}")

        except (KeyboardInterrupt, EOFError):
            break

    print("\nBitti!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="BLUE AI Brain Model Trainer")
    parser.add_argument("--transform-only", action="store_true", help="Sadece veri setini dönüştür, eğitme")
    parser.add_argument("--train-only", action="store_true", help="Sadece eğit (önceden dönüştürülmüş veri ile)")
    parser.add_argument("--no-interactive", action="store_true", help="İnteraktif test yapma")
    args = parser.parse_args()

    if args.transform_only:
        transform_dataset()
    elif args.train_only:
        train_model()
    else:
        data = transform_dataset()
        train_model(data)
