import boto3
import os
from typing import List

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "rekognition",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
    return _client


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

    # TODO: add product-name normalization here (fuzzy match against a known
    # product list) so minor OCR variations don't create duplicate entries.
    return labels
