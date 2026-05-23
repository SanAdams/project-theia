"""
Extract embedded barcode images from the Order Inventory Guides PDF.

Layout insight: the PDF has two product columns per page. CIC code text sits
at x≈100 (left col) and x≈480 (right col). Each product's barcode image is
~120pt to the right on the SAME ROW, consistently at x≈220 (left) and x≈590
(right). Row Y offset between text and image is ~10pt.

Algorithm:
  1. Split CIC codes and images into left / right columns (midpoint x=306).
  2. Within each column, build all (image, CIC) candidate pairs where the
     Y-distance is within MAX_ROW_Y_DIFF.
  3. Sort pairs by Y-distance and greedily assign 1:1 (each image and each
     CIC code used at most once).

Run from backend/:
    python scripts/extract_barcodes.py [--overwrite]
"""

import json
import sys
from io import BytesIO
from pathlib import Path

import fitz  # pymupdf
from PIL import Image

BASE_DIR = Path(__file__).parent.parent
PDF_PATH = BASE_DIR / "Order Inventory Guides Jan 2026.pdf"
PRODUCTS_PATH = BASE_DIR / "products.json"
OUTPUT_DIR = BASE_DIR / "static" / "barcodes"

# x coordinate splitting left and right product columns (matches parse_products.py).
COLUMN_MIDPOINT = 306

# Maximum Y-distance (pt) between a barcode image centre and its CIC code
# centre to be considered the same row. Rows are ~36pt apart; the image/text
# offset is consistently ~10pt, so 30pt gives comfortable headroom.
MAX_ROW_Y_DIFF = 30

# Aspect ratio lower bound: barcodes are wider than tall (observed ~2–3:1).
MIN_ASPECT_RATIO = 1.5

# Minimum image area (pt²) — filters out hairlines and tiny decorative marks.
MIN_AREA = 500


def load_cic_codes() -> set[str]:
    with open(PRODUCTS_PATH, encoding="utf-8") as f:
        products = json.load(f)
    return {p["CIC Code"] for p in products if p.get("CIC Code")}


def match_column(
    images: list[tuple[int, float]],  # [(xref, cy), ...]
    cics: list[tuple[str, float]],  # [(cic_code, cy), ...]
) -> list[tuple[int, str]]:
    """Return 1:1 (xref, cic_code) pairs using greedy min-Y-diff assignment."""
    candidates: list[tuple[float, int, int, int, str]] = []
    for img_idx, (xref, img_cy) in enumerate(images):
        for cic_idx, (cic, cic_cy) in enumerate(cics):
            ydiff = abs(img_cy - cic_cy)
            if ydiff <= MAX_ROW_Y_DIFF:
                candidates.append((ydiff, img_idx, cic_idx, xref, cic))

    candidates.sort()
    used_imgs: set[int] = set()
    used_cics: set[int] = set()
    matches: list[tuple[int, str]] = []

    for ydiff, img_idx, cic_idx, xref, cic in candidates:
        if img_idx in used_imgs or cic_idx in used_cics:
            continue
        matches.append((xref, cic))
        used_imgs.add(img_idx)
        used_cics.add(cic_idx)

    return matches


def save_image(doc: fitz.Document, xref: int, out_path: Path) -> bool:
    try:
        base_image = doc.extract_image(xref)
        img_pil = Image.open(BytesIO(base_image["image"])).convert("RGBA")
        img_pil.save(out_path, "PNG")
        return True
    except Exception as e:
        print(f"  WARNING: failed to save {out_path.name} — {e}", file=sys.stderr)
        return False


def extract_barcodes(overwrite: bool = False) -> None:
    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found at {PDF_PATH}", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cic_codes = load_cic_codes()
    print(f"Loaded {len(cic_codes)} CIC codes  |  overwrite={overwrite}")

    doc = fitz.open(PDF_PATH)
    saved = skipped_exists = skipped_no_match = 0

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Collect CIC code positions, split by column.
        words = page.get_text("words")
        left_cics: list[tuple[str, float]] = []
        right_cics: list[tuple[str, float]] = []
        for w in words:
            text = w[4].strip()
            if text in cic_codes:
                cx = (w[0] + w[2]) / 2
                cy = (w[1] + w[3]) / 2
                (left_cics if cx < COLUMN_MIDPOINT else right_cics).append((text, cy))

        if not left_cics and not right_cics:
            continue

        # Collect barcode-shaped images, split by column.
        left_imgs: list[tuple[int, float]] = []
        right_imgs: list[tuple[int, float]] = []
        for img in page.get_images(full=True):
            xref = img[0]
            rects = page.get_image_rects(xref)
            if not rects:
                continue
            r = rects[0]
            w, h = r.x1 - r.x0, r.y1 - r.y0
            if w * h < MIN_AREA or h == 0 or (w / h) < MIN_ASPECT_RATIO:
                continue
            cx = (r.x0 + r.x1) / 2
            cy = (r.y0 + r.y1) / 2
            (left_imgs if cx < COLUMN_MIDPOINT else right_imgs).append((xref, cy))

        # Match each column independently.
        page_matches = match_column(left_imgs, left_cics) + match_column(
            right_imgs, right_cics
        )

        # Count unmatched images on this page.
        matched_xrefs = {xref for xref, _ in page_matches}
        all_xrefs = {xref for xref, _ in left_imgs + right_imgs}
        page_no_match = len(all_xrefs - matched_xrefs)
        skipped_no_match += page_no_match

        for xref, cic in page_matches:
            out_path = OUTPUT_DIR / f"{cic}.png"
            if out_path.exists() and not overwrite:
                skipped_exists += 1
                continue
            if save_image(doc, xref, out_path):
                saved += 1
                print(f"  page {page_num + 1}: saved {cic}.png")

        if page_no_match:
            print(
                f"  page {page_num + 1}: {page_no_match} image(s) had no CIC "
                f"within {MAX_ROW_Y_DIFF}pt Y — skipped"
            )

    doc.close()
    print(
        f"\nDone. saved={saved}  skipped_exists={skipped_exists}  "
        f"unmatched_images={skipped_no_match}"
    )
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    extract_barcodes(overwrite="--overwrite" in sys.argv)
