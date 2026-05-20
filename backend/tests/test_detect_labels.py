"""
Quick test: run Rekognition DetectLabels on an image and save an annotated copy.

Usage (from backend/ with venv active):
    python scripts/test_detect_labels.py path/to/freezer.jpg

Output:
    - Prints every detected label with confidence and bounding box
    - Saves  <original_name>_labels.jpg  with boxes drawn on it
"""

import sys
import os
import json
import boto3
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()

BOX_LABELS = {"Box", "Cardboard", "Carton", "Container", "Package", "Packaging"}
MIN_CONFIDENCE = 50.0  # lower than normal so we see everything rekognition finds


def main(image_path: str):
    path = Path(image_path)
    if not path.exists():
        print(f"File not found: {image_path}")
        sys.exit(1)

    image_bytes = path.read_bytes()

    client = boto3.client(
        "rekognition", region_name=os.getenv("AWS_REGION", "us-east-1")
    )

    print(f"Sending {path.name} to Rekognition DetectLabels …\n")
    response = client.detect_labels(
        Image={"Bytes": image_bytes},
        MinConfidence=MIN_CONFIDENCE,
    )

    labels = response["Labels"]
    print(f"{'Label':<30} {'Conf':>6}   Instances")
    print("-" * 60)
    for label in sorted(labels, key=lambda l: l["Confidence"], reverse=True):
        instances = label.get("Instances", [])
        bb_summary = ""
        if instances:
            for inst in instances:
                bb = inst["BoundingBox"]
                bb_summary += (
                    f"  [{inst['Confidence']:.0f}%] "
                    f"x={bb['Left']:.3f}–{bb['Left']+bb['Width']:.3f} "
                    f"y={bb['Top']:.3f}–{bb['Top']+bb['Height']:.3f}"
                )
        print(f"  {label['Name']:<28} {label['Confidence']:>5.1f}%{bb_summary}")

    # --- annotate image ---
    img = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    box_like = [l for l in labels if l["Name"] in BOX_LABELS]
    if not box_like:
        print(
            "\nNo box-like labels detected. Annotating ALL labels that have bounding boxes."
        )
        box_like = [l for l in labels if l.get("Instances")]

    drawn = 0
    for label in box_like:
        for inst in label.get("Instances", []):
            bb = inst["BoundingBox"]
            x0 = bb["Left"] * w
            y0 = bb["Top"] * h
            x1 = x0 + bb["Width"] * w
            y1 = y0 + bb["Height"] * h
            draw.rectangle([x0, y0, x1, y1], outline="red", width=3)
            draw.text(
                (x0 + 4, y0 + 4),
                f"{label['Name']} {inst['Confidence']:.0f}%",
                fill="red",
            )
            drawn += 1

    out_path = path.with_stem(path.stem + "_labels")
    img.save(out_path)
    print(f"\nAnnotated {drawn} instance(s) → {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_detect_labels.py <image>")
        sys.exit(1)
    main(sys.argv[1])
