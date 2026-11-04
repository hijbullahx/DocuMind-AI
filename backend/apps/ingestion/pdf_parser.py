"""
Digital PDF Text and Table Extractor.
Uses PyMuPDF (pymupdf) for fast vector text and layout parsing,
and pdfplumber for high-precision table cell extraction.
"""
import io
import time
from pathlib import Path
from typing import List, Optional, Union

import pymupdf as fitz  # PyMuPDF
import pdfplumber

from .base import (
    BaseParser,
    DocumentExtractionResult,
    DocumentMetadata,
    ExtractionStatus,
    PageExtraction,
)


class PDFParser(BaseParser):
    """
    Modular digital PDF extraction engine.
    Extracts text, metadata, pagination, and tables from single and multi-page PDFs.
    Distinguishes clean digital text, scanned/image-based pages requiring OCR, blank pages, and corrupted files.
    """

    def __init__(self, min_words_per_page_threshold: int = 5, extract_tables: bool = True):
        self.min_words_per_page_threshold = min_words_per_page_threshold
        self.extract_tables = extract_tables

    def parse(
        self,
        file_input: Union[str, Path, bytes],
        filename: Optional[str] = None
    ) -> DocumentExtractionResult:
        start_time = time.perf_counter()
        resolved_name = filename or "document.pdf"

        # Resolve file path or bytes
        file_bytes: Optional[bytes] = None
        file_path_str: Optional[str] = None
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
                file_path_str = str(path_obj)
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
            full_text_parts: List[str] = []

            for idx in range(page_count):
                page = doc.load_page(idx)
                raw_page_text = page.get_text("text").strip()
                words = raw_page_text.split()
                word_count = len(words)
                char_count = len(raw_page_text)

                # Inspect image objects on page
                images_list = page.get_images()
                has_images = len(images_list) > 0
                has_text = word_count >= self.min_words_per_page_threshold

                # Per-page categorization
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
                        tables=page_tables,
                    )
                )

                if raw_page_text:
                    full_text_parts.append(raw_page_text)

            full_text = "\n\n--- Page Break ---\n\n".join(full_text_parts)

            # Robust document-level status determination
            text_page_count = sum(1 for p in pages_extraction if p.has_text)
            ocr_needed_count = sum(1 for p in pages_extraction if p.needs_ocr)
            blank_page_count = sum(1 for p in pages_extraction if p.is_blank)
            sparse_page_count = sum(
                1 for p in pages_extraction
                if not p.has_text and not p.needs_ocr and not p.is_blank
            )

            if blank_page_count == page_count:
                # 1. All pages are completely blank
                status = ExtractionStatus.EMPTY
            elif ocr_needed_count == page_count:
                # 2. All pages are image-only pages requiring OCR
                status = ExtractionStatus.NEEDS_OCR
            elif ocr_needed_count > 0:
                # 3. There is at least one page requiring OCR
                if text_page_count > 0:
                    # Mixed document: has both digital text pages and image-only scanned pages
                    status = ExtractionStatus.PARTIAL_SUCCESS
                else:
                    # Document has OCR-needed pages and blank pages, but zero digital text
                    status = ExtractionStatus.NEEDS_OCR
            elif text_page_count > 0:
                # 4. No pages require OCR; there is at least one digital text page
                if sparse_page_count == 0:
                    # Every non-blank page has adequate digital text (digital + blank is SUCCESS)
                    status = ExtractionStatus.SUCCESS
                else:
                    # Some non-blank pages have insufficient text (< threshold) without images
                    status = ExtractionStatus.PARTIAL_SUCCESS
            elif sparse_page_count > 0:
                # 5. Document has sparse text (1-4 words) with no images and no full text pages
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
