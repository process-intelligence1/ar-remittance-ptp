"""Small learned model: TF-IDF on character n-grams + logistic regression.

Character n-grams (2-5 letters inside words) work for every language, including Japanese, without
word splitting. Classes: REMITTANCE, PTP, MIXED, OUT_OF_SCOPE:<CATEGORY>. Only asked when the rules
are unsure (see classifier.py).

Training uses scikit-learn on the LAPTOP only (`python -m scripts.train_classifier`, library in
requirements-dev.txt). The result is saved as plain numbers (model.npz: vocabulary, IDF weights,
coefficients) and predicted here with numpy, so the container image does not need scikit-learn and
scipy (~50 MB compressed - the free GHCR storage is already nearly full). A test checks that these
predictions equal scikit-learn's.
"""
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.classification.inputs import ClassifierInput
from app.classification.signals import fold

MODEL_FILE = Path(__file__).with_name("model.npz")
MAX_CHARS = 6000  # per e-mail; enough for subject + body + the first pages of attachments
NGRAMS = (2, 5)
_WHITE_SPACES = re.compile(r"\s\s+")


def model_text(inp: ClassifierInput) -> str:
    return fold(inp.all_text())[:MAX_CHARS]


def char_wb_ngrams(text: str, min_n: int = NGRAMS[0], max_n: int = NGRAMS[1]) -> list[str]:
    """Same n-grams as scikit-learn's TfidfVectorizer(analyzer="char_wb"): each word padded with a
    space, n-grams taken inside it; a word shorter than n gives one (short) n-gram."""
    grams = []
    for w in _WHITE_SPACES.sub(" ", text.lower()).split():
        w = f" {w} "
        for n in range(min_n, max_n + 1):
            offset = 0
            grams.append(w[offset:offset + n])
            while offset + n < len(w):
                offset += 1
                grams.append(w[offset:offset + n])
            if offset == 0:  # word shorter than n
                break
    return grams


@dataclass
class TextModel:
    classes: list[str]
    vocabulary: dict[str, int]
    idf: np.ndarray        # (terms,)
    coef: np.ndarray       # (classes, terms), or (1, terms) for two classes
    intercept: np.ndarray  # (classes,) or (1,)
    meta: dict

    @property
    def trained_on(self) -> int:
        return self.meta["trained_on"]

    def _vector(self, text: str) -> np.ndarray:
        x = np.zeros(len(self.idf))
        for gram, count in Counter(g for g in char_wb_ngrams(text) if g in self.vocabulary).items():
            x[self.vocabulary[gram]] = 1 + np.log(count)  # sublinear term frequency
        x *= self.idf
        norm = np.linalg.norm(x)
        return x / norm if norm else x

    def probabilities(self, text: str) -> np.ndarray:
        z = self.coef @ self._vector(text) + self.intercept
        if len(z) == 1:  # two classes: logistic
            p = 1 / (1 + np.exp(-z[0]))
            return np.array([1 - p, p])
        e = np.exp(z - z.max())  # softmax
        return e / e.sum()

    def predict(self, inp: ClassifierInput) -> list[tuple[str, float]]:
        """All classes with probabilities, most likely first."""
        probs = self.probabilities(model_text(inp))
        return sorted(zip(self.classes, (float(p) for p in probs)), key=lambda kv: -kv[1])


def build_pipeline():
    """scikit-learn pipeline used for training (laptop only)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    return Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=NGRAMS, min_df=2, max_features=20000,
                                  sublinear_tf=True)),
        ("lr", LogisticRegression(C=10.0, max_iter=3000, class_weight="balanced")),
    ])


def export(pipe, trained_on: int) -> TextModel:
    import sklearn

    tfidf, lr = pipe.named_steps["tfidf"], pipe.named_steps["lr"]
    return TextModel(
        classes=[str(c) for c in lr.classes_], vocabulary={str(t): int(i) for t, i in tfidf.vocabulary_.items()},
        idf=tfidf.idf_.astype(np.float64), coef=lr.coef_.astype(np.float64), intercept=lr.intercept_.astype(np.float64),
        meta={"trained_on": trained_on, "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "sklearn_version": sklearn.__version__, "ngrams": list(NGRAMS)})


def train(texts: list[str], keys: list[str]) -> TextModel:
    pipe = build_pipeline()
    pipe.fit(texts, keys)
    return export(pipe, len(texts))


def save(model: TextModel, path: Path = MODEL_FILE) -> None:
    terms = [""] * len(model.vocabulary)
    for t, i in model.vocabulary.items():
        terms[i] = t
    np.savez_compressed(path, classes=np.array(model.classes), terms=np.array(terms), idf=model.idf,
                        coef=model.coef, intercept=model.intercept, meta=np.array(json.dumps(model.meta)))


@lru_cache
def load_model(path: Path = MODEL_FILE) -> TextModel | None:
    """None when there is no trained model yet (the rules then work alone). Plain arrays only - no pickle."""
    if not path.exists():
        return None
    with np.load(path, allow_pickle=False) as z:
        return TextModel(classes=[str(c) for c in z["classes"]],
                         vocabulary={str(t): i for i, t in enumerate(z["terms"])},
                         idf=z["idf"], coef=z["coef"], intercept=z["intercept"], meta=json.loads(str(z["meta"])))
