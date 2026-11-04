"""
Standalone Image Parser for PNG, JPG, JPEG, and TIFF document files.
Uses BaseOCREngine for OCR text extraction and Pillow for image validation.
"""
import io
import time
from pathlib import Path
from typing import Optional, Union

from PIL import Image, UnidentifiedImageError

from .base import (
    BaseParser,
    DocumentExtractionResult,
    DocumentMetadata,
    ExtractionStatus,
    PageExtraction,
)
from .ocr_engine import BaseOCREngine, OCRResult


class ImageParser(BaseParser):
    """
    Parser for standalone image files (PNG, JPG, JPEG, TIFF).
    Validates image integrity and extracts text via injected BaseOCREngine.
    """

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif"}

    def __init__(
        self,
        ocr_engine: Optional[BaseOCREngine] = None,
        min_words_threshold: int = 3,
    ):
        self._ocr_engine = ocr_engine
        self.min_words_threshold = min_words_threshold

    @property
    def ocr_engine(self) -> BaseOCREngine:
        """Lazy initialization of default EasyOCREngine if not injected."""
        if self._ocr_engine is None:
            from .ocr_engine import EasyOCREngine
            self._ocr_engine = EasyOCREngine()
        return self._ocr_engine

    def parse(
        self,
        file_input: Union[str, Path, bytes],
        filename: Optional[str] = None
    ) -> DocumentExtractionResult:
        start_time = time.perf_counter()

        # Determine resolved filename and extension
        if filename:
            resolved_name = filename
        elif isinstance(file_input, (str, Path)):
            resolved_name = Path(file_input).name
        else:
            resolved_name = "image.png"

        ext = Path(resolved_name).suffix.lower()
        file_type = ext.lstrip(".") if ext else "png"

        # Enforce supported image file extensions
        if ext and ext not in self.SUPPORTED_EXTENSIONS:
            return DocumentExtractionResult(
                filename=resolved_name,
                file_type=file_type,
                status=ExtractionStatus.FAILED,
                metadata=DocumentMetadata(),
                error_message=f"Unsupported image file extension '{ext}'. Supported extensions: {sorted(self.SUPPORTED_EXTENSIONS)}",
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Resolve input bytes or path
        image_bytes: Optional[bytes] = None
        file_size: int = 0

        if isinstance(file_input, (str, Path)):
            path_obj = Path(file_input)
            if not path_obj.exists():
                return DocumentExtractionResult(
                    filename=resolved_name,
                    file_type=file_type,
                    status=ExtractionStatus.FAILED,
                    metadata=DocumentMetadata(),
                    error_message=f"File not found: {path_obj}",
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
            try:
                file_size = path_obj.stat().st_size
                if file_size == 0:
                    return DocumentExtractionResult(
                        filename=resolved_name,
                        file_type=file_type,
                        status=ExtractionStatus.EMPTY,
                        metadata=DocumentMetadata(file_size_bytes=0),
                        error_message="Image file is 0 bytes (empty file)",
                        processing_time_ms=(time.perf_counter() - start_time) * 1000,
                    )
                with open(path_obj, "rb") as f:
                    image_bytes = f.read()
            except Exception as e:
                return DocumentExtractionResult(
                    filename=resolved_name,
                    file_type=file_type,
                    status=ExtractionStatus.FAILED,
                    metadata=DocumentMetadata(),
                    error_message=f"Unable to read file: {e}",
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
        elif isinstance(file_input, bytes):
            image_bytes = file_input
            file_size = len(image_bytes)
            if file_size == 0:
                return DocumentExtractionResult(
                    filename=resolved_name,
                    file_type=file_type,
                    status=ExtractionStatus.EMPTY,
                    metadata=DocumentMetadata(file_size_bytes=0),
                    error_message="Image byte stream is empty (0 bytes)",
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
        else:
            return DocumentExtractionResult(
                filename=resolved_name,
                file_type=file_type,
                status=ExtractionStatus.FAILED,
                metadata=DocumentMetadata(),
                error_message="Unsupported input format: must be filepath or bytes",
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Validate image format and integrity with Pillow
        try:
            pil_image = Image.open(io.BytesIO(image_bytes))
            pil_image.verify()  # Fast check for corruption
            # Reopen after verify since verify() closes file pointer
            pil_image = Image.open(io.BytesIO(image_bytes))
        except (UnidentifiedImageError, OSError) as e:
            return DocumentExtractionResult(
                filename=resolved_name,
                file_type=file_type,
                status=ExtractionStatus.CORRUPTED,
                metadata=DocumentMetadata(file_size_bytes=file_size),
                error_message=f"Corrupted or unsupported image format: {e}",
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        metadata = DocumentMetadata(
            page_count=1,
            file_size_bytes=file_size,
            is_encrypted=False,
        )

        # Execute OCR via injected BaseOCREngine
        ocr_warnings = []
        try:
            ocr_result: OCRResult = self.ocr_engine.extract_text(pil_image)
            text = ocr_result.text.strip()
            word_count = len(text.split())
            char_count = len(text)
            has_text = word_count >= self.min_words_threshold

            if has_text:
                status = ExtractionStatus.SUCCESS
            else:
                # Clarification: Short OCR text (< min_words_threshold) yields EMPTY.
                # In document OCR, image noise (scanning speckles, stray margin artifacts, or
                # non-text markings) commonly produces 1-2 spurious tokens. Treating sub-threshold
                # recognition as EMPTY prevents downstream ingestion components from indexing noise
                # as substantive document content, while preserving the raw text for auditability.
                status = ExtractionStatus.EMPTY
                if word_count == 0:
                    ocr_warnings.append("OCR completed across image, but no recognizable text was found.")
                else:
                    ocr_warnings.append(
                        f"OCR recognized {word_count} word(s) ('{text}'), which is below the substantive "
                        f"threshold of {self.min_words_threshold} words; document classified as EMPTY."
                    )

            page = PageExtraction(
                page_number=1,
                text=text,
                word_count=word_count,
                char_count=char_count,
                has_text=has_text,
                has_images=True,
                is_blank=False,
                needs_ocr=False,  # Resolved
                ocr_applied=True,
                ocr_confidence=ocr_result.confidence,
                tables=[],
            )

            return DocumentExtractionResult(
                filename=resolved_name,
                file_type=file_type,
                status=status,
                metadata=metadata,
                pages=[page],
                full_text=text,
                tables_extracted=0,
                ocr_warnings=ocr_warnings,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        except Exception as e:
            # OCR engine exception (e.g. OOM, inference crash)
            ocr_warnings.append(f"OCR engine exception: {e}")
            page = PageExtraction(
                page_number=1,
                text="",
                word_count=0,
                char_count=0,
                has_text=False,
                has_images=True,
                is_blank=False,
                needs_ocr=True,  # OCR could not resolve page
                ocr_applied=False,
                ocr_confidence=None,
                tables=[],
            )
            return DocumentExtractionResult(
                filename=resolved_name,
                file_type=file_type,
                status=ExtractionStatus.FAILED,
                metadata=metadata,
                pages=[page],
                full_text="",
                tables_extracted=0,
                error_message=f"OCR execution failed: {e}",
                ocr_warnings=ocr_warnings,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )
