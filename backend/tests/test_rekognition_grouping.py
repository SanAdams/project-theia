from unittest.mock import patch, MagicMock
from app.services.rekognition import _match_from_crops, _match_full_image
from app.models import Product

RING_DONUT = Product(
    name="Ring Donut",
    cic_code="94981327",
    label="Ready To Finish Ring Yeast-Raised Donut",
)


def _line(text, top, confidence=99.0):
    return {
        "DetectedText": text,
        "Type": "LINE",
        "Confidence": confidence,
        "Geometry": {
            "BoundingBox": {"Left": 0.1, "Top": top, "Width": 0.5, "Height": 0.04}
        },
    }


def test_match_from_crops_joins_lines_before_matching():
    """_match_from_crops must call _match_product with all crop lines joined, not one-by-one."""
    client = MagicMock()
    client.detect_text.return_value = {
        "TextDetections": [
            _line("Ready To Finish", 0.10),
            _line("Ring Yeast-Raised", 0.15),
            _line("Donut", 0.20),
        ]
    }

    with patch("app.services.rekognition._get_products", return_value=[RING_DONUT]):
        with patch(
            "app.services.rekognition._match_product", return_value=None
        ) as mock_match:
            with patch("app.services.rekognition._crop_region", return_value=b"crop"):
                regions = [{"Left": 0.0, "Top": 0.0, "Width": 1.0, "Height": 1.0}]
                _match_from_crops(client, b"fake", regions)

    called_with = [c.args[0] for c in mock_match.call_args_list]
    assert called_with == [
        "Ready To Finish Ring Yeast-Raised Donut"
    ], f"Expected joined text, got: {called_with}"


def test_match_full_image_joins_group_lines_before_matching():
    """_match_full_image must call _match_product with all group lines joined, not one-by-one."""
    client = MagicMock()
    # Two lines close enough in Y to fall into one spatial group
    client.detect_text.return_value = {
        "TextDetections": [
            _line("Ready To Finish Ring", 0.10),
            _line("Yeast-Raised Donut", 0.13),
        ]
    }

    with patch("app.services.rekognition._get_products", return_value=[RING_DONUT]):
        with patch(
            "app.services.rekognition._match_product", return_value=None
        ) as mock_match:
            _match_full_image(client, b"fake")

    called_with = [c.args[0] for c in mock_match.call_args_list]
    assert called_with == [
        "Ready To Finish Ring Yeast-Raised Donut"
    ], f"Expected joined text, got: {called_with}"
