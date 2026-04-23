"""
OCR Service Layer for MarkItDown
Provides LLM Vision-based and offline Tesseract-based image text extraction.
"""

import base64
import io
import sys
from typing import Any, BinaryIO
from dataclasses import dataclass

from markitdown import StreamInfo


@dataclass
class OCRResult:
    """Result from OCR extraction."""

    text: str
    confidence: float | None = None
    backend_used: str | None = None
    error: str | None = None


_tesseract_exc_info = None
try:
    import pytesseract
    from PIL import (
        Image as _PILImage,
        ImageEnhance as _PILImageEnhance,
        ImageFile as _PILImageFile,
        ImageFilter as _PILImageFilter,
        ImageOps as _PILImageOps,
    )

    # Allow Pillow to load truncated/incomplete image files (e.g. interrupted
    # downloads, partially written files from other processes).
    _PILImageFile.LOAD_TRUNCATED_IMAGES = True
except ImportError:
    _tesseract_exc_info = sys.exc_info()

# Cap image dimensions to avoid OOM with 50 MP+ originals while keeping
# enough detail for accurate OCR.
_MAX_OCR_PIXELS = 6000 * 6000  # ~36 MP

# Minimum short-edge size: below this Tesseract's LSTM classifier struggles
# to distinguish strokes.  Images smaller than this are upscaled.
_MIN_SHORT_EDGE = 1000  # px

# Tesseract config: LSTM engine (oem 3 = auto), auto page segmentation (psm 3)
_TESS_CONFIG = "--oem 3 --psm 3"


# --------------------------------------------------------------------------- #
#  Image normalisation helpers
# --------------------------------------------------------------------------- #

def _to_rgb(img: "_PILImage.Image") -> "_PILImage.Image":
    """
    Convert any PIL image mode to a plain 8-bit RGB image that Tesseract
    can accept, handling transparency, palettes, CMYK, high-bit-depth, etc.
    """
    mode = img.mode

    # Palette → expand (keep transparency info if present)
    if mode == "P":
        img = img.convert("RGBA" if "transparency" in img.info else "RGB")
        mode = img.mode

    # Alpha → composite onto white background
    if mode in ("RGBA", "LA"):
        bg = _PILImage.new("RGB", img.size, (255, 255, 255))
        alpha = img.convert("RGBA").split()[3]
        bg.paste(img.convert("RGB"), mask=alpha)
        return bg

    # Colour-space conversions
    if mode in ("CMYK", "YCbCr", "HSV", "LAB"):
        return img.convert("RGB")

    # 32-bit int / float (high-bit-depth scans) → normalise to 8-bit L
    if mode in ("I", "F"):
        import struct
        raw = img.tobytes()
        fmt = "i" if mode == "I" else "f"
        values = list(struct.unpack(f"{len(raw) // 4}{fmt}", raw))
        lo, hi = min(values), max(values)
        span = hi - lo or 1
        pixels = bytes(int((v - lo) / span * 255) for v in values)
        img = _PILImage.frombytes("L", img.size, pixels)
        return img.convert("RGB")

    if mode not in ("RGB", "L"):
        return img.convert("RGB")

    return img


def _resize_for_ocr(img: "_PILImage.Image") -> "_PILImage.Image":
    """
    Keep image within safe memory bounds and ensure the short edge is large
    enough for Tesseract's LSTM engine to recognise character strokes.
    """
    w, h = img.size

    # Downscale extreme resolutions (e.g. 50 MP RAW phone shots)
    if w * h > _MAX_OCR_PIXELS:
        scale = (_MAX_OCR_PIXELS / (w * h)) ** 0.5
        w, h = max(1, int(w * scale)), max(1, int(h * scale))
        img = img.resize((w, h), _PILImage.LANCZOS)

    # Upscale images that are too small (thumbnails, low-res captures)
    short = min(w, h)
    if short < _MIN_SHORT_EDGE:
        scale = _MIN_SHORT_EDGE / short
        img = img.resize((int(w * scale), int(h * scale)), _PILImage.LANCZOS)

    return img


def _adaptive_binarize(gray: "_PILImage.Image") -> "_PILImage.Image":
    """
    Adaptive local thresholding implemented with Pillow.

    Strategy: estimate the local background brightness by applying a heavy
    Gaussian blur, then subtract it from the original so that uneven
    illumination (shadows, phone-camera glare) is cancelled out.  The
    result is thresholded to produce a clean black-on-white binary image.

    This is equivalent to OpenCV's adaptiveThreshold(ADAPTIVE_THRESH_MEAN_C)
    but requires no extra dependencies.
    """
    # Estimated background (local average brightness)
    background = gray.filter(_PILImageFilter.GaussianBlur(radius=25))

    # Local contrast: pixel - local_mean, shifted to centre at 128
    w, h = gray.size
    src = gray.load()
    bg  = background.load()
    out = _PILImage.new("L", (w, h))
    dst = out.load()
    for y in range(h):
        for x in range(w):
            diff = int(src[x, y]) - int(bg[x, y]) + 128
            dst[x, y] = min(255, max(0, diff))

    # Threshold: pixels brighter than mid-grey → white (background),
    # darker → black (ink).  A small bias (−10) helps retain faint strokes.
    threshold = 128 - 10
    return out.point(lambda p: 255 if p > threshold else 0)


def _enhance(img: "_PILImage.Image") -> "_PILImage.Image":
    """
    Apply a preprocessing pipeline that substantially improves Tesseract
    accuracy on phone photos and low-quality scans.

    Pipeline
    --------
    1. Grayscale       – colour carries no information for OCR; removing it
                         reduces noise and simplifies subsequent steps.
    2. Auto-contrast   – stretches the histogram so that the darkest ink
                         becomes black and the brightest paper becomes white.
    3. Unsharp mask    – recovers edges softened by camera lens / JPEG
                         compression; makes character strokes crisper.
    4. Contrast boost  – increases the separation between ink and paper,
                         which helps Tesseract's binariser make cleaner cuts.
    5. Adaptive binarisation – removes uneven illumination (the #1 cause of
                         poor accuracy with phone photos).  Text and background
                         are separated locally rather than with a single global
                         threshold.
    """
    # 1. Grayscale
    gray = img.convert("L")

    # 2. Auto-contrast (clips darkest/lightest 1 % of pixels)
    gray = _PILImageOps.autocontrast(gray, cutoff=1)

    # 3. Unsharp mask – sharpen without amplifying noise
    gray = gray.filter(
        _PILImageFilter.UnsharpMask(radius=2, percent=120, threshold=3)
    )

    # 4. Contrast boost
    gray = _PILImageEnhance.Contrast(gray).enhance(1.8)

    # 5. Adaptive binarisation
    binary = _adaptive_binarize(gray)

    return binary


def _normalize_for_ocr(img: "_PILImage.Image") -> "_PILImage.Image":
    """
    Full normalisation pipeline for maximum Tesseract compatibility and
    accuracy across all image sources (phone camera, scanner, screenshot …).
    """
    # Step 1: bake EXIF rotation into pixels (phone cameras)
    try:
        img = _PILImageOps.exif_transpose(img)
    except Exception:
        pass

    # Step 2: convert to a mode Tesseract understands
    img = _to_rgb(img)

    # Step 3: safe size (downscale huge / upscale tiny)
    img = _resize_for_ocr(img)

    # Step 4: image enhancement (grayscale → contrast → sharpen → binarise)
    img = _enhance(img)

    return img


# --------------------------------------------------------------------------- #
#  OCR services
# --------------------------------------------------------------------------- #

class TesseractOCRService:
    """
    Offline OCR service using Tesseract via pytesseract. No network required.

    Broadly compatible with images from phone cameras, scanners, screenshots,
    web sources, and partially downloaded files.
    """

    def __init__(
        self,
        lang: str = "chi_sim+eng",
        tesseract_cmd: str | None = None,
    ) -> None:
        """
        Args:
            lang: Tesseract language string, e.g. "chi_sim+eng".
                  Install language packs:
                      sudo apt install tesseract-ocr-chi-sim
            tesseract_cmd: Path to tesseract binary (auto-detected if None).
        """
        self.lang = lang
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def extract_text(
        self,
        image_stream: BinaryIO,
        prompt: str | None = None,
        stream_info: "StreamInfo | None" = None,
        **kwargs: Any,
    ) -> OCRResult:
        """Extract text offline using Tesseract OCR."""
        if _tesseract_exc_info is not None:
            return OCRResult(
                text="",
                backend_used="tesseract",
                error=(
                    "pytesseract is not installed. "
                    "Run: pip install pytesseract  and  "
                    "sudo apt install tesseract-ocr tesseract-ocr-chi-sim"
                ),
            )

        try:
            image_stream.seek(0)
            img = _PILImage.open(image_stream)
            img.load()  # force full decode; respects LOAD_TRUNCATED_IMAGES

            img = _normalize_for_ocr(img)

            text = pytesseract.image_to_string(
                img,
                lang=self.lang,
                config=_TESS_CONFIG,
            )
            return OCRResult(
                text=text.strip(),
                backend_used="tesseract",
            )
        except Exception as e:
            return OCRResult(text="", backend_used="tesseract", error=str(e))
        finally:
            image_stream.seek(0)


class LLMVisionOCRService:
    """OCR service using LLM vision models (OpenAI-compatible)."""

    def __init__(
        self,
        client: Any,
        model: str,
        default_prompt: str | None = None,
    ) -> None:
        """
        Initialize LLM Vision OCR service.

        Args:
            client: OpenAI-compatible client
            model: Model name (e.g., 'gpt-4o', 'gemini-2.0-flash')
            default_prompt: Default prompt for OCR extraction
        """
        self.client = client
        self.model = model
        self.default_prompt = default_prompt or (
            "Extract all text from this image. "
            "Return ONLY the extracted text, maintaining the original "
            "layout and order. Do not add any commentary or description."
        )

    def extract_text(
        self,
        image_stream: BinaryIO,
        prompt: str | None = None,
        stream_info: StreamInfo | None = None,
        **kwargs: Any,
    ) -> OCRResult:
        """Extract text using LLM vision."""
        if self.client is None:
            return OCRResult(
                text="",
                backend_used="llm_vision",
                error="LLM client not configured",
            )

        try:
            image_stream.seek(0)

            content_type: str | None = None
            if stream_info:
                content_type = stream_info.mimetype

            if not content_type:
                try:
                    from PIL import Image

                    image_stream.seek(0)
                    img = Image.open(image_stream)
                    fmt = img.format.lower() if img.format else "png"
                    content_type = f"image/{fmt}"
                except Exception:
                    content_type = "image/png"

            image_stream.seek(0)
            base64_image = base64.b64encode(image_stream.read()).decode("utf-8")
            data_uri = f"data:{content_type};base64,{base64_image}"

            actual_prompt = prompt or self.default_prompt
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": actual_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": data_uri},
                            },
                        ],
                    }
                ],
            )

            text = response.choices[0].message.content
            return OCRResult(
                text=text.strip() if text else "",
                backend_used="llm_vision",
            )
        except Exception as e:
            return OCRResult(text="", backend_used="llm_vision", error=str(e))
        finally:
            image_stream.seek(0)
