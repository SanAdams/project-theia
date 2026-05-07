from unittest.mock import patch
from app.services.rekognition import _normalize

PRODUCTS = [
    "Chicken Nuggets 5kg",
    "Beef Burgers 4kg",
    "Fish Fillets 2.5kg",
]


def test_exact_match():
    with patch("app.services.rekognition._get_products", return_value=PRODUCTS):
        assert _normalize("Chicken Nuggets 5kg") == "Chicken Nuggets 5kg"


def test_ocr_typo():
    with patch("app.services.rekognition._get_products", return_value=PRODUCTS):
        assert _normalize("Chiken Nuggets 5kg") == "Chicken Nuggets 5kg"


def test_case_variation():
    with patch("app.services.rekognition._get_products", return_value=PRODUCTS):
        assert _normalize("chicken nuggets 5kg") == "Chicken Nuggets 5kg"


def test_no_match_returns_raw():
    with patch("app.services.rekognition._get_products", return_value=PRODUCTS):
        assert _normalize("Frozen Pizza 1kg") == "Frozen Pizza 1kg"


def test_empty_product_list():
    with patch("app.services.rekognition._get_products", return_value=[]):
        assert _normalize("anything") == "anything"
