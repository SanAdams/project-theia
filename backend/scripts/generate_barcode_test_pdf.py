"""
Generate a test PDF listing every product with its canonical name, CIC code,
and extracted barcode image.

Products are listed in products.json order.
Barcode images are read from static/barcodes/<cic_code>.png.

Output: backend/barcode_test.pdf

Run from backend/:
    python scripts/generate_barcode_test_pdf.py
"""

import json
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Table,
    TableStyle,
)

BASE_DIR = Path(__file__).parent.parent
PRODUCTS_PATH = BASE_DIR / "products.json"
BARCODES_DIR = BASE_DIR / "static" / "barcodes"
OUTPUT_PATH = BASE_DIR / "barcode_test.pdf"

# Column widths (points). Letter page = 612pt wide; margins = 36pt each side.
# Usable width = 540pt.
COL_NAME = 220
COL_CIC = 90
COL_BARCODE = 230
ROW_HEIGHT = 36  # pt — tall enough for the barcode image

BARCODE_W = 110  # pt — rendered width inside the cell
BARCODE_H = 28  # pt — rendered height inside the cell


def build_pdf() -> None:
    with open(PRODUCTS_PATH, encoding="utf-8") as f:
        products = json.load(f)

    styles = getSampleStyleSheet()
    name_style = styles["Normal"]
    name_style.fontSize = 8
    name_style.leading = 10

    header = [
        Paragraph("<b>Product Name</b>", name_style),
        Paragraph("<b>CIC Code</b>", name_style),
        Paragraph("<b>Barcode</b>", name_style),
    ]

    rows = [header]
    missing = 0

    for product in products:
        name = product.get("name", "—")
        cic = product.get("CIC Code", "—")
        barcode_path = BARCODES_DIR / f"{cic}.png"

        if barcode_path.exists():
            barcode_cell = RLImage(
                str(barcode_path),
                width=BARCODE_W,
                height=BARCODE_H,
            )
        else:
            barcode_cell = Paragraph("<i>missing</i>", name_style)
            missing += 1

        rows.append(
            [
                Paragraph(name, name_style),
                Paragraph(cic, name_style),
                barcode_cell,
            ]
        )

    table = Table(
        rows,
        colWidths=[COL_NAME, COL_CIC, COL_BARCODE],
        rowHeights=None,  # let reportlab auto-size rows
        repeatRows=1,
    )

    table.setStyle(
        TableStyle(
            [
                # Header row
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1C1C1E")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                # Alternating row shading
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F2F2F7")],
                ),
                # Grid
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C7C7CC")),
                # Padding
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                # Vertical alignment — centre barcodes
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
        title="Barcode Extraction Test",
    )

    doc.build([table])

    print(f"Generated: {OUTPUT_PATH}")
    print(f"Products:  {len(products)}")
    print(f"Missing barcodes: {missing}")


if __name__ == "__main__":
    build_pdf()
