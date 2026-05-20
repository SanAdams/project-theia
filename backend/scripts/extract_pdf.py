import PyPDF2
from pathlib import Path

PDF_PATH = Path(__file__).parent.parent / "Order Inventory Guides Jan 2026.pdf"

with open(PDF_PATH, "rb") as f:
    reader = PyPDF2.PdfReader(f)
    for i, page in enumerate(reader.pages):
        print(f"\n=== PAGE {i+1} ===")
        print(page.extract_text())
