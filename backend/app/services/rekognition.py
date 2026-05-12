import boto3
from rapidfuzz import process
import json
import os
from pathlib import Path
from typing import List, Dict, Any

_client = None
_products: List[Dict[str, Any]] | None = None

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


def _get_products() -> List[Dict[str, Any]]:
    global _products
    if _products is None:
        data = json.loads(_PRODUCTS_PATH.read_text()) if _PRODUCTS_PATH.exists() else []
        # If it's list of strings (old format), convert to dicts
        if data and isinstance(data[0], str):
            _products = [{"name": item, "CIC Code": "", "page": 0} for item in data]
        else:
            _products = data
    return _products


def _normalize(label: str) -> str:
    products = _get_products()
    if not products:
        return label
    product_names = [p["name"] for p in products]
    match = process.extractOne(label, product_names, score_cutoff=_MATCH_CUTOFF * 100)
    return match[0] if match else label


def detect_box_labels(image_bytes: bytes) -> List[str]:
    """
    Calls Rekognition DetectText and returns one entry per detected LINE,
    filtered to high-confidence results. Each LINE represents a full label
    line on a box (e.g. "Chicken Nuggets 5kg").
    """
    client = _get_client()

    response = client.detect_text(Image={"Bytes": image_bytes})

    labels = [
        detection["DetectedText"]
        for detection in response["TextDetections"]
        if detection["Type"] == "LINE" and detection["Confidence"] >= 80.0
    ]

    return [_normalize(label) for label in labels]
