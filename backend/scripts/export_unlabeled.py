"""Export products without a label field to a CSV (Name, CIC Code).

Usage (from backend/):
    python scripts/export_unlabeled.py [output.csv]
"""

import csv
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
PRODUCTS_PATH = BACKEND / "products.json"
DEFAULT_OUT = BACKEND / "unlabeled_products.csv"


def main() -> None:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT

    with open(PRODUCTS_PATH, encoding="utf-8") as f:
        products = json.load(f)

    unlabeled = [p for p in products if not str(p.get("label", "")).strip()]

    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "CIC Code"])
        for p in unlabeled:
            writer.writerow([p["name"], p["CIC Code"]])

    print(f"Wrote {len(unlabeled)} of {len(products)} products to {out_path}")


if __name__ == "__main__":
    main()
