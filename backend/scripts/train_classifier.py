"""Train the small classification model on all sample folders and save it.

Run from the backend folder:
    python -m scripts.train_classifier
-> app/classification/model.npz (commit it; the API and worker load it from there).
Needs the laptop-only libraries: pip install -r requirements-dev.txt
Re-run after adding or changing samples. Accuracy: python -m scripts.evaluate --stage classification
"""
import sys
from collections import Counter

from app.classification.model import MODEL_FILE, model_text, save, train
from app.classification.samples import load_corpus


def main() -> int:
    print("Reading the sample folders (cached text is reused) ...", flush=True)
    corpus = load_corpus(progress=True)
    texts = [model_text(inp) for _, inp, _ in corpus]
    keys = [exp.key for _, _, exp in corpus]
    model = train(texts, keys)
    save(model)
    print(f"Trained on {model.trained_on} e-mails ({dict(Counter(keys))}) -> {MODEL_FILE} "
          f"({MODEL_FILE.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
