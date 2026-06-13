"""
BLUE_AI — Model Trainer
Veri setinden model egitir, test eder, kaydeder.
"""

import json
import time
import sys
from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

from blue_ai.ai.model import BlueAIModel, normalize_turkish, TRAINING_DIR, MODELS_DIR


def train_and_evaluate():
    """Modeli egit ve degerlendir."""
    dataset_path = TRAINING_DIR / "intent_dataset.json"

    if not dataset_path.exists():
        print("HATA: intent_dataset.json bulunamadi!")
        print("Once dataset generator'i calistirin:")
        print("  python -m blue_ai.ai.build_base_dataset")
        print("  python -m blue_ai.ai.dataset_generator")
        sys.exit(1)

    print("=" * 60)
    print("BLUE_AI Model Egitimi")
    print("=" * 60)

    # Veri setini yukle
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    texts = [normalize_turkish(item["text"]) for item in data["data"]]
    labels = [item["intent"] for item in data["data"]]

    print(f"\nToplam ornek: {len(texts)}")
    print(f"Toplam intent: {len(set(labels))}")

    # Train/Test ayir
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )

    print(f"Egitim seti: {len(X_train)}")
    print(f"Test seti: {len(X_test)}")

    # Model olustur ve egit
    model = BlueAIModel()

    print("\nModel egitiliyor...")
    start = time.time()
    model.pipeline = None
    model._loaded = False

    # Egitim verisinden pipeline olustur
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.svm import LinearSVC
    from sklearn.pipeline import Pipeline
    from sklearn.calibration import CalibratedClassifierCV

    model.pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=50000,
            ngram_range=(1, 3),
            sublinear_tf=True,
            min_df=2,
            max_df=0.95,
            analyzer="char_wb",
        )),
        ("clf", CalibratedClassifierCV(
            LinearSVC(C=1.0, max_iter=5000, class_weight="balanced"),
            cv=3,
        )),
    ])

    model.pipeline.fit(X_train, y_train)
    model._loaded = True
    model.intent_labels = sorted(set(labels))

    elapsed = time.time() - start
    print(f"Egitim tamamlandi! ({elapsed:.1f} saniye)")

    # Test
    print("\nTest ediliyor...")
    y_pred = model.pipeline.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    print(f"\n{'='*60}")
    print(f"DOGRULUK: %{accuracy*100:.2f}")
    print(f"{'='*60}")

    # Detayli rapor
    report = classification_report(y_test, y_pred, zero_division=0)
    print(f"\nDetayli Rapor:\n{report}")

    # Modeli kaydet
    model.save()
    print(f"\nModel kaydedildi: {MODELS_DIR / 'intent_model.joblib'}")

    # Interaktif test
    print(f"\n{'='*60}")
    print("Interaktif Test (cikis icin 'q' yazin)")
    print(f"{'='*60}")

    while True:
        try:
            text = input("\n> ").strip()
            if text.lower() in ("q", "quit", "exit", "cikis"):
                break
            if not text:
                continue

            result = model.predict(text)
            print(f"  Intent: {result['intent']}")
            print(f"  Guven:  %{result['confidence']*100:.1f}")
            if "top_3" in result:
                print(f"  Top 3:")
                for t in result["top_3"]:
                    print(f"    - {t['intent']}: %{t['confidence']*100:.1f}")
        except (KeyboardInterrupt, EOFError):
            break

    print("\nBitti!")


if __name__ == "__main__":
    train_and_evaluate()
