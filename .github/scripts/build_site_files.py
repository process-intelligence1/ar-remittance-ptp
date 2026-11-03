"""Put the demo edition's data and files into the site folder (M15) - run by the Pages workflow, and on the laptop to measure.

    python .github/scripts/build_site_files.py <site folder> [--max-mb 300]

From snapshot/ (made by scripts.export_snapshot and checked by scripts.check_snapshot):
  snapshot/data     -> <site>/data
  snapshot/files    -> <site>/files            (attachments unpacked from ZIP files)
  data/samples/...  -> <site>/samples/...      ONLY the sample files listed in the manifest data/files.json (nothing else from the sample folder)
  PDF pages         -> <site>/pages/<attachment id>/<n>.jpg   rendered here (PyMuPDF, the same resolution as the live viewer), so the
                       evidence highlights (fractions of the page) fit exactly. Page images are not kept in git.
Prints the measured size of everything and fails when it is over the limit (default 300 MB).
Needs: pip install pymupdf
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DPI = 110          # as in the live viewer (backend/app/api/workitems.py PAGE_DPI)
JPEG_QUALITY = 72


def folder_bytes(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    ap.add_argument("--max-mb", type=float, default=300)
    args = ap.parse_args()
    site, snap = Path(args.site), ROOT / "snapshot"
    manifest = json.loads((snap / "data" / "files.json").read_text(encoding="utf-8"))

    shutil.copytree(snap / "data", site / "data", dirs_exist_ok=True)
    if (snap / "files").exists():
        shutil.copytree(snap / "files", site / "files", dirs_exist_ok=True)

    copied = 0
    samples = ROOT / "data" / "samples"
    for e in manifest:
        if e["kind"] != "sample":
            continue
        src = samples / e["path"]
        if not src.is_file():
            print(f"MISSING sample file {src}")
            return 1
        dest = site / "samples" / e["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        copied += 1

    import pymupdf

    rendered = 0
    for e in manifest:
        if not e.get("pages"):
            continue
        src = samples / e["path"] if e["kind"] == "sample" else snap / "files" / e["path"]
        doc = pymupdf.open(src)
        try:
            for n in range(1, min(doc.page_count, e["pages"]) + 1):
                out = site / "pages" / str(e["id"]) / f"{n}.jpg"
                out.parent.mkdir(parents=True, exist_ok=True)
                doc[n - 1].get_pixmap(dpi=DPI).save(out, jpg_quality=JPEG_QUALITY)
                rendered += 1
        finally:
            doc.close()

    sizes = {k: folder_bytes(site / k) for k in ("data", "files", "samples", "pages")}
    total = sum(sizes.values())
    print(f"copied {copied} sample files, rendered {rendered} page images")
    print({k: f"{v / 1024 / 1024:.1f} MB" for k, v in sizes.items()}, f"-> {total / 1024 / 1024:.1f} MB of demo data (limit {args.max_mb:.0f} MB for the whole site)")
    return 0 if total / 1024 / 1024 <= args.max_mb else 1


if __name__ == "__main__":
    sys.exit(main())
