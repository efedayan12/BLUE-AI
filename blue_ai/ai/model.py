"""
BLUE_AI — AI Model
TF-IDF + LinearSVC pipeline ile intent siniflandirma.
Kendi veri setimizle egitilmis, Ollama/LLM gerektirmez.
"""

import json
import os
from pathlib import Path
from typing import Optional

# sklearn + joblib LAZY yüklenir (import süresini 0'a düşürür)
# from sklearn.* çağrıları yöntemlerin içine taşındı

DATA_DIR     = Path(__file__).parent.parent.parent / "data"
TRAINING_DIR = DATA_DIR / "training"
MODELS_DIR   = DATA_DIR / "models"
# mkdir() uygulamayı bloke etmemek için lazy — ilk train/load'da çağrılır

MODEL_PATH      = MODELS_DIR / "intent_model.joblib"
VECTORIZER_PATH = MODELS_DIR / "tfidf_vectorizer.joblib"


# Turkce karakter normalizasyonu
_CHAR_MAP = {
    "ı": "i", "İ": "I", "ö": "o", "Ö": "O",
    "ü": "u", "Ü": "U", "ş": "s", "Ş": "S",
    "ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G",
}


def normalize_turkish(text: str) -> str:
    """Turkce metni normalize et."""
    text = text.lower().strip()
    # Turkce karakterleri ASCII'ye cevir (hem turkce hem turksuz yazanlar icin)
    normalized = text
    for tr, en in _CHAR_MAP.items():
        normalized = normalized.replace(tr, en.lower())
    return normalized


class BlueAIModel:
    """BLUE_AI intent siniflandirma modeli."""

    def __init__(self):
        self.pipeline: Optional[Pipeline] = None
        self.intent_labels: list[str] = []
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    def train(self, dataset_path: str = None):
        """Veri setiyle modeli egit."""
        # Lazy sklearn import
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.svm import LinearSVC
        from sklearn.pipeline import Pipeline
        from sklearn.calibration import CalibratedClassifierCV
        try:
            import joblib
        except ImportError:
            from sklearn.externals import joblib

        if dataset_path is None:
            dataset_path = str(TRAINING_DIR / "intent_dataset.json")

        with open(dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        texts  = [normalize_turkish(item["text"])   for item in data["data"]]
        labels = [item["intent"]                     for item in data["data"]]

        self.intent_labels = sorted(set(labels))

        self.pipeline = Pipeline([
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

        self.pipeline.fit(texts, labels)
        self._loaded = True
        return self

    def predict(self, text: str) -> dict:
        """Metin icin intent tahmini yap."""
        import numpy as np  # lazy
        if not self._loaded:
            self.load()

        if not self._loaded:
            return {"intent": "general_question", "confidence": 0.0, "error": "Model yuklu degil"}

        normalized = normalize_turkish(text)
        intent = self.pipeline.predict([normalized])[0]
        proba  = self.pipeline.predict_proba([normalized])[0]
        confidence = float(max(proba))

        top_indices = np.argsort(proba)[-3:][::-1]
        classes = self.pipeline.classes_
        top_3 = [
            {"intent": classes[i], "confidence": round(float(proba[i]), 4)}
            for i in top_indices
        ]

        return {
            "intent": intent,
            "confidence": round(confidence, 4),
            "top_3": top_3,
        }

    def save(self, path: str = None):
        """Modeli dosyaya kaydet."""
        import joblib  # lazy
        if path is None:
            path = str(MODEL_PATH)
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        if self.pipeline is not None:
            joblib.dump({
                "pipeline": self.pipeline,
                "intent_labels": self.intent_labels,
                "version": "1.0",
            }, path)
            print(f"Model kaydedildi: {path}")

    def load(self, path: str = None) -> bool:
        """Modeli dosyadan yukle."""
        import joblib  # lazy
        if path is None:
            path = str(MODEL_PATH)
        if not os.path.exists(path):
            return False
        try:
            data = joblib.load(path)
            self.pipeline       = data["pipeline"]
            self.intent_labels  = data["intent_labels"]
            self._loaded = True
            return True
        except Exception as e:
            print(f"Model yukleme hatasi: {e}")
            return False


# Singleton
_model: Optional[BlueAIModel] = None


def get_model() -> BlueAIModel:
    """Singleton model instance dondur."""
    global _model
    if _model is None:
        _model = BlueAIModel()
        if MODEL_PATH.exists():
            _model.load()
    return _model
