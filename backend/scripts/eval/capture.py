#!/usr/bin/env python3
"""Add a real-photo eval case with minimal typing.

Runs the PRODUCTION OCR pipeline on a photo once, caches the resulting match units,
copies the image into scripts/eval/images/, and appends a fillable stub to dataset.json.
You then just fill in the expected products (or nothing, for a negative case).

Usage:
    cd backend
    python scripts/eval/capture.py path/to/photo.jpg
    python scripts/eval/capture.py path/to/junk_box.jpg --negative --note "cleaning supplies"

Positive captures are added to image_cases as exhaustive by default (set "partial": true
later if the shelf is too crowded to label completely). Negative captures go to
negative_cases and must match nothing. Re-capturing the same filename refreshes the cached
OCR without duplicating the dataset entry.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from harness import DATASET_PATH, EVAL_DIR, load_dataset, save_cached_units

from app.services.image_processor import prepare_image
from app.services.rekognition import get_match_units

IMAGES_DIR = EVAL_DIR / "images"


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture an eval case from a photo.")
    parser.add_argument("photo", help="path to the source image")
    parser.add_argument(
        "--negative",
        action="store_true",
        help="add as a negative case (must match nothing)",
    )
    parser.add_argument("--note", default="", help="optional note stored on the case")
    args = parser.parse_args()

    src = Path(args.photo)
    if not src.exists():
        print(f"ERROR: {src} not found")
        sys.exit(1)

    IMAGES_DIR.mkdir(exist_ok=True)
    dest = IMAGES_DIR / src.name
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    rel = f"images/{src.name}"

    # OCR once via production pipeline; cache keyed on the stored image bytes so the
    # eval/gate find it later without re-calling AWS.
    image_bytes = dest.read_bytes()
    print(f"Running production OCR on {src.name} ...")
    units = get_match_units(prepare_image(image_bytes))
    save_cached_units(image_bytes, units)

    print(f"\nCached {len(units)} match unit(s):")
    for i, u in enumerate(units, 1):
        print(f"  {i}. {u!r}")

    dataset = load_dataset()
    bucket = "negative_cases" if args.negative else "image_cases"
    dataset.setdefault(bucket, [])

    existing = next((c for c in dataset[bucket] if c.get("file") == rel), None)
    if existing is not None:
        if args.note:
            existing["note"] = args.note
        action = "refreshed existing"
    else:
        if args.negative:
            dataset[bucket].append(
                {"file": rel, "note": args.note or "must match nothing"}
            )
        else:
            dataset[bucket].append(
                {
                    "file": rel,
                    "expected": [""],
                    "partial": False,
                    "note": args.note or "FILL IN expected products",
                }
            )
        action = "added new"

    DATASET_PATH.write_text(json.dumps(dataset, indent=2) + "\n")

    print(f"\n{action} {bucket[:-1]} for {rel} in dataset.json.")
    if not args.negative and existing is None:
        print(
            '  -> Edit dataset.json: replace expected [""] with the products that should match.'
        )
    print("Then run: python scripts/eval/eval_matching.py")


if __name__ == "__main__":
    main()
