"""Thin wrapper around the Flask API so the UI code never touches `requests`."""
import os

import requests

API_URL = os.environ.get("API_URL", "http://127.0.0.1:5000").rstrip("/")
TIMEOUT_S = 60  # first CPU inference after a cold start can be slow


class BackendDown(Exception):
    """The Flask server cannot be reached."""


class ModelNotReady(Exception):
    """Backend is up but has no trained model yet (HTTP 503)."""

    def __init__(self, reason: str = "", quality: dict | None = None):
        super().__init__(reason)
        self.reason = reason
        self.quality = quality  # the photo-quality check works even without a model


class BadImage(Exception):
    """Backend rejected the image (HTTP 400/413). The message is user-safe."""


class BackendError(Exception):
    """Any other backend failure."""


def health() -> dict | None:
    """Return the /api/health JSON, or None if the backend is unreachable."""
    try:
        r = requests.get(f"{API_URL}/api/health", timeout=3)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def predict(image_bytes: bytes, filename: str) -> dict:
    try:
        r = requests.post(
            f"{API_URL}/api/predict",
            files={"image": (filename, image_bytes)},
            timeout=TIMEOUT_S,
        )
    except requests.ConnectionError as exc:
        raise BackendDown(str(exc)) from exc
    except requests.RequestException as exc:  # timeouts etc.
        raise BackendError(str(exc)) from exc

    try:
        body = r.json()
    except ValueError:
        raise BackendError(f"Unexpected response (HTTP {r.status_code}).")

    if r.status_code == 200:
        return body
    if r.status_code == 503 and body.get("error") == "model_not_ready":
        raise ModelNotReady(body.get("reason", ""), body.get("quality"))
    if r.status_code in (400, 413):
        raise BadImage(body.get("message", "The image was rejected."))
    raise BackendError(body.get("message", f"HTTP {r.status_code}"))


def names(lang: str) -> dict:
    """Localised disease names {label: name}. Empty dict if the backend cannot be reached (callers fall back to English labels)."""
    try:
        r = requests.get(f"{API_URL}/api/classes", params={"lang": lang}, timeout=5)
        r.raise_for_status()
        return r.json().get("names", {})
    except (requests.RequestException, ValueError):
        return {}


def info(label: str, lang: str, severity: str | None = None) -> dict | None:
    """Knowledge-base text for a diagnosis, or None if unavailable."""
    try:
        params = {"label": label, "lang": lang, **({"severity": severity} if severity else {})}
        r = requests.get(f"{API_URL}/api/info", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def report(image_bytes: bytes, filename: str, result: dict, lang: str) -> bytes:
    """Ask the backend for the PDF report. Returns the PDF bytes."""
    import json

    slim = dict(result)
    if isinstance(slim.get("severity"), dict):  # the severity overlay is large and not used in the PDF
        slim["severity"] = {k: v for k, v in slim["severity"].items() if k != "overlay_png_b64"}
    try:
        r = requests.post(
            f"{API_URL}/api/report",
            files={"image": (filename, image_bytes)},
            data={"result": json.dumps(slim), "lang": lang},
            timeout=TIMEOUT_S,
        )
    except requests.ConnectionError as exc:
        raise BackendDown(str(exc)) from exc
    except requests.RequestException as exc:
        raise BackendError(str(exc)) from exc
    if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/pdf"):
        return r.content
    try:
        raise BackendError(r.json().get("message", f"HTTP {r.status_code}"))
    except ValueError:
        raise BackendError(f"HTTP {r.status_code}")
