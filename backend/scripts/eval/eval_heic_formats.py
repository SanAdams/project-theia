#!/usr/bin/env python3
"""
Compare HEIC-to-Rekognition conversion strategies for product matching.

Converts the HEIC test image three ways — PNG (lossless), JPEG-95, JPEG-85 —
then calls get_ocr_lines() for each (AWS-cached by MD5 of converted bytes,
same pattern as eval_matching.py) and runs product matching with the current
WRatio scorer at cutoff 80.

AWS calls (first run only): get_ocr_lines() makes 1 DetectLabels + N DetectText
calls per strategy, where N is the number of detected box regions. Results are
cached — subsequent runs cost nothing.

Usage:
    cd backend
    python scripts/eval/eval_heic_formats.py
"""

import hashlib
import io
import json
import sys
from pathlib import Path

import pillow_heif
from PIL import Image

SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")

pillow_heif.register_heif_opener()

from rapidfuzz import fuzz, process

from app.services.rekognition import get_ocr_lines

HEIC_PATH = BACKEND_DIR / "tests" / "test_images" / "IMG_20260526_221011 (4) (1).heic"
CACHE_DIR = SCRIPT_DIR / "cache"
PRODUCTS_PATH = BACKEND_DIR / "products.json"
CUTOFF = 80.0
STRATEGIES = ["png", "jpeg-95", "jpeg-85"]


def load_catalog() -> tuple[list[str], dict[str, str]]:
    data = json.loads(PRODUCTS_PATH.read_text())
    labeled = [(p["name"], p["label"]) for p in data if p.get("label")]
    labels = [label for _, label in labeled]
    name_by_label = {label: name for name, label in labeled}
    return labels, name_by_label


def _cache_path(image_bytes: bytes) -> Path:
    return CACHE_DIR / f"{hashlib.md5(image_bytes).hexdigest()}.json"


def get_cached_ocr(image_bytes: bytes) -> list[str] | None:
    CACHE_DIR.mkdir(exist_ok=True)
    cp = _cache_path(image_bytes)
    return json.loads(cp.read_text()) if cp.exists() else None


def save_cached_ocr(image_bytes: bytes, lines: list[str]) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    _cache_path(image_bytes).write_text(json.dumps(lines))


def convert(heic_bytes: bytes, strategy: str) -> bytes:
    img = Image.open(io.BytesIO(heic_bytes)).convert("RGB")
    buf = io.BytesIO()
    if strategy == "png":
        img.save(buf, format="PNG")
    elif strategy == "jpeg-95":
        img.save(buf, format="JPEG", quality=95)
    elif strategy == "jpeg-85":
        img.save(buf, format="JPEG", quality=85)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
    return buf.getvalue()


def match_all(
    ocr_lines: list[str], labels: list[str], name_by_label: dict[str, str]
) -> set[str]:
    matched: set[str] = set()
    for line in ocr_lines:
        if sum(c.isalnum() for c in line) < 3:
            continue
        result = process.extractOne(
            line, labels, scorer=fuzz.WRatio, score_cutoff=CUTOFF
        )
        if result:
            matched.add(name_by_label[result[0]])
    return matched


def main() -> None:
    if not HEIC_PATH.exists():
        print(f"ERROR: HEIC test file not found:\n  {HEIC_PATH}")
        sys.exit(1)

    raw = HEIC_PATH.read_bytes()
    print(f"Source: {HEIC_PATH.name}  ({len(raw) / 1024:.1f} KB HEIC)")

    labels, name_by_label = load_catalog()
    print(f"Catalog: {len(labels)} labeled products\n")

    MAX_BYTES = 5 * 1024 * 1024
    results: dict[str, dict] = {}
    for strategy in STRATEGIES:
        converted = convert(raw, strategy)
        size_kb = len(converted) / 1024

        if len(converted) > MAX_BYTES:
            print(
                f"  [{strategy}]  {size_kb:.1f} KB — EXCEEDS 5 MB LIMIT, skipping AWS call"
            )
            results[strategy] = {
                "size_kb": size_kb,
                "lines": None,
                "matched": None,
            }
            continue

        lines = get_cached_ocr(converted)
        if lines is None:
            print(f"  [{strategy}]  {size_kb:.1f} KB — calling AWS...")
            lines = get_ocr_lines(converted)
            save_cached_ocr(converted, lines)
            print(f"    -> {len(lines)} OCR lines, cached")
        else:
            print(f"  [{strategy}]  {size_kb:.1f} KB — {len(lines)} lines (cached)")

        results[strategy] = {
            "size_kb": size_kb,
            "lines": lines,
            "matched": match_all(lines, labels, name_by_label),
        }

    # Comparison table — only strategies that fit within the 5 MB limit
    viable = {s: r for s, r in results.items() if r["matched"] is not None}
    all_products = sorted(set().union(*(r["matched"] for r in viable.values())))

    print("\n" + "=" * 70)
    print("PRODUCT MATCH COMPARISON  (strategies over 5 MB skipped)")
    print("=" * 70)
    if not viable:
        print("  (all strategies exceed 5 MB — no AWS calls possible)")
    elif not all_products:
        print("  (no products matched by any viable strategy)")
    else:
        headers = [s for s in STRATEGIES if s in viable]
        header_str = "".join(f"{s:^10}" for s in headers)
        print(f"  {'Product':<42} {header_str}")
        print("  " + "-" * (42 + 10 * len(headers)))
        for product in all_products:
            cols = "".join(
                (f"{'+'if product in viable[s]['matched'] else '-':^10}")
                for s in headers
            )
            print(f"  {product:<42} {cols}")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for strategy in STRATEGIES:
        r = results[strategy]
        if r["matched"] is None:
            print(
                f"  {strategy:<10}  {r['size_kb']:>7.1f} KB   EXCEEDS 5 MB — not viable as-is"
            )
        else:
            print(
                f"  {strategy:<10}  {r['size_kb']:>7.1f} KB"
                f"   {len(r['lines']):>3} OCR lines"
                f"   {len(r['matched']):>2} products matched"
            )

    # Diff JPEG strategies against each other (PNG may not be viable)
    if "jpeg-95" in viable and "jpeg-85" in viable:
        lost = viable["jpeg-95"]["matched"] - viable["jpeg-85"]["matched"]
        gained = viable["jpeg-85"]["matched"] - viable["jpeg-95"]["matched"]
        print()
        if not lost and not gained:
            print(
                "  JPEG-85 matches JPEG-95 exactly — quality degradation has no impact here."
            )
            print("  Recommendation: use JPEG-95 as the HEIC conversion quality floor.")
        else:
            if lost:
                print(f"  JPEG-85 LOST vs JPEG-95: {', '.join(sorted(lost))}")
            if gained:
                print(f"  JPEG-85 GAINED vs JPEG-95: {', '.join(sorted(gained))}")
            print("  Recommendation: use JPEG-95 as the quality floor to avoid losses.")


if __name__ == "__main__":
    main()
