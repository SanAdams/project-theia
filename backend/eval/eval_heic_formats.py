#!/usr/bin/env python3
"""
Compare HEIC-to-Rekognition conversion strategies for product matching.

Converts the HEIC test image three ways — PNG (lossless), JPEG-95, JPEG-85 —
then runs the PRODUCTION OCR + matching pipeline on each (via harness.py) so the
comparison reflects exactly what production would extract and match. Uses the
production scorer/cutoff, not a hardcoded one (previously this drifted to WRatio
while production ran partial_ratio).

OCR is cached by hash(converted bytes + pipeline version); subsequent runs cost nothing.

Usage:
    cd backend
    python scripts/eval/eval_heic_formats.py
"""

import io
import sys
from pathlib import Path

import pillow_heif
from PIL import Image

from backend.eval.harness import (
    BACKEND_DIR,
    get_cached_units,
    load_catalog,
    save_cached_units,
)

from app.services.rekognition import get_match_units, match_text

pillow_heif.register_heif_opener()

HEIC_PATH = BACKEND_DIR / "tests" / "test_images" / "IMG_20260526_221011 (4) (1).heic"
STRATEGIES = ["png", "jpeg-95", "jpeg-85"]
MAX_BYTES = 5 * 1024 * 1024


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


def units_for_bytes(converted: bytes) -> list[str]:
    """Cached production match-units for already-converted image bytes."""
    cached = get_cached_units(converted)
    if cached is not None:
        return cached
    units = get_match_units(converted)
    save_cached_units(converted, units)
    return units


def match_all(units: list[str], labeled) -> set[str]:
    """Match using the PRODUCTION scorer/cutoff (match_text defaults)."""
    matched: set[str] = set()
    for unit in units:
        r = match_text(unit, labeled)
        if r.product is not None:
            matched.add(r.product.name)
    return matched


def main() -> None:
    if not HEIC_PATH.exists():
        print(f"ERROR: HEIC test file not found:\n  {HEIC_PATH}")
        sys.exit(1)

    raw = HEIC_PATH.read_bytes()
    print(f"Source: {HEIC_PATH.name}  ({len(raw) / 1024:.1f} KB HEIC)")

    labeled, _ = load_catalog()
    print(f"Catalog: {len(labeled)} labeled products\n")

    results: dict[str, dict] = {}
    for strategy in STRATEGIES:
        converted = convert(raw, strategy)
        size_kb = len(converted) / 1024

        if len(converted) > MAX_BYTES:
            print(f"  [{strategy}]  {size_kb:.1f} KB — EXCEEDS 5 MB LIMIT, skipping")
            results[strategy] = {"size_kb": size_kb, "units": None, "matched": None}
            continue

        cached = get_cached_units(converted)
        if cached is None:
            print(f"  [{strategy}]  {size_kb:.1f} KB — calling AWS...")
            units = units_for_bytes(converted)
            print(f"    -> {len(units)} match units, cached")
        else:
            units = cached
            print(f"  [{strategy}]  {size_kb:.1f} KB — {len(units)} units (cached)")

        results[strategy] = {
            "size_kb": size_kb,
            "units": units,
            "matched": match_all(units, labeled),
        }

    viable = {s: r for s, r in results.items() if r["matched"] is not None}
    all_products = (
        sorted(set().union(*(r["matched"] for r in viable.values()))) if viable else []
    )

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
                (f"{'+' if product in viable[s]['matched'] else '-':^10}")
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
                f"   {len(r['units']):>3} units"
                f"   {len(r['matched']):>2} products matched"
            )

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
