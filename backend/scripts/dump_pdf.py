import pdfplumber
from pathlib import Path

PDF_PATH = Path(__file__).parent.parent / "Order Inventory Guides Jan 2026.pdf"

with pdfplumber.open(PDF_PATH) as pdf:
    for i, page in enumerate(pdf.pages):
        print(f"\n{'='*60}")
        print(f"PDF PAGE {i+1}")
        print("=" * 60)
        words = page.extract_words()
        for w in words:
            print(f"  x={w['x0']:6.1f}  y={w['top']:6.1f}  {w['text']!r}")
