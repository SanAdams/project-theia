from fastapi import APIRouter, UploadFile, File, HTTPException
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional

from app.services.rekognition import detect_box_labels
from app.services.image_processor import prepare_image
from app.services.debug_annotator import annotate_scan

BARCODES_DIR = Path(__file__).parent.parent.parent / "static" / "barcodes"
DEBUG_DIR = Path(__file__).parent.parent.parent / "static" / "debug"
MAX_DEBUG_IMAGES = 10

router = APIRouter()


class InventoryItem(BaseModel):
    name: str
    cic_code: str
    count: int
    barcode_image_url: Optional[str] = None


class InventoryResult(BaseModel):
    items: List[InventoryItem]
    total_boxes: int
    debug_image_url: Optional[str] = None


@router.post("/scan", response_model=InventoryResult)
async def scan_image(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    raw_bytes = await file.read()
    image_bytes = prepare_image(raw_bytes)

    matched_products, bboxes = detect_box_labels(image_bytes)

    known = [p for p in matched_products if p.cic_code != "--"]
    unknown_count = sum(1 for p in matched_products if p.cic_code == "--")

    counts: Counter = Counter(p.cic_code for p in known)
    product_map = {p.cic_code: p for p in known}

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
    items += [
        InventoryItem(name="Unknown", cic_code="--", count=1, barcode_image_url=None)
        for _ in range(unknown_count)
    ]

    debug_image_url = None
    if matched_products and bboxes:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        existing = sorted(DEBUG_DIR.glob("scan_*.jpg"))
        while len(existing) >= MAX_DEBUG_IMAGES:
            existing.pop(0).unlink()
        annotated = annotate_scan(image_bytes, matched_products, bboxes)
        debug_path = DEBUG_DIR / f"scan_{timestamp}.jpg"
        debug_path.write_bytes(annotated)
        debug_image_url = f"/static/debug/scan_{timestamp}.jpg"

    return InventoryResult(
        items=items,
        total_boxes=len(matched_products),
        debug_image_url=debug_image_url,
    )
