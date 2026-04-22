"""
OCR Service Layer for MarkItDown
Provides LLM Vision-based and offline Tesseract-based image text extraction.
"""

import base64
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
    from PIL import Image as _PILImage
except ImportError:
    _tesseract_exc_info = sys.exc_info()


class TesseractOCRService:
    """Offline OCR service using Tesseract via pytesseract. No network required."""

    def __init__(
        self,
        lang: str = "chi_sim+eng",
        tesseract_cmd: str | None = None,
    ) -> None:
        """
        Args:
            lang: Tesseract language string, e.g. "chi_sim+eng" for Simplified Chinese + English.
                  Install language packs: sudo apt install tesseract-ocr-chi-sim
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
                    "Run: pip install pytesseract  and  sudo apt install tesseract-ocr tesseract-ocr-chi-sim"
                ),
            )

        try:
            image_stream.seek(0)
            img = _PILImage.open(image_stream)
            text = pytesseract.image_to_string(img, lang=self.lang)
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
