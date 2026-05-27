#!/usr/bin/env python3
"""
Benchmark rapidfuzz scorer combinations against the product catalog.

Suite A: hardcoded text test cases — no AWS calls, runs instantly.
Suite B: your own photos via manifest.json — calls AWS once per image,
         then caches; subsequent runs are instant.

Usage:
    cd backend
    python scripts/eval/eval_matching.py

To add image test cases:
    1. Drop photos into scripts/eval/images/
    2. Edit scripts/eval/manifest.json with expected product names
       (use the canonical "name" field from products.json)
"""

import hashlib
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")

from rapidfuzz import fuzz, process

from app.services.image_processor import prepare_image
from app.services.rekognition import get_ocr_lines

PRODUCTS_PATH = BACKEND_DIR / "products.json"
CACHE_DIR = SCRIPT_DIR / "cache"
MANIFEST_PATH = SCRIPT_DIR / "manifest.json"
CUTOFF = 80.0

SCORERS = {
    "WRatio (current)": fuzz.WRatio,
    "ratio": fuzz.ratio,
    "partial_ratio": fuzz.partial_ratio,
    "token_sort_ratio": fuzz.token_sort_ratio,
    "token_set_ratio": fuzz.token_set_ratio,
    "token_ratio": fuzz.token_ratio,
    "partial_token_sort_ratio": fuzz.partial_token_sort_ratio,
    "partial_token_set_ratio": fuzz.partial_token_set_ratio,
}

# Noisy/partial OCR variants — add more as you discover real failure cases.
# Format: (ocr_text_as_rekognition_would_return_it, expected_canonical_product_name)
NOISY_CASES: list[tuple[str, str]] = [
    ("RING YEAST-RAISED DONUT", "Ring Donut"),  # dropped "READY TO FINISH"
    ("READY RING YEAST RAISED DONUT", "Ring Donut"),  # shuffled, dropped hyphen
    ("READY T0 FINISH RING YEAST-RAIS3D DONUT", "Ring Donut"),  # OCR noise: 0/3
]


# ---------------------------------------------------------------------------
# Catalog helpers
# ---------------------------------------------------------------------------


def load_catalog() -> tuple[list[tuple[str, str]], list[str], dict[str, str]]:
    data = json.loads(PRODUCTS_PATH.read_text())
    labeled = [(p["name"], p["label"]) for p in data if p.get("label")]
    labels = [label for _, label in labeled]
    name_by_label = {label: name for name, label in labeled}
    return labeled, labels, name_by_label


def match_line(ocr_text: str, labels: list[str], scorer) -> tuple[str | None, float]:
    if sum(c.isalnum() for c in ocr_text) < 3:
        return None, 0.0
    result = process.extractOne(ocr_text, labels, scorer=scorer, score_cutoff=CUTOFF)
    if result:
        return result[0], result[1]
    return None, 0.0


def match_lines(
    ocr_lines: list[str],
    labels: list[str],
    name_by_label: dict[str, str],
    scorer,
) -> set[str]:
    matched: set[str] = set()
    for line in ocr_lines:
        label, _ = match_line(line, labels, scorer)
        if label:
            matched.add(name_by_label[label])
    return matched


# ---------------------------------------------------------------------------
# OCR cache
# ---------------------------------------------------------------------------


def _cache_path(image_path: Path) -> Path:
    h = hashlib.md5(image_path.read_bytes()).hexdigest()
    return CACHE_DIR / f"{h}.json"


def get_cached_ocr(image_path: Path) -> list[str] | None:
    CACHE_DIR.mkdir(exist_ok=True)
    cp = _cache_path(image_path)
    return json.loads(cp.read_text()) if cp.exists() else None


def save_cached_ocr(image_path: Path, lines: list[str]) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    _cache_path(image_path).write_text(json.dumps(lines))


# ---------------------------------------------------------------------------
# Suite A: text cases
# ---------------------------------------------------------------------------


def run_suite_a(
    labeled: list[tuple[str, str]],
    labels: list[str],
    name_by_label: dict[str, str],
) -> tuple[dict[str, int], int]:
    print("\n" + "=" * 72)
    print("SUITE A  —  text cases (no AWS)")
    print("=" * 72)

    # Auto-generate exact-label cases from the catalog (first 15 labeled products)
    exact_cases: list[tuple[str, str]] = [(label, name) for name, label in labeled[:15]]
    all_cases = exact_cases + NOISY_CASES
    total = len(all_cases)

    scorer_passes: dict[str, int] = {}

    for scorer_name, scorer in SCORERS.items():
        passes = 0
        rows = []
        for ocr_text, expected_name in all_cases:
            matched_label, score = match_line(ocr_text, labels, scorer)
            got_name = name_by_label.get(matched_label or "") or None
            ok = got_name == expected_name
            passes += ok
            rows.append((ok, ocr_text, expected_name, got_name or "(no match)", score))

        scorer_passes[scorer_name] = passes
        print(f"\n  [{scorer_name}]  {passes}/{total}")
        for ok, ocr, expected, got, score in rows:
            mark = "✓" if ok else "✗"
            print(f"    {mark} {ocr[:46]:<47} → {got[:32]:<33} [{score:.0f}%]")

    return scorer_passes, total


# ---------------------------------------------------------------------------
# Suite B: image cases
# ---------------------------------------------------------------------------


def run_suite_b(
    labels: list[str],
    name_by_label: dict[str, str],
) -> tuple[dict[str, int], int]:
    if not MANIFEST_PATH.exists():
        print("\nSuite B: manifest.json not found — skipping.")
        return {}, 0

    manifest: list[dict] = json.loads(MANIFEST_PATH.read_text())
    if not manifest:
        print(
            "\nSuite B: manifest.json is empty — add images and expected products to run."
        )
        return {}, 0

    print("\n" + "=" * 72)
    print("SUITE B  —  image cases (AWS / cached)")
    print("=" * 72)

    # Fetch/cache OCR lines for each image
    image_data: list[tuple[str, list[str], list[str]]] = []
    for entry in manifest:
        img_path = SCRIPT_DIR / entry["file"]
        if not img_path.exists():
            print(f"  WARNING: {entry['file']} not found — skipping")
            continue
        lines = get_cached_ocr(img_path)
        if lines is None:
            print(f"  Calling AWS for {img_path.name}...")
            image_bytes = prepare_image(img_path.read_bytes())
            lines = get_ocr_lines(image_bytes)
            save_cached_ocr(img_path, lines)
            print(f"    cached {len(lines)} OCR line(s): {lines}")
        else:
            print(f"  {img_path.name}: {len(lines)} line(s) from cache")
        image_data.append((img_path.name, lines, entry["expected"]))

    if not image_data:
        return {}, 0

    total_products = sum(len(exp) for _, _, exp in image_data)
    scorer_passes: dict[str, int] = {}

    for scorer_name, scorer in SCORERS.items():
        passes = 0
        print(f"\n  [{scorer_name}]")
        for filename, ocr_lines, expected_names in image_data:
            matched = match_lines(ocr_lines, labels, name_by_label, scorer)
            for expected in expected_names:
                ok = expected in matched
                passes += ok
                print(f"    {'✓' if ok else '✗'}  {filename:<28} expected: {expected}")
        print(f"  Score: {passes}/{total_products}")
        scorer_passes[scorer_name] = passes

    return scorer_passes, total_products


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def print_summary(
    suite_a: dict[str, int],
    total_a: int,
    suite_b: dict[str, int],
    total_b: int,
) -> None:
    print("\n" + "=" * 72)
    print("SUMMARY")
    print(f"  {'Scorer':<30} {'Suite A':>12} {'Suite B':>12} {'Total':>12}")
    print("  " + "-" * 68)

    rows = []
    for name in SCORERS:
        a = suite_a.get(name, 0)
        b = suite_b.get(name, 0)
        rows.append((name, a, b, a + b))
    rows.sort(key=lambda r: r[3], reverse=True)

    grand_total = total_a + total_b
    for i, (name, a, b, total) in enumerate(rows):
        a_str = f"{a}/{total_a}" if total_a else "n/a"
        b_str = f"{b}/{total_b}" if total_b else "n/a"
        t_str = f"{total}/{grand_total}"
        best = " ← best" if i == 0 else ""
        print(f"  {name:<30} {a_str:>12} {b_str:>12} {t_str:>12}{best}")

    print()
    if rows:
        winner = rows[0][0].replace(" (current)", "")
        print(f"  To apply: set `_SCORER = fuzz.{winner}` in rekognition.py")
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    labeled, labels, name_by_label = load_catalog()
    print(f"Catalog: {len(labeled)} labeled products loaded")

    suite_a_results, suite_a_total = run_suite_a(labeled, labels, name_by_label)
    suite_b_results, suite_b_total = run_suite_b(labels, name_by_label)
    print_summary(suite_a_results, suite_a_total, suite_b_results, suite_b_total)
