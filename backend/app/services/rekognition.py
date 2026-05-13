import boto3
from rapidfuzz import process
import json
import os
from pathlib import Path
from typing import List, Optional

from app.models import Product

_client = None
_products: List[Product] | None = None

_PRODUCTS_PATH = Path(__file__).parent.parent.parent / "products.json"
_MATCH_CUTOFF = 0.75


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "rekognition",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
    return _client


def _get_products() -> List[Product]:
    global _products
    if _products is None:
        data = json.loads(_PRODUCTS_PATH.read_text()) if _PRODUCTS_PATH.exists() else []
        if data and isinstance(data[0], str):
            _products = [Product(name=item, cic_code="") for item in data]
        else:
            _products = [
                Product(
                    name=p["name"],
                    cic_code=p.get("CIC Code", ""),
                    barcode=p.get("barcode", ""),
                    page=p.get("page", 0),
                )
                for p in data
            ]
    return _products


def _match_product(label: str) -> Optional[Product]:
    products = _get_products()
    if not products:
        return None
    names = [p.name for p in products]
    result = process.extractOne(label, names, score_cutoff=_MATCH_CUTOFF * 100)
    if not result:
        return None
    matched_name = result[0]
    return next(p for p in products if p.name == matched_name)


def detect_box_labels(image_bytes: bytes) -> List[Product]:
    """
    Calls Rekognition DetectText and returns one matched Product per detected
    LINE that clears the confidence and fuzzy-match thresholds.
    """
    client = _get_client()
    response = client.detect_text(Image={"Bytes": image_bytes})

    labels = [
        detection["DetectedText"]
        for detection in response["TextDetections"]
        if detection["Type"] == "LINE" and detection["Confidence"] >= 80.0
    ]

    matched = [_match_product(label) for label in labels]
    return [p for p in matched if p is not None]
