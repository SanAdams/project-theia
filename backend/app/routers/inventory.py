from fastapi import APIRouter, UploadFile, File, HTTPException
from collections import Counter
from pydantic import BaseModel
from typing import List

from app.services.rekognition import detect_box_labels
from app.services.image_processor import prepare_image

router = APIRouter()


class InventoryItem(BaseModel):
    product: str
    count: int


class InventoryResult(BaseModel):
    items: List[InventoryItem]
    total_boxes: int


@router.post("/scan", response_model=InventoryResult)
async def scan_image(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    raw_bytes = await file.read()
    image_bytes = prepare_image(raw_bytes)

    detected_labels = detect_box_labels(image_bytes)

    counts = Counter(detected_labels)
    items = [InventoryItem(product=k, count=v) for k, v in sorted(counts.items())]

    return InventoryResult(items=items, total_boxes=sum(counts.values()))
