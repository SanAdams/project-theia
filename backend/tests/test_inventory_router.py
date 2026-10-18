import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models import Product
from app.routers import inventory

DONUT = Product(name="Ring Donut", cic_code="94981327", label="RING DONUT")
CAKE = Product(name="Pound Cake", cic_code="94983232", label="POUND CAKE")
UNKNOWN = Product(name="Unknown", cic_code="--", label="")
BBOX = {"Left": 0.1, "Top": 0.1, "Width": 0.3, "Height": 0.3}


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Router mounted on a bare app, with Rekognition/image work faked out and
    all file output redirected to a temp folder."""
    monkeypatch.setattr(inventory, "BARCODES_DIR", tmp_path / "barcodes")
    monkeypatch.setattr(inventory, "DEBUG_DIR", tmp_path / "debug")
    monkeypatch.setattr(inventory, "CROPS_DIR", tmp_path / "crops")
    monkeypatch.setattr(inventory, "prepare_image", lambda raw: raw)
    monkeypatch.setattr(inventory, "crop_region", lambda img, bb: b"crop")
    monkeypatch.setattr(inventory, "annotate_scan", lambda img, prods, bbs: b"debug")

    def set_detection(products):
        monkeypatch.setattr(
            inventory,
            "detect_box_labels",
            lambda img: (products, [BBOX] * len(products)),
        )

    app = FastAPI()
    app.include_router(inventory.router, prefix="/api/v1")
    test_client = TestClient(app)
    test_client.set_detection = set_detection
    test_client.tmp_path = tmp_path
    return test_client


def _scan(client, content_type="image/jpeg"):
    return client.post(
        "/api/v1/scan", files={"file": ("box.jpg", b"fake-bytes", content_type)}
    )


def test_rejects_non_image_upload(client):
    resp = _scan(client, content_type="text/plain")
    assert resp.status_code == 400


def test_no_boxes_returns_empty_result(client):
    client.set_detection([])
    body = _scan(client).json()
    assert body["items"] == []
    assert body["total_boxes"] == 0
    assert body["debug_image_url"] is None


def test_counts_duplicate_products(client):
    client.set_detection([DONUT, CAKE, DONUT])
    body = _scan(client).json()
    counts = {item["cic_code"]: item["count"] for item in body["items"]}
    assert counts == {"94981327": 2, "94983232": 1}
    assert body["total_boxes"] == 3


def test_each_unknown_box_is_its_own_item(client):
    client.set_detection([DONUT, UNKNOWN, UNKNOWN])
    body = _scan(client).json()
    unknowns = [i for i in body["items"] if i["cic_code"] == "--"]
    assert len(unknowns) == 2
    assert all(i["count"] == 1 and len(i["crop_image_urls"]) == 1 for i in unknowns)


def test_crops_are_saved_and_linked_to_their_product(client):
    client.set_detection([DONUT, DONUT])
    body = _scan(client).json()
    urls = body["items"][0]["crop_image_urls"]
    assert len(urls) == 2
    for url in urls:
        assert (client.tmp_path / "crops" / url.rsplit("/", 1)[1]).exists()


def test_barcode_url_only_when_image_exists(client):
    barcodes = client.tmp_path / "barcodes"
    barcodes.mkdir()
    (barcodes / "94981327.png").write_bytes(b"png")
    client.set_detection([DONUT, CAKE])
    items = {i["cic_code"]: i for i in _scan(client).json()["items"]}
    assert items["94981327"]["barcode_image_url"] == "/static/barcodes/94981327.png"
    assert items["94983232"]["barcode_image_url"] is None


def test_debug_image_saved_and_old_ones_pruned(client, monkeypatch):
    monkeypatch.setattr(inventory, "MAX_DEBUG_IMAGES", 2)
    debug = client.tmp_path / "debug"
    debug.mkdir()
    for name in ("scan_0001.jpg", "scan_0002.jpg"):
        (debug / name).write_bytes(b"old")
    client.set_detection([DONUT])
    url = _scan(client).json()["debug_image_url"]
    remaining = sorted(p.name for p in debug.glob("scan_*.jpg"))
    assert url.rsplit("/", 1)[1] in remaining
    assert "scan_0001.jpg" not in remaining
    assert len(remaining) == 2


def test_old_crops_pruned_but_new_ones_kept(client, monkeypatch):
    monkeypatch.setattr(inventory, "MAX_CROP_IMAGES", 3)
    crops = client.tmp_path / "crops"
    crops.mkdir()
    for name in ("crop_0001.jpg", "crop_0002.jpg", "crop_0003.jpg"):
        (crops / name).write_bytes(b"old")
    client.set_detection([DONUT, CAKE])
    urls = [u for i in _scan(client).json()["items"] for u in i["crop_image_urls"]]
    assert len(urls) == 2
    assert all((crops / u.rsplit("/", 1)[1]).exists() for u in urls)
    assert len(list(crops.glob("crop_*.jpg"))) <= 3
