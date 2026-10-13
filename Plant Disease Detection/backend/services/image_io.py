"""Image validation and preprocessing shared by upload and camera inputs.

Steps (from the project brief): check the file, fix EXIF orientation,
downscale large phone images, convert to RGB.
"""
import io
import os

from PIL import Image, ImageOps, UnidentifiedImageError

from backend import config


class ImageError(ValueError):
    """The uploaded file is unusable. The message is safe to show to the user."""


def load_image(filename: str, data: bytes) -> Image.Image:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in config.ALLOWED_EXT:
        raise ImageError("Unsupported file type. Please upload a JPG, JPEG or PNG image.")
    if not data:
        raise ImageError("The uploaded file is empty.")
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise ImageError(f"Image is larger than {config.MAX_UPLOAD_MB} MB.")

    try:
        img = Image.open(io.BytesIO(data))
        # The extension can lie (e.g. a renamed PDF), so check the decoded format.
        if img.format not in config.ALLOWED_FORMATS:
            raise ImageError("Unsupported image content. Please upload a JPG or PNG photo.")
        img.load()  # force a full decode now so corrupt files fail here, not later
    except ImageError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ImageError("This file could not be read as an image. Please try another photo.")

    # Phones store rotation in EXIF instead of rotating pixels; apply it.
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")  # drops alpha / palette modes the model cannot take
    img.thumbnail((config.MAX_SIDE_PX, config.MAX_SIDE_PX), Image.LANCZOS)  # only shrinks
    return img
