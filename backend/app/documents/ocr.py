"""OCR for images and scanned PDF pages.

prepare_image()   grey, scale to ~300 dpi (max OCR_MAX_SIDE_PX), deskew, light denoise
TesseractEngine   script detection (Latin vs Japanese) -> language set; page segmentation mode 6
                  (one block of lines, keeps table rows together) + preserve_interword_spaces=1;
                  lines are rebuilt top-to-bottom, left-to-right, wide gaps kept as two spaces so
                  "invoice  amount" stays on one line and table columns can be found again.
AzureDIEngine     same interface, Document Intelligence "Read" (F0). OFF by default (OCR_ENGINE).
"""
import io
import json
import logging
import time
import urllib.request
from dataclasses import dataclass, field

import cv2
import numpy as np
import pytesseract
from PIL import Image

from app.config import get_settings
from app.documents.common import Deadline, DocumentTimeout, box, mean

log = logging.getLogger(__name__)

LATIN_LANGS = "eng+deu+fra+spa+por"
JAPANESE_LANGS = "jpn+eng"
JAPANESE_VERTICAL_LANGS = "jpn_vert+jpn"
JAPANESE_SCRIPTS = {"Japanese", "Han", "Hiragana", "Katakana", "HanS", "HanT"}
BASE_CONFIG = "-c preserve_interword_spaces=1"
MIN_TIMEOUT_S = 5


@dataclass
class OcrPage:
    text: str
    words: list[list]                 # [text, x0, y0, x1, y1, conf] - boxes scaled 0..1
    width: int
    height: int
    confidence: float | None
    languages: str
    lines: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- image preparation
def to_gray(img: Image.Image | np.ndarray) -> np.ndarray:
    if isinstance(img, Image.Image):
        if img.mode not in ("L", "RGB"):
            img = img.convert("RGB")
        arr = np.asarray(img)
    else:
        arr = img
    if arr.ndim == 3:
        arr = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    return arr


def skew_angle(gray: np.ndarray) -> float:
    """Angle (degrees) of the text lines; 0 = straight. Uses the dark pixels' minimum-area box."""
    _, inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    coords = cv2.findNonZero(inv)
    if coords is None or len(coords) < 50:
        return 0.0
    angle = cv2.minAreaRect(coords)[-1]
    # OpenCV returns [0, 90): map to (-45, 45]
    if angle > 45:
        angle -= 90
    return float(angle)


def rotate(gray: np.ndarray, angle: float) -> np.ndarray:
    h, w = gray.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(gray, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def prepare_image(img: Image.Image | np.ndarray, source_dpi: float | None = None) -> tuple[np.ndarray, dict]:
    """Returns the image to OCR and what was done to it."""
    s = get_settings()
    gray = to_gray(img)
    info: dict = {}
    h, w = gray.shape[:2]
    # Tesseract works best around 300 dpi: A4 scans at ~150 dpi (1240 px wide) are scaled up
    scale = 1.0
    if source_dpi and source_dpi < 250:
        scale = min(2.0, 300 / source_dpi)
    elif not source_dpi and max(h, w) < 2000:
        scale = 2.0
    if max(h, w) * scale > s.ocr_max_side_px:
        scale = s.ocr_max_side_px / max(h, w)
    if abs(scale - 1.0) > 0.05:
        gray = cv2.resize(gray, None, fx=scale, fy=scale,
                          interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA)
        info["scale"] = round(scale, 3)
    angle = skew_angle(gray)
    if 0.3 <= abs(angle) <= 15:
        gray = rotate(gray, angle)
        info["deskew_deg"] = round(angle, 2)
    gray = cv2.medianBlur(gray, 3)  # removes salt-and-pepper scan noise, keeps edges
    return gray, info


# --------------------------------------------------------------------------- Tesseract
def _configure_tesseract() -> None:
    cmd = get_settings().tesseract_cmd
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd


def _timeout(deadline: Deadline | None) -> float:
    if deadline is None:
        return 0  # pytesseract: 0 = no timeout
    deadline.check()
    return max(MIN_TIMEOUT_S, deadline.remaining())


def _run(fn, *args, deadline: Deadline | None, **kwargs):
    try:
        return fn(*args, timeout=_timeout(deadline), **kwargs)
    except RuntimeError as exc:  # pytesseract raises RuntimeError("Tesseract process timeout")
        if "timeout" in str(exc).lower():
            raise DocumentTimeout(f"timeout after {deadline.seconds:.0f} s" if deadline else "timeout") from exc
        raise


MIN_ROTATE_CONF = 1.5   # OSD orientation confidence needed before a page is turned
MIN_SCRIPT_CONF = 1.0   # OSD script confidence needed before its language guess is used
GOOD_ENOUGH_CONF = 70   # a reading at or above this mean word confidence is accepted at once
MAX_PASSES = 3          # readings tried per page at most (only weak pages need more than one)


@dataclass
class Osd:
    script: str = "Latin"
    rotate: int = 0
    rotate_conf: float = 0.0
    script_conf: float = 0.0


def detect_orientation(gray: np.ndarray, deadline: Deadline | None = None) -> Osd:
    """Tesseract OSD (orientation + script). Empty result when there is too little text."""
    try:
        d = _run(pytesseract.image_to_osd, gray, deadline=deadline,
                 config="--psm 0 -c min_characters_to_try=10", output_type=pytesseract.Output.DICT)
        return Osd(d.get("script", "Latin"), int(d.get("rotate", 0)), float(d.get("orientation_conf", 0)),
                   float(d.get("script_conf", 0)))
    except DocumentTimeout:
        raise
    except Exception:
        return Osd()


def _turn(gray: np.ndarray, degrees: int) -> np.ndarray:
    # OSD "rotate" = degrees to turn the image clockwise; np.rot90 turns counter-clockwise
    return np.ascontiguousarray(np.rot90(gray, k=(-degrees // 90) % 4)) if degrees % 360 else gray


def _quality(page: "OcrPage") -> float:
    """Mean word confidence, lowered for readings with almost no text."""
    chars = len(page.text.replace(" ", ""))
    return (page.confidence or 0) * min(1.0, chars / 40)


class TesseractEngine:
    name = "tesseract"

    def __init__(self):
        _configure_tesseract()

    def ocr(self, img: Image.Image | np.ndarray, deadline: Deadline | None = None,
            source_dpi: float | None = None) -> OcrPage:
        """Best of up to MAX_PASSES readings. OSD is only trusted when confident: a weak
        orientation or script guess is tried as an alternative, not applied blindly."""
        gray, _info = prepare_image(img, source_dpi)
        osd = detect_orientation(gray, deadline)
        confident_turn = osd.rotate if osd.rotate_conf >= MIN_ROTATE_CONF else 0
        japanese_first = osd.script in JAPANESE_SCRIPTS and osd.script_conf >= MIN_SCRIPT_CONF
        langs = [JAPANESE_LANGS, LATIN_LANGS] if japanese_first else [LATIN_LANGS, JAPANESE_LANGS]

        candidates = [(confident_turn, langs[0], 6), (confident_turn, langs[1], 6)]
        if osd.rotate and not confident_turn:
            candidates.append((osd.rotate, langs[0], 6))   # weak rotation hint: try it, don't trust it
        best = None
        for turn, lang, psm in candidates[:MAX_PASSES]:
            page = self._ocr_once(_turn(gray, turn), lang, psm, deadline)
            if best is None or _quality(page) > _quality(best):
                best = page
            if (best.confidence or 0) >= GOOD_ENOUGH_CONF:
                break
        if best.languages == JAPANESE_LANGS and (best.confidence or 0) < 50:  # maybe vertical Japanese
            vertical = self._ocr_once(_turn(gray, confident_turn), JAPANESE_VERTICAL_LANGS, 5, deadline)
            if _quality(vertical) > _quality(best):
                best = vertical
        return best

    def _ocr_once(self, gray: np.ndarray, langs: str, psm: int, deadline: Deadline | None) -> OcrPage:
        data = _run(pytesseract.image_to_data, gray, deadline=deadline, lang=langs,
                    config=f"--psm {psm} {BASE_CONFIG}", output_type=pytesseract.Output.DICT)
        h, w = gray.shape[:2]
        return build_page(data, w, h, langs)


def _is_cjk(ch: str) -> bool:
    """Japanese/Chinese characters and full-width punctuation (no spaces between them)."""
    o = ord(ch)
    return (0x3000 <= o <= 0x30FF or 0x3400 <= o <= 0x4DBF or 0x4E00 <= o <= 0x9FFF
            or 0xF900 <= o <= 0xFAFF or 0xFF00 <= o <= 0xFFEF)


def build_page(data: dict, width: int, height: int, langs: str) -> OcrPage:
    """Words with boxes, and text rebuilt line by line in reading order."""
    words, confs = [], []
    by_line: dict[tuple, list] = {}
    for i, txt in enumerate(data["text"]):
        txt = (txt or "").strip()
        conf = float(data["conf"][i])
        if not txt or conf < 0:
            continue
        x, y, bw, bh = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        words.append([txt, *box(x, y, x + bw, y + bh, width, height), round(conf, 1)])
        confs.append(conf)
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        by_line.setdefault(key, []).append((x, y, bw, bh, txt))
    lines = []
    for key in sorted(by_line, key=lambda k: (min(t[1] for t in by_line[k]), k)):  # top to bottom
        items = sorted(by_line[key])                                              # left to right
        char_w = max(1.0, sum(t[2] for t in items) / max(1, sum(len(t[4]) for t in items)))
        out = items[0][4]
        for prev, cur in zip(items, items[1:]):
            gap = cur[0] - (prev[0] + prev[2])
            if gap > 2.5 * char_w:
                out += "  "                       # wide gap = new column
            elif not (_is_cjk(prev[4][-1]) and _is_cjk(cur[4][0])):
                out += " "                        # Japanese is written without spaces
            out += cur[4]
        lines.append(out)
    return OcrPage("\n".join(lines), words, width, height, mean(confs), langs, lines)


# --------------------------------------------------------------------------- Azure Document Intelligence
class AzureDIEngine:
    """Document Intelligence 'prebuilt-read' over REST (F0 tier). Not used unless OCR_ENGINE=azure_di.
    NOTE: written against the public REST API; not yet tested against a live resource."""
    name = "azure_di"
    API = "documentintelligence/documentModels/prebuilt-read:analyze?api-version=2024-11-30"

    def __init__(self):
        s = get_settings()
        if not (s.azure_di_endpoint and s.azure_di_key):
            raise RuntimeError("OCR_ENGINE=azure_di needs AZURE_DI_ENDPOINT and AZURE_DI_KEY")
        self.endpoint, self.key = s.azure_di_endpoint.rstrip("/"), s.azure_di_key

    def ocr(self, img: Image.Image | np.ndarray, deadline: Deadline | None = None,
            source_dpi: float | None = None) -> OcrPage:
        gray, _ = prepare_image(img, source_dpi)
        ok, png = cv2.imencode(".png", gray)
        req = urllib.request.Request(f"{self.endpoint}/{self.API}", data=png.tobytes(), method="POST",
                                     headers={"Ocp-Apim-Subscription-Key": self.key, "Content-Type": "image/png"})
        with urllib.request.urlopen(req, timeout=60) as r:
            op_url = r.headers["Operation-Location"]
        while True:
            if deadline:
                deadline.check()
            time.sleep(1)
            with urllib.request.urlopen(urllib.request.Request(
                    op_url, headers={"Ocp-Apim-Subscription-Key": self.key}), timeout=60) as r:
                res = json.load(r)
            if res.get("status") in ("succeeded", "failed"):
                break
        if res["status"] != "succeeded":
            raise RuntimeError(f"Document Intelligence failed: {res.get('error')}")
        page = res["analyzeResult"]["pages"][0]
        pw, ph = page["width"], page["height"]
        words, confs = [], []
        for wd in page.get("words", []):
            xs, ys = wd["polygon"][0::2], wd["polygon"][1::2]
            words.append([wd["content"], *box(min(xs), min(ys), max(xs), max(ys), pw, ph),
                          round(wd.get("confidence", 0) * 100, 1)])
            confs.append(wd.get("confidence", 0) * 100)
        lines = [ln["content"] for ln in page.get("lines", [])]
        h, w = gray.shape[:2]
        return OcrPage("\n".join(lines), words, w, h, mean(confs), "azure_di", lines)


def get_engine():
    return AzureDIEngine() if get_settings().ocr_engine == "azure_di" else TesseractEngine()


def open_image_frames(data: bytes) -> list[Image.Image]:
    """All frames of an image file (multi-page TIFF -> several pages)."""
    from PIL import ImageSequence

    img = Image.open(io.BytesIO(data))
    frames = [f.copy() for f in ImageSequence.Iterator(img)]
    return frames or [img]
