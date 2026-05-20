"""
Parse the order guide PDF into products.json using pdfplumber.

Strategy:
- Separate each page into left/right columns by x-coordinate.
- Group words into lines using Y proximity.
- Track Y positions so that only name lines IMMEDIATELY above a code line
  (gap <= MAX_LINE_GAP) are treated as the product name. Lines further away
  are section headers and are excluded.
"""

import pdfplumber
import re
import json
from pathlib import Path

PDF_PATH = Path(__file__).parent.parent / "Order Inventory Guides Jan 2026.pdf"
OUTPUT_PATH = Path(__file__).parent.parent / "products.json"

COLUMN_MID = 306  # x midpoint splitting left / right columns
Y_TOL = 6  # words within this many y-pixels are on the same line
MAX_NAME_GAP = 16  # max y-gap between a name line and its code line

CODE_RE = re.compile(r"^\d{8,9}$")

PAGE_SKIP_RE = re.compile(
    r"\d+/\s*\d+\s+Updated|^Backroom|^Freezer|^Decorator|^GMHBC",
    re.IGNORECASE,
)


def group_by_line(words):
    """Return list of (y, [token, ...]) sorted top-to-bottom."""
    if not words:
        return []
    words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines = [(words[0]["top"], [words[0]["text"]])]
    for w in words[1:]:
        if abs(w["top"] - lines[-1][0]) <= Y_TOL:
            lines[-1][1].append(w["text"])
        else:
            lines.append((w["top"], [w["text"]]))
    return lines


def parse_column(lines, page_num):
    products = []
    pending = []  # list of (y, text)

    for y, tokens in lines:
        text = " ".join(tokens).strip()
        if not text or PAGE_SKIP_RE.search(text):
            pending = []
            continue

        code, before_tokens = None, []
        for i, t in enumerate(tokens):
            if CODE_RE.match(t):
                code = t
                before_tokens = tokens[:i]
                break

        if code is None:
            pending.append((y, text))
            continue

        before = " ".join(before_tokens).strip()

        close = [t for (ny, t) in pending if (y - ny) <= MAX_NAME_GAP]
        if before:
            close.append(before)

        name = re.sub(r"\s+", " ", " ".join(close)).strip()
        name = re.sub(r"^\d{8,9}\s*", "", name).strip()

        if name:
            products.append({"name": name, "CIC Code": code, "page": page_num})

        pending = []

    return products


products = []

with pdfplumber.open(PDF_PATH) as pdf:
    for page_num, page in enumerate(pdf.pages, 1):
        words = page.extract_words()
        left = [w for w in words if w["x0"] < COLUMN_MID]
        right = [w for w in words if w["x0"] >= COLUMN_MID]
        products.extend(parse_column(group_by_line(left), page_num))
        products.extend(parse_column(group_by_line(right), page_num))

# Deduplicate by CIC code (keep first occurrence)
seen, unique = set(), []
for p in products:
    if p["CIC Code"] not in seen:
        seen.add(p["CIC Code"])
        unique.append(p)

with open(OUTPUT_PATH, "w") as f:
    json.dump(unique, f, indent=2)

print(
    f"Parsed {len(unique)} products ({len(products) - len(unique)} duplicates removed)"
)
