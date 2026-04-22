"""
Image Converter with OCR support for MarkItDown.
Handles PNG/JPG images using offline (Tesseract) or LLM Vision OCR backends.
"""

from typing import Any, BinaryIO, Union

from markitdown import DocumentConverter, DocumentConverterResult, StreamInfo

from ._ocr_service import LLMVisionOCRService, TesseractOCRService

ACCEPTED_MIME_TYPE_PREFIXES = [
    "image/jpeg",
    "image/png",
]

ACCEPTED_FILE_EXTENSIONS = [".jpg", ".jpeg", ".png"]

OCRService = Union[TesseractOCRService, LLMVisionOCRService]


class ImageConverterWithOCR(DocumentConverter):
    """
    Converts PNG/JPG images to markdown using OCR.

    Supports two backends:
    - TesseractOCRService: fully offline, no API key required
    - LLMVisionOCRService: uses an OpenAI-compatible vision model
    """

    def __init__(self, ocr_service: OCRService | None = None) -> None:
        super().__init__()
        self.ocr_service = ocr_service

    def accepts(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> bool:
        mimetype = (stream_info.mimetype or "").lower()
        extension = (stream_info.extension or "").lower()

        if extension in ACCEPTED_FILE_EXTENSIONS:
            return True

        for prefix in ACCEPTED_MIME_TYPE_PREFIXES:
            if mimetype.startswith(prefix):
                return True

        return False

    def convert(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> DocumentConverterResult:
        ocr_service: OCRService | None = kwargs.get("ocr_service") or self.ocr_service

        if ocr_service is None:
            return DocumentConverterResult(markdown="")

        result = ocr_service.extract_text(
            file_stream,
            stream_info=stream_info,
        )

        if result.error:
            return DocumentConverterResult(
                markdown=f"*[OCR Error ({result.backend_used}): {result.error}]*"
            )

        return DocumentConverterResult(markdown=result.text)
