"""
Plugin registration for markitdown-ocr.
Registers OCR-enhanced converters with priority-based replacement strategy.
"""

from typing import Any, Union
from markitdown import MarkItDown

from ._ocr_service import LLMVisionOCRService, TesseractOCRService
from ._pdf_converter_with_ocr import PdfConverterWithOCR
from ._docx_converter_with_ocr import DocxConverterWithOCR
from ._pptx_converter_with_ocr import PptxConverterWithOCR
from ._xlsx_converter_with_ocr import XlsxConverterWithOCR
from ._image_converter_with_ocr import ImageConverterWithOCR


__plugin_interface_version__ = 1

OCRService = Union[TesseractOCRService, LLMVisionOCRService]


def register_converters(markitdown: MarkItDown, **kwargs: Any) -> None:
    """
    Register OCR-enhanced converters with MarkItDown.

    Supports offline (Tesseract) and online (LLM Vision) OCR backends.
    Backend selection is controlled by the ``ocr_backend`` kwarg.

    Args:
        markitdown: MarkItDown instance to register converters with
        **kwargs: Additional keyword arguments:
            ocr_backend (str): "tesseract" (default, offline) | "llm" | "auto"
                - "tesseract": use Tesseract for all OCR (no internet needed)
                - "llm": use LLM Vision (requires llm_client + llm_model)
                - "auto": prefer Tesseract; fall back to LLM if not available
            tesseract_lang (str): Tesseract language string, default "chi_sim+eng"
            tesseract_cmd (str): Path to tesseract binary (auto-detected if omitted)
            llm_client: OpenAI-compatible client (required when ocr_backend="llm")
            llm_model (str): Model name, e.g. "gpt-4o"
            llm_prompt (str): Custom prompt for LLM text extraction
    """
    ocr_backend: str = kwargs.get("ocr_backend", "tesseract")

    llm_client = kwargs.get("llm_client")
    llm_model = kwargs.get("llm_model")
    llm_prompt = kwargs.get("llm_prompt")
    tesseract_lang: str = kwargs.get("tesseract_lang", "chi_sim+eng")
    tesseract_cmd: str | None = kwargs.get("tesseract_cmd")

    ocr_service: OCRService | None = None

    if ocr_backend in ("tesseract", "auto"):
        ocr_service = TesseractOCRService(
            lang=tesseract_lang,
            tesseract_cmd=tesseract_cmd,
        )
    elif ocr_backend == "llm":
        if llm_client and llm_model:
            ocr_service = LLMVisionOCRService(
                client=llm_client,
                model=llm_model,
                default_prompt=llm_prompt,
            )
    else:
        raise ValueError(
            f"Unknown ocr_backend={ocr_backend!r}. Choose 'tesseract', 'llm', or 'auto'."
        )

    # Register converters with priority -1.0 (before built-ins at 0.0)
    PRIORITY_OCR_ENHANCED = -1.0

    markitdown.register_converter(
        ImageConverterWithOCR(ocr_service=ocr_service), priority=PRIORITY_OCR_ENHANCED
    )

    markitdown.register_converter(
        PdfConverterWithOCR(ocr_service=ocr_service), priority=PRIORITY_OCR_ENHANCED
    )

    markitdown.register_converter(
        DocxConverterWithOCR(ocr_service=ocr_service), priority=PRIORITY_OCR_ENHANCED
    )

    markitdown.register_converter(
        PptxConverterWithOCR(ocr_service=ocr_service), priority=PRIORITY_OCR_ENHANCED
    )

    markitdown.register_converter(
        XlsxConverterWithOCR(ocr_service=ocr_service), priority=PRIORITY_OCR_ENHANCED
    )
