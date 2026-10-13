"""Flask API for rice leaf disease detection.

Run from the project root:
    flask --app backend.app:create_app run --port 5000

Endpoints
    GET  /api/health   -> {status, model_loaded, model_reason, classes}
    POST /api/predict  -> multipart field "image" (JPG/JPEG/PNG)
        400 bad file | 413 too large | 503 model not ready | 200 result
        200 body: {label | null, confidence, rejected, reject_reasons, top3[], heatmap_png_b64,
                   severity{percent, level, leaf_found, overlay_png_b64} | null, quality{ok, issues[], ...}}
        503 body also carries "quality", so photo problems can be reported before a model exists.
    GET  /api/classes  -> ?lang=en|kn|hi  {names: {label: localised name}}
    GET  /api/info     -> ?label=Blast&lang=kn&severity=Moderate  knowledge-base text (404 for an unknown label)
    POST /api/report   -> multipart: image, result (JSON from /api/predict), lang  ->  application/pdf
"""
import io
import json
from datetime import datetime

from flask import Flask, Request, Response, jsonify, request
from werkzeug.exceptions import HTTPException

from backend import config
from backend import disease_info as di
from backend.services import pdf_report, quality
from backend.services.image_io import ImageError, load_image
from backend.services.inference import ModelNotReady, ModelRegistry


class _Request(Request):
    # Werkzeug >= 3.1 caps each non-file form field at 500 KB. The /api/report "result" field carries the heatmap
    # (and, if a client sends it, the severity overlay) as base64 text and can reach ~0.6 MB, so raise the cap.
    max_form_memory_size = 4 * 1024 * 1024


def _clean_result(r: dict) -> dict:
    """Keep only the fields the report uses, with safe types. The result comes from the browser, so do not trust it."""
    top3 = [{"label": str(t["label"])[:60], "confidence": min(1.0, max(0.0, float(t["confidence"])))}
            for t in (r.get("top3") or [])[:3]]
    sev = r.get("severity")
    if isinstance(sev, dict) and sev.get("leaf_found"):
        level = sev.get("level")
        if level not in ("Mild", "Moderate", "Severe"):
            raise ValueError("bad severity level")
        sev = {"leaf_found": True, "level": level, "percent": min(100.0, max(0.0, float(sev["percent"])))}
    elif isinstance(sev, dict):
        sev = {"leaf_found": False}
    else:
        sev = None
    quality_in = r.get("quality") or {}
    issues = [i for i in (quality_in.get("issues") or []) if i in ("blurry", "too_dark", "overexposed")]
    label = r.get("label")
    return {
        "label": None if label is None else str(label),
        "rejected": bool(r.get("rejected")),
        "reject_reasons": [x for x in (r.get("reject_reasons") or []) if x in ("low_confidence", "high_entropy")],
        "confidence": min(1.0, max(0.0, float(r.get("confidence") or 0))),
        "top3": top3,
        "heatmap_png_b64": r.get("heatmap_png_b64") if isinstance(r.get("heatmap_png_b64"), str) else None,
        "severity": sev,
        "quality": {"issues": issues},
    }


def create_app(registry: ModelRegistry | None = None) -> Flask:
    app = Flask(__name__)
    app.request_class = _Request
    # Flask rejects bodies above this with a 413 before we read them into memory.
    app.config["MAX_CONTENT_LENGTH"] = (config.MAX_UPLOAD_MB + 1) * 1024 * 1024
    registry = registry or ModelRegistry()

    @app.get("/api/health")
    def health():
        status = registry.status()
        return jsonify(
            status="ok",
            model_loaded=status["ready"],
            model_reason=status["reason"],
            classes=registry.class_names(),
        )

    @app.post("/api/predict")
    def predict():
        file = request.files.get("image")
        if file is None:
            return jsonify(error="no_image", message="No image was sent (field name must be 'image')."), 400

        # Same preprocessing for uploads and camera photos.
        try:
            img = load_image(file.filename, file.read())
        except ImageError as exc:
            return jsonify(error="bad_image", message=str(exc)), 400

        photo_quality = quality.assess(img)  # needs no model, so it is reported in every response

        try:
            result = registry.predict(img)
        except ModelNotReady as exc:
            return jsonify(
                error="model_not_ready",
                message="The model has not been trained or installed yet.",
                reason=str(exc),
                image={"width": img.width, "height": img.height},  # proves preprocessing worked
                quality=photo_quality,
            ), 503
        result["quality"] = photo_quality
        result["image"] = {"width": img.width, "height": img.height}
        return jsonify(result)

    @app.get("/api/classes")
    def classes():
        lang = request.args.get("lang", "en")
        return jsonify(lang=lang if lang in di.LANGS else "en", names=di.names(lang))

    @app.get("/api/info")
    def info():
        """Knowledge-base text for one diagnosis. ?label=Blast&lang=kn&severity=Moderate"""
        label, lang = request.args.get("label", ""), request.args.get("lang", "en")
        data = di.get_info(label, lang, request.args.get("severity"))
        if data is None:
            return jsonify(error="unknown_label", message=f"No information for '{label}'."), 404
        titles = pdf_report.S[data["lang"]]  # section titles, so the UI and the PDF use the same words
        data["section_titles"] = {k: titles[k] for k in (
            "description", "symptoms", "causes", "actions", "management", "cultural", "organic", "chemical", "prevention",
            "growth", "nutrient", "water", "spacing", "monitoring", "sources", "sources_note", "translation_note")}
        return jsonify(data)

    @app.post("/api/report")
    def report():
        """multipart: image (the photo), result (the JSON /api/predict returned), lang (en|kn|hi) -> application/pdf"""
        file = request.files.get("image")
        raw = request.form.get("result", "")
        lang = request.form.get("lang", "en")
        if file is None or not raw:
            return jsonify(error="bad_request", message="Send the photo as 'image' and the diagnosis as 'result'."), 400
        try:
            img = load_image(file.filename, file.read())
        except ImageError as exc:
            return jsonify(error="bad_image", message=str(exc)), 400
        try:
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError
            result = _clean_result(result)
        except (ValueError, TypeError, KeyError):
            return jsonify(error="bad_result", message="The diagnosis data could not be read."), 400
        label = result.get("label")
        if label is not None and label not in di.INFO:
            return jsonify(error="bad_result", message=f"Unknown diagnosis '{label}'."), 400
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=88)  # the processed photo (EXIF-corrected, downscaled)
        try:
            pdf = pdf_report.build_report(result, buf.getvalue(), lang)
        except Exception:
            app.logger.exception("PDF generation failed")
            return jsonify(error="report_failed", message="The report could not be created."), 500
        name = f"rice-leaf-report-{datetime.now():%Y%m%d-%H%M}.pdf"
        return Response(pdf, mimetype="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})

    # JSON for every error so the frontend never has to parse an HTML page.
    @app.errorhandler(404)
    def not_found(_):
        return jsonify(error="not_found", message="Unknown endpoint."), 404

    @app.errorhandler(405)
    def bad_method(_):
        return jsonify(error="method_not_allowed", message="Method not allowed."), 405

    @app.errorhandler(413)
    def too_large(_):
        return jsonify(error="too_large", message=f"The request is too large (photos may be at most {config.MAX_UPLOAD_MB} MB)."), 413

    @app.errorhandler(Exception)
    def unexpected(exc):
        if isinstance(exc, HTTPException):  # e.g. a malformed multipart body -> 400, not 500
            return jsonify(error="http_error", message=exc.description), exc.code
        app.logger.exception("Unhandled error")
        return jsonify(error="server_error", message="Something went wrong on the server."), 500

    return app
