"""Model registry: loads the trained ensemble once and turns a photo into a diagnosis.

Files expected in models/ (produced by the Colab notebook's export cell):
    class_names.json, calibration.json, efficientnetv2s.pt, swin_t.pt
calibration.json says which models make up the ensemble and holds, per model, the timm architecture
name, input size, normalisation, temperature, plus the rejection thresholds chosen on validation data.

Pipeline for one photo:
    squash to a square (as in training) -> each model's logits -> divide by its temperature -> softmax
    -> average the models -> top-3 -> reject if confidence is low or the distribution is too flat
    -> Grad-CAM heatmap and severity (only for an accepted, non-healthy answer).
"""
import base64
import io
import json
import logging
import os
import threading
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms as T

from backend import config
from backend.services import gradcam, severity

log = logging.getLogger(__name__)


class ModelNotReady(RuntimeError):
    """Raised when a prediction is requested but no usable model is available."""


def _png_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def normalised_entropy(p: np.ndarray) -> float:
    """Shannon entropy of a probability vector divided by its maximum, so 0 = certain and 1 = completely unsure."""
    return float(-(p * np.log(p + 1e-12)).sum() / np.log(len(p)))


class _Loaded:
    """Everything built from the model files, created once."""

    def __init__(self, models_dir):
        import timm  # imported here so the Flask app starts quickly even without trained models

        cal = json.loads((models_dir / "calibration.json").read_text(encoding="utf-8"))
        self.class_names = json.loads((models_dir / "class_names.json").read_text(encoding="utf-8"))
        self.reject = cal["reject"]
        self.names = list(cal["ensemble"])
        self.models, self.tfms, self.temps, self.sizes = {}, {}, {}, {}
        torch.set_num_threads(max(1, min(2, os.cpu_count() or 1)))  # a free Hugging Face Space has 2 vCPUs
        for name in self.names:
            spec = cal["models"][name]
            model = timm.create_model(spec["timm_name"], pretrained=False, num_classes=len(self.class_names), **(spec.get("kwargs") or {}))
            state = torch.load(models_dir / spec["file"], map_location="cpu", weights_only=True)
            model.load_state_dict(state)
            self.models[name] = model.eval()
            self.sizes[name] = spec["img_size"]
            self.temps[name] = float(spec["temperature"] or 1.0)
            # Same transform as validation/test in the notebook: resize to a square, no crop.
            self.tfms[name] = T.Compose([T.Resize((spec["img_size"], spec["img_size"])), T.ToTensor(),
                                         T.Normalize(spec["mean"], spec["std"])])
        # Grad-CAM runs on the first ensemble member that it supports.
        self.cam_name = next((n for n in self.names if gradcam.is_supported(self.models[n])), None)


class ModelRegistry:
    def __init__(self, models_dir=None):
        self.models_dir = Path(models_dir) if models_dir else None  # None => read config.MODELS_DIR on each call
        self._lock = threading.Lock()
        self._loaded = None
        self._failed_signature = None

    # ---- discovery ---------------------------------------------------------------
    @property
    def dir(self):
        return self.models_dir or config.MODELS_DIR

    def _missing(self) -> list[str]:
        """Files still needed in models/. The weight files are the ones named in calibration.json."""
        missing = [f for f in ("class_names.json", "calibration.json") if not (self.dir / f).exists()]
        if "calibration.json" in missing:  # cannot know the weight names yet: report the expected ones
            return missing + ["efficientnetv2s.pt", "swin_t.pt"]
        try:
            cal = json.loads((self.dir / "calibration.json").read_text(encoding="utf-8"))
            weights = [cal["models"][n]["file"] for n in cal["ensemble"]]
        except (OSError, ValueError, KeyError):
            return missing + ["calibration.json (unreadable or incomplete)"]
        return missing + [f for f in weights if not (self.dir / f).exists()]

    def _signature(self):
        """Changes whenever a file in models/ is added, replaced or edited, so a failed load is retried then."""
        if not self.dir.exists():
            return ()
        return tuple(sorted((p.name, p.stat().st_mtime_ns) for p in self.dir.iterdir() if p.suffix in (".pt", ".json")))

    def class_names(self) -> list[str]:
        path = self.dir / "class_names.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
        return list(config.CLASS_NAMES)

    def _ensure_loaded(self):
        """Load the models on first use. Returns (loaded or None, reason)."""
        with self._lock:
            if self._loaded is not None:
                return self._loaded, ""
            missing = self._missing()
            if missing:
                return None, "Missing in models/: " + ", ".join(missing)
            sig = self._signature()
            if sig == self._failed_signature:
                return None, self._failed_reason
            try:
                self._loaded = _Loaded(self.dir)
                return self._loaded, ""
            except Exception as exc:  # corrupt file, wrong architecture, out of memory ...
                log.exception("Could not load models")
                self._failed_signature, self._failed_reason = sig, f"Model files found but could not be loaded: {exc}"
                return None, self._failed_reason

    def status(self) -> dict:
        loaded, reason = self._ensure_loaded()
        return {"ready": loaded is not None, "reason": reason}

    def is_ready(self) -> bool:
        return self.status()["ready"]

    # ---- prediction --------------------------------------------------------------
    def predict(self, image: Image.Image) -> dict:
        loaded, reason = self._ensure_loaded()
        if loaded is None:
            raise ModelNotReady(reason)
        L = loaded
        image = image.convert("RGB")

        # Build the input tensors OUTSIDE inference_mode: Grad-CAM later needs a backward pass through them,
        # and PyTorch refuses that for tensors created inside inference_mode.
        tensors = {name: L.tfms[name](image).unsqueeze(0) for name in L.names}
        probs = []
        with torch.inference_mode():
            for name in L.names:
                probs.append(F.softmax(L.models[name](tensors[name])[0] / L.temps[name], dim=0).numpy())
        p = np.mean(probs, axis=0)

        order = np.argsort(-p)
        top3 = [{"label": L.class_names[i], "confidence": float(p[i])} for i in order[:3]]
        conf, ent = float(p[order[0]]), normalised_entropy(p)
        reasons = []
        if conf < L.reject["min_confidence"]:
            reasons.append("low_confidence")
        if ent > L.reject["max_normalised_entropy"]:
            reasons.append("high_entropy")
        rejected = bool(reasons)
        label = L.class_names[order[0]]

        result = {
            "label": None if rejected else label,
            "confidence": conf,
            "rejected": rejected,
            "reject_reasons": reasons,
            "entropy": ent,
            "top3": top3,
            "heatmap_png_b64": None,
            "severity": None,
            "models_used": L.names,
        }
        if rejected:
            return result

        # Heatmap: for the accepted class, on one model (see gradcam.py).
        if L.cam_name is not None:
            try:
                size = L.sizes[L.cam_name]
                rgb = np.asarray(image.resize((size, size), Image.BILINEAR))
                result["heatmap_png_b64"] = _png_b64(gradcam.heatmap_overlay(L.models[L.cam_name], tensors[L.cam_name], int(order[0]), rgb))
                result["heatmap_model"] = L.cam_name
            except Exception:  # a heatmap failure must not lose the diagnosis
                log.exception("Grad-CAM failed")

        # Severity only makes sense for a diseased leaf.
        if label.lower() != "healthy":
            sev = severity.estimate(image, with_overlay=True)
            overlay = sev.pop("overlay", None)
            if overlay is not None:
                sev["overlay_png_b64"] = _png_b64(overlay)
            result["severity"] = sev
        return result
