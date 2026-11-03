import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models import Product
from app.routers import inventory
from app.services import storage

DONUT = Product(name="Ring Donut", cic_code="94981327", label="RING DONUT")
CAKE = Product(name="Pound Cake", cic_code="94983232", label="POUND CAKE")
UNKNOWN = Product(name="Unknown", cic_code="--", label="")
BBOX = {"Left": 0.1, "Top": 0.1, "Width": 0.3, "Height": 0.3}


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Router mounted on a bare app, with Rekognition/image work faked out and
    all file output redirected to a temp folder."""
    monkeypatch.setattr(storage, "BARCODES_DIR", tmp_path / "barcodes")
    monkeypatch.setattr(inventory, "DEBUG_DIR", tmp_path / "debug")
    monkeypatch.setattr(storage, "CROPS_DIR", tmp_path / "crops")
    monkeypatch.setattr(inventory, "prepare_image", lambda raw: raw)
    monkeypatch.setattr(inventory, "crop_region", lambda img, bb: b"crop")
    monkeypatch.setattr(inventory, "annotate_scan", lambda img, prods, bbs: b"debug")

    def set_detection(products):
        monkeypatch.setattr(
            inventory,
            "detect_box_labels",
            lambda img: (products, [BBOX] * len(products)),
        )

    monkeypatch.delenv("IMAGES_BUCKET", raising=False)

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
    monkeypatch.setattr(storage, "MAX_CROP_IMAGES", 3)
    crops = client.tmp_path / "crops"
    crops.mkdir()
    for name in ("crop_0001.jpg", "crop_0002.jpg", "crop_0003.jpg"):
        (crops / name).write_bytes(b"old")
    client.set_detection([DONUT, CAKE])
    urls = [u for i in _scan(client).json()["items"] for u in i["crop_image_urls"]]
    assert len(urls) == 2
    assert all((crops / u.rsplit("/", 1)[1]).exists() for u in urls)
    assert len(list(crops.glob("crop_*.jpg"))) <= 3


# --- S3 mode through the router ---


class _FakeS3:
    def __init__(self, fail=False):
        self.fail = fail

    def put_object(self, **kw):
        if self.fail:
            raise RuntimeError("boom")

    def generate_presigned_url(self, op, Params, ExpiresIn):
        if self.fail:
            raise RuntimeError("boom")
        return f"https://signed/{Params['Key']}"

    def get_paginator(self, name):
        fake = self

        class P:
            def paginate(self, Bucket, Prefix):
                if fake.fail:
                    raise RuntimeError("boom")
                yield {"Contents": [{"Key": "barcodes/94981327.png"}]}

        return P()


def _use_s3(monkeypatch, fake):
    monkeypatch.setenv("IMAGES_BUCKET", "theia-images")
    monkeypatch.setattr(storage, "_get_s3", lambda: fake)
    monkeypatch.setattr(storage, "_barcode_cics", None)


def test_s3_scan_returns_presigned_urls(client, monkeypatch):
    _use_s3(monkeypatch, _FakeS3())
    client.set_detection([DONUT, CAKE, UNKNOWN])
    items = {i["cic_code"]: i for i in _scan(client).json()["items"]}
    donut = items["94981327"]
    assert donut["barcode_image_url"] == "https://signed/barcodes/94981327.png"
    assert donut["crop_image_urls"][0].startswith("https://signed/crops/crop_")
    assert items["94983232"]["barcode_image_url"] is None
    assert items["--"]["crop_image_urls"][0].startswith("https://signed/crops/")
    assert not (client.tmp_path / "crops").exists()


def test_s3_failure_does_not_fail_the_scan(client, monkeypatch):
    _use_s3(monkeypatch, _FakeS3(fail=True))
    client.set_detection([DONUT, UNKNOWN])
    resp = _scan(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_boxes"] == 2
    donut = next(i for i in body["items"] if i["cic_code"] == "94981327")
    assert donut["barcode_image_url"] is None and donut["crop_image_urls"] == []
    unknown = next(i for i in body["items"] if i["cic_code"] == "--")
    assert unknown["crop_image_urls"] == []
