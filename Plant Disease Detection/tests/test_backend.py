"""Backend tests. Run from the project root:  pytest tests/"""
import io

import pytest
from PIL import Image

from backend.app import create_app


@pytest.fixture()
def client():
    return create_app().test_client()


def make_image(fmt="JPEG", size=(300, 200), exif_orientation=None) -> bytes:
    img = Image.new("RGB", size, (30, 140, 40))
    buf = io.BytesIO()
    if exif_orientation:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation  # 6 = "rotate 90 degrees clockwise to view"
        img.save(buf, fmt, exif=exif)
    else:
        img.save(buf, fmt)
    return buf.getvalue()


def post(client, data, name="leaf.jpg"):
    return client.post("/api/predict", data={"image": (io.BytesIO(data), name)}, content_type="multipart/form-data")


def test_health(client):
    body = client.get("/api/health").get_json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is False
    assert "Healthy" in body["classes"]


def test_missing_image_is_400(client):
    r = client.post("/api/predict", data={}, content_type="multipart/form-data")
    assert r.status_code == 400 and r.get_json()["error"] == "no_image"


def test_wrong_extension_is_400(client):
    assert post(client, b"hello", "notes.pdf").status_code == 400


def test_renamed_non_image_is_400(client):
    r = post(client, b"this is not an image", "fake.jpg")
    assert r.status_code == 400 and r.get_json()["error"] == "bad_image"


def test_gif_renamed_to_png_is_400(client):
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, "GIF")
    assert post(client, buf.getvalue(), "x.png").status_code == 400


def test_oversized_is_413(client):
    assert post(client, b"0" * (12 * 1024 * 1024)).status_code == 413


def test_valid_image_gets_503_not_fake_prediction(client):
    r = post(client, make_image())
    body = r.get_json()
    assert r.status_code == 503 and body["error"] == "model_not_ready"
    assert body["image"] == {"width": 300, "height": 200}


def test_png_accepted(client):
    assert post(client, make_image("PNG"), "leaf.png").status_code == 503  # passed validation


def test_exif_rotation_applied(client):
    # 300x200 stored sideways with orientation 6 must come out 200x300.
    body = post(client, make_image(exif_orientation=6)).get_json()
    assert body["image"] == {"width": 200, "height": 300}


def test_large_image_downscaled(client):
    body = post(client, make_image(size=(4000, 3000))).get_json()
    assert max(body["image"].values()) == 1024


def test_report_without_data_is_400(client):
    assert client.post("/api/report", data={}, content_type="multipart/form-data").status_code == 400


def test_unknown_route_is_json_404(client):
    r = client.get("/nope")
    assert r.status_code == 404 and r.get_json()["error"] == "not_found"
