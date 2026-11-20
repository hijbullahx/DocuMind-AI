"""
Digital PDF Text and Table Extractor with Optional Modular OCR Integration.
Uses PyMuPDF (pymupdf) for fast vector text and layout parsing,
pdfplumber for high-precision table cell extraction,
and pluggable BaseOCREngine for scanned/image-based pages.
"""
import io
import time
from pathlib import Path
from typing import List, Optional, Union

from PIL import Image
try:
    import pymupdf as fitz  # PyMuPDF
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


from .base import (
    BaseParser,
    DocumentExtractionResult,
    DocumentMetadata,
    ExtractionStatus,
    PageExtraction,
)
from .ocr_engine import BaseOCREngine, OCRResult


class PDFParser(BaseParser):
    """
    Modular digital PDF extraction engine with selective OCR fallback.
    Extracts text, metadata, pagination, and tables from single and multi-page PDFs.
    Routes only image-only scanned pages to BaseOCREngine; blank pages never trigger OCR.
    """

    def __init__(
        self,
        min_words_per_page_threshold: int = 5,
        extract_tables: bool = True,
        ocr_engine: Optional[BaseOCREngine] = None,
        enable_ocr: bool = False,
    ):
        self.min_words_per_page_threshold = min_words_per_page_threshold
        self.extract_tables = extract_tables
        self._ocr_engine = ocr_engine
        # OCR is active if explicitly enabled or if an ocr_engine is provided
        self.enable_ocr = enable_ocr or (ocr_engine is not None)

    @property
    def ocr_engine(self) -> BaseOCREngine:
        """Lazy initialization of EasyOCREngine if not injected."""
        if self._ocr_engine is None:
            from .ocr_engine import EasyOCREngine
            self._ocr_engine = EasyOCREngine()
        return self._ocr_engine

    def _render_page_to_image(self, page: fitz.Page, dpi: int = 200) -> Image.Image:
        """Renders an individual PDF page to a PIL Image for OCR using PyMuPDF."""
        pix = page.get_pixmap(dpi=dpi)
        img_bytes = pix.tobytes("png")
        return Image.open(io.BytesIO(img_bytes))

    def parse(
        self,
        file_input: Union[str, Path, bytes],
        filename: Optional[str] = None
    ) -> DocumentExtractionResult:
        start_time = time.perf_counter()
        resolved_name = filename or "document.pdf"

        # Resolve file path or bytes
        file_bytes: Optional[bytes] = None
        file_size: int = 0

        if isinstance(file_input, (str, Path)):
            path_obj = Path(file_input)
            if not resolved_name or resolved_name == "document.pdf":
                resolved_name = path_obj.name
            if not path_obj.exists():
                return DocumentExtractionResult(
                    filename=resolved_name,
                    file_type="pdf",
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
                        file_type="pdf",
                        status=ExtractionStatus.EMPTY,
                        metadata=DocumentMetadata(file_size_bytes=0),
                        error_message="PDF file is 0 bytes (empty file)",
                        processing_time_ms=(time.perf_counter() - start_time) * 1000,
                    )
                with open(path_obj, "rb") as f:
                    file_bytes = f.read()
            except Exception as e:
                return DocumentExtractionResult(
                    filename=resolved_name,
                    file_type="pdf",
                    status=ExtractionStatus.FAILED,
                    metadata=DocumentMetadata(),
                    error_message=f"Unable to read file: {e}",
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
        elif isinstance(file_input, bytes):
            file_bytes = file_input
            file_size = len(file_bytes)
            if file_size == 0:
                return DocumentExtractionResult(
                    filename=resolved_name,
                    file_type="pdf",
                    status=ExtractionStatus.EMPTY,
                    metadata=DocumentMetadata(file_size_bytes=0),
                    error_message="PDF byte stream is empty (0 bytes)",
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
        else:
            return DocumentExtractionResult(
                filename=resolved_name,
                file_type="pdf",
                status=ExtractionStatus.FAILED,
                metadata=DocumentMetadata(),
                error_message="Unsupported input format: must be filepath or bytes",
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Open and inspect document with PyMuPDF
        doc: Optional[fitz.Document] = None
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as e:
            return DocumentExtractionResult(
                filename=resolved_name,
                file_type="pdf",
                status=ExtractionStatus.CORRUPTED,
                metadata=DocumentMetadata(file_size_bytes=file_size),
                error_message=f"Corrupted or invalid PDF format: {e}",
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        try:
            if doc.is_encrypted:
                return DocumentExtractionResult(
                    filename=resolved_name,
                    file_type="pdf",
                    status=ExtractionStatus.FAILED,
                    metadata=DocumentMetadata(
                        page_count=len(doc),
                        file_size_bytes=file_size,
                        is_encrypted=True,
                    ),
                    error_message="PDF is password encrypted and cannot be parsed without credentials",
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )

            page_count = len(doc)
            if page_count == 0:
                return DocumentExtractionResult(
                    filename=resolved_name,
                    file_type="pdf",
                    status=ExtractionStatus.EMPTY,
                    metadata=DocumentMetadata(file_size_bytes=file_size),
                    error_message="PDF container contains 0 pages",
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )

            # Metadata extraction
            doc_meta = doc.metadata or {}
            metadata = DocumentMetadata(
                page_count=page_count,
                title=doc_meta.get("title") or None,
                author=doc_meta.get("author") or None,
                creator=doc_meta.get("creator") or None,
                producer=doc_meta.get("producer") or None,
                creation_date=doc_meta.get("creationDate") or None,
                modification_date=doc_meta.get("modDate") or None,
                file_size_bytes=file_size,
                is_encrypted=False,
            )

            # Extract tables using pdfplumber if enabled
            tables_by_page: List[List[List[List[Optional[str]]]]] = [[] for _ in range(page_count)]
            total_tables = 0
            table_warning: Optional[str] = None

            if self.extract_tables:
                try:
                    with pdfplumber.open(io.BytesIO(file_bytes)) as plumber_pdf:
                        for page_idx, plumber_page in enumerate(plumber_pdf.pages):
                            if page_idx < page_count:
                                page_tables = plumber_page.extract_tables() or []
                                tables_by_page[page_idx] = page_tables
                                total_tables += len(page_tables)
                except Exception as e:
                    # Non-fatal diagnostic warning; text extraction proceeds
                    table_warning = f"Table extraction non-fatal warning: {e}"

            pages_extraction: List[PageExtraction] = []
            ocr_warnings: List[str] = []

            # 1. First Pass: Vector text extraction and page classification
            for idx in range(page_count):
                page = doc.load_page(idx)
                raw_page_text = page.get_text("text").strip()
                words = raw_page_text.split()
                word_count = len(words)
                char_count = len(raw_page_text)

                images_list = page.get_images()
                has_images = len(images_list) > 0
                has_text = word_count >= self.min_words_per_page_threshold

                # Per-page classification
                is_blank = (word_count == 0 and char_count == 0 and not has_images)
                needs_ocr = (not has_text and has_images)

                page_tables = tables_by_page[idx] if idx < len(tables_by_page) else []

                pages_extraction.append(
                    PageExtraction(
                        page_number=idx + 1,
                        text=raw_page_text,
                        word_count=word_count,
                        char_count=char_count,
                        has_text=has_text,
                        has_images=has_images,
                        is_blank=is_blank,
                        needs_ocr=needs_ocr,
                        ocr_applied=False,
                        ocr_confidence=None,
                        tables=page_tables,
                    )
                )

            # 2. Second Pass: Selective OCR routing (only for needs_ocr pages if enable_ocr is True)
            if self.enable_ocr:
                for page_entry in pages_extraction:
                    # Blank pages and digital text pages NEVER trigger OCR
                    if page_entry.is_blank or page_entry.has_text or not page_entry.needs_ocr:
                        continue

                    try:
                        fitz_page = doc.load_page(page_entry.page_number - 1)
                        pil_img = self._render_page_to_image(fitz_page)
                        ocr_res = self.ocr_engine.extract_text(pil_img)
                        ocr_text = ocr_res.text.strip()
                        ocr_words = ocr_text.split()
                        ocr_word_count = len(ocr_words)

                        if ocr_word_count >= self.min_words_per_page_threshold:
                            # Outcome 1: OCR successfully extracted adequate text
                            page_entry.text = ocr_text
                            page_entry.word_count = ocr_word_count
                            page_entry.char_count = len(ocr_text)
                            page_entry.has_text = True
                            page_entry.needs_ocr = False  # Resolved
                            page_entry.ocr_applied = True
                            page_entry.ocr_confidence = ocr_res.confidence
                        else:
                            # Outcome 2: OCR completed, but no or sparse text found
                            page_entry.text = ocr_text
                            page_entry.word_count = ocr_word_count
                            page_entry.char_count = len(ocr_text)
                            page_entry.has_text = False
                            page_entry.needs_ocr = False  # OCR was completed
                            page_entry.ocr_applied = True
                            page_entry.ocr_confidence = ocr_res.confidence
                            ocr_warnings.append(
                                f"Page {page_entry.page_number}: OCR completed, but no adequate text was recognized."
                            )

                    except Exception as e:
                        # Outcome 3: OCR engine exception
                        page_entry.ocr_applied = False
                        page_entry.needs_ocr = True  # Remains unresolved
                        page_entry.ocr_confidence = None
                        ocr_warnings.append(f"Page {page_entry.page_number}: OCR engine exception: {e}")

            # Recompute consolidated document full text
            full_text_parts = [p.text for p in pages_extraction if p.text]
            full_text = "\n\n--- Page Break ---\n\n".join(full_text_parts)

            # 3. Post-OCR Final Document Status Recomputation
            if self.enable_ocr:
                final_text_pages = sum(1 for p in pages_extraction if p.has_text)
                final_blank_pages = sum(1 for p in pages_extraction if p.is_blank)
                final_ocr_exceptions = sum(1 for p in pages_extraction if p.needs_ocr and not p.ocr_applied)
                final_ocr_empty = sum(1 for p in pages_extraction if p.ocr_applied and not p.has_text)
                final_sparse_pages = sum(
                    1 for p in pages_extraction
                    if not p.has_text and not p.needs_ocr and not p.ocr_applied and not p.is_blank
                )

                if final_blank_pages == page_count:
                    # 1. Blank-only document
                    status = ExtractionStatus.EMPTY
                elif final_ocr_exceptions == page_count:
                    # 2. Fatal: OCR engine crashed on all pages
                    status = ExtractionStatus.FAILED
                elif final_text_pages == page_count:
                    # 3. All pages extracted successfully (all digital or all OCR recovered)
                    status = ExtractionStatus.SUCCESS
                elif final_text_pages > 0 and (final_text_pages + final_blank_pages == page_count):
                    # 4. Digital/OCR text + blank pages, zero OCR failures -> SUCCESS
                    status = ExtractionStatus.SUCCESS
                elif final_text_pages > 0 and (final_ocr_exceptions > 0 or final_ocr_empty > 0 or final_sparse_pages > 0):
                    # 5. Mixed document with some digital text, but OCR crashed or yielded empty on other pages
                    status = ExtractionStatus.PARTIAL_SUCCESS
                elif final_text_pages == 0 and final_ocr_empty > 0 and final_ocr_exceptions == 0:
                    # 6. Scanned pages where OCR completed cleanly but recognized zero text
                    status = ExtractionStatus.EMPTY
                elif final_text_pages == 0 and final_ocr_exceptions > 0:
                    # 7. OCR engine crashed on pages and 0 text pages
                    status = ExtractionStatus.FAILED
                else:
                    # 8. Sparse-only or empty content in OCR-enabled mode:
                    # When OCR is enabled, the ingestion pipeline is definitive. A document with zero substantive
                    # text pages (final_text_pages == 0) and zero OCR errors contains only non-substantive noise
                    # or watermarks (e.g. < 5 words) and zero actionable text, deterministically yielding EMPTY.
                    # Conversely, if at least one substantive text page exists (final_text_pages > 0), any
                    # accompanying sparse pages correctly downgrade the document to PARTIAL_SUCCESS.
                    status = ExtractionStatus.PARTIAL_SUCCESS if final_text_pages > 0 else ExtractionStatus.EMPTY
            else:
                # Digital-only mode (enable_ocr=False): preserves TASK-002 exact state determination
                text_page_count = sum(1 for p in pages_extraction if p.has_text)
                ocr_needed_count = sum(1 for p in pages_extraction if p.needs_ocr)
                blank_page_count = sum(1 for p in pages_extraction if p.is_blank)
                sparse_page_count = sum(
                    1 for p in pages_extraction
                    if not p.has_text and not p.needs_ocr and not p.is_blank
                )

                if blank_page_count == page_count:
                    status = ExtractionStatus.EMPTY
                elif ocr_needed_count == page_count:
                    status = ExtractionStatus.NEEDS_OCR
                elif ocr_needed_count > 0:
                    if text_page_count > 0:
                        status = ExtractionStatus.PARTIAL_SUCCESS
                    else:
                        status = ExtractionStatus.NEEDS_OCR
                elif text_page_count > 0:
                    if sparse_page_count == 0:
                        status = ExtractionStatus.SUCCESS
                    else:
                        status = ExtractionStatus.PARTIAL_SUCCESS
                elif sparse_page_count > 0:
                    # In digital-only mode (enable_ocr=False), sparse text is classified as PARTIAL_SUCCESS
                    # to signal to downstream callers that digital characters were extracted from the vector
                    # stream (document is not physically blank), but full OCR resolution was not performed.
                    status = ExtractionStatus.PARTIAL_SUCCESS
                else:
                    status = ExtractionStatus.EMPTY

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            return DocumentExtractionResult(
                filename=resolved_name,
                file_type="pdf",
                status=status,
                metadata=metadata,
                pages=pages_extraction,
                full_text=full_text,
                tables_extracted=total_tables,
                table_extraction_warning=table_warning,
                ocr_warnings=ocr_warnings,
                processing_time_ms=elapsed_ms,
            )

        except Exception as e:
            return DocumentExtractionResult(
                filename=resolved_name,
                file_type="pdf",
                status=ExtractionStatus.CORRUPTED,
                metadata=DocumentMetadata(file_size_bytes=file_size),
                error_message=f"Error while processing PDF pages: {e}",
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )
        finally:
            if doc:
                doc.close()
