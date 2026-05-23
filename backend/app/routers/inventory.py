from fastapi import APIRouter, UploadFile, File, HTTPException
from collections import Counter
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional

from app.services.rekognition import detect_box_labels
from app.services.image_processor import prepare_image

BARCODES_DIR = Path(__file__).parent.parent.parent / "static" / "barcodes"

router = APIRouter()


class InventoryItem(BaseModel):
    name: str
    cic_code: str
    count: int
    barcode_image_url: Optional[str] = None


class InventoryResult(BaseModel):
    items: List[InventoryItem]
    total_boxes: int


@router.post("/scan", response_model=InventoryResult)
async def scan_image(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    raw_bytes = await file.read()
    image_bytes = prepare_image(raw_bytes)

    matched_products = detect_box_labels(image_bytes)

    counts: Counter = Counter(p.cic_code for p in matched_products)
    product_map = {p.cic_code: p for p in matched_products}

    items = [
        InventoryItem(
            name=product_map[cic].name,
            cic_code=cic,
            count=count,
            barcode_image_url=(
                f"/static/barcodes/{cic}.png"
                if (BARCODES_DIR / f"{cic}.png").exists()
                else None
            ),
        )
        for cic, count in sorted(counts.items())
    ]

    return InventoryResult(items=items, total_boxes=sum(counts.values()))
