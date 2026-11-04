"""
Unified Document Ingestion Service and Corrupted File Guard.
Provides a single, resilient entry point for ingesting all supported document types:
PDF, Images (PNG, JPG, TIFF), and Spreadsheets (XLSX, XLS, CSV).
Routes documents to specialized parsers using both extension and magic byte sniffing,
enforcing strict validation, empty guards, and corruption isolation.
"""
import io
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .base import (
    BaseParser,
    DocumentExtractionResult,
    DocumentMetadata,
    ExtractionStatus,
    PageExtraction,
)
from .image_parser import ImageParser
from .ocr_engine import BaseOCREngine
from .pdf_parser import PDFParser
from .spreadsheet_parser import SpreadsheetParser


class DocumentIngestionService:
    """
    Unified Ingestion Service routing documents to appropriate parser engines.
    Provides centralized:
    - Format detection (extension + magic signature sniffing)
    - Zero-byte and empty file guards
    - Centralized corrupted container handling
    - Unsupported file rejection
    - Injection of custom parser engines and OCR models
    """

    SUPPORTED_EXTENSIONS = {
        ".pdf": "pdf",
        ".png": "png",
        ".jpg": "jpg",
        ".jpeg": "jpg",
        ".tiff": "tiff",
        ".tif": "tiff",
        ".xlsx": "xlsx",
        ".xls": "xls",
        ".csv": "csv",
    }

    # Category mappings
    CATEGORY_PDF = "pdf"
    CATEGORY_IMAGE = "image"
    CATEGORY_SPREADSHEET = "spreadsheet"
    CATEGORY_UNSUPPORTED = "unsupported"

    FORMAT_TO_CATEGORY = {
        "pdf": CATEGORY_PDF,
        "png": CATEGORY_IMAGE,
        "jpg": CATEGORY_IMAGE,
        "jpeg": CATEGORY_IMAGE,
        "tiff": CATEGORY_IMAGE,
        "tif": CATEGORY_IMAGE,
        "xlsx": CATEGORY_SPREADSHEET,
        "xls": CATEGORY_SPREADSHEET,
        "csv": CATEGORY_SPREADSHEET,
    }

    def __init__(
        self,
        pdf_parser: Optional[PDFParser] = None,
        image_parser: Optional[ImageParser] = None,
        spreadsheet_parser: Optional[SpreadsheetParser] = None,
        ocr_engine: Optional[BaseOCREngine] = None,
        enable_ocr: bool = True,
    ):
        self.ocr_engine = ocr_engine
        self.enable_ocr = enable_ocr
        self._pdf_parser = pdf_parser
        self._image_parser = image_parser
        self._spreadsheet_parser = spreadsheet_parser

    @property
    def pdf_parser(self) -> PDFParser:
        """Lazy initialization of PDFParser if not injected."""
        if self._pdf_parser is None:
            self._pdf_parser = PDFParser(
                ocr_engine=self.ocr_engine,
                enable_ocr=self.enable_ocr
            )
        return self._pdf_parser

    @property
    def image_parser(self) -> ImageParser:
        """Lazy initialization of ImageParser if not injected."""
        if self._image_parser is None:
            self._image_parser = ImageParser(ocr_engine=self.ocr_engine)
        return self._image_parser

    @property
    def spreadsheet_parser(self) -> SpreadsheetParser:
        """Lazy initialization of SpreadsheetParser if not injected."""
        if self._spreadsheet_parser is None:
            self._spreadsheet_parser = SpreadsheetParser()
        return self._spreadsheet_parser

    def sniff_format(self, file_bytes: bytes, filename: Optional[str] = None) -> Tuple[str, str]:
        """
        Determines the normalized file type and high-level category using
        both filename extension and magic bytes inspection.
        Returns: (file_type, category)
        """
        ext = Path(filename).suffix.lower() if filename else ""

        # 1. Magic byte sniffing for binary signatures
        if b"%PDF-" in file_bytes[:1024]:
            return "pdf", self.CATEGORY_PDF

        if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png", self.CATEGORY_IMAGE

        if file_bytes.startswith(b"\xff\xd8\xff"):
            return "jpg", self.CATEGORY_IMAGE

        if file_bytes.startswith(b"II*\x00") or file_bytes.startswith(b"MM\x00*"):
            return "tiff", self.CATEGORY_IMAGE

        if file_bytes.startswith(b"PK\x03\x04"):
            # Zip container: check if it's an OpenXML Excel file
            if ext == ".xlsx" or b"xl/" in file_bytes[:2048] or b"[Content_Types].xml" in file_bytes[:2048]:
                return "xlsx", self.CATEGORY_SPREADSHEET

        if file_bytes.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            # OLE2 Compound Document: Excel 97-2003
            return "xls", self.CATEGORY_SPREADSHEET

        # 2. Extension-based fallback if extension is recognized
        if ext in self.SUPPORTED_EXTENSIONS:
            fmt = self.SUPPORTED_EXTENSIONS[ext]
            return fmt, self.FORMAT_TO_CATEGORY[fmt]

        # 3. Text heuristic for CSV (delimiter detection without extension)
        if len(file_bytes) > 0 and len(file_bytes) < 10_000_000:
            try:
                sample = file_bytes[:4096].decode("utf-8")
                lines = sample.splitlines()
                if len(lines) >= 2 and any(d in lines[0] for d in (",", "\t", ";")):
                    return "csv", self.CATEGORY_SPREADSHEET
            except (UnicodeDecodeError, Exception):
                pass

        return "unsupported", self.CATEGORY_UNSUPPORTED

    def ingest(
        self,
        file_input: Union[str, Path, bytes],
        filename: Optional[str] = None
    ) -> DocumentExtractionResult:
        """
        Ingest a document from file path or in-memory byte stream.
        Routes to the appropriate parser with full exception isolation and error reporting.
        """
        start_time = time.perf_counter()

        # Resolve path or bytes input
        file_bytes: Optional[bytes] = None
        file_size: int = 0
        resolved_name: str = filename or "document"

        if isinstance(file_input, (str, Path)):
            path_obj = Path(file_input)
            if not filename:
                resolved_name = path_obj.name
            if not path_obj.exists():
                return DocumentExtractionResult(
                    filename=resolved_name,
                    file_type="unknown",
                    status=ExtractionStatus.FAILED,
                    metadata=DocumentMetadata(),
                    error_message=f"File not found: {path_obj}",
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
            try:
                file_size = path_obj.stat().st_size
                if file_size == 0:
                    ext = path_obj.suffix.lower().lstrip(".")
                    return DocumentExtractionResult(
                        filename=resolved_name,
                        file_type=ext or "unknown",
                        status=ExtractionStatus.EMPTY,
                        metadata=DocumentMetadata(file_size_bytes=0),
                        error_message="Document is empty (0 bytes)",
                        processing_time_ms=(time.perf_counter() - start_time) * 1000,
                    )
                with open(path_obj, "rb") as f:
                    file_bytes = f.read()
            except Exception as e:
                return DocumentExtractionResult(
                    filename=resolved_name,
                    file_type="unknown",
                    status=ExtractionStatus.FAILED,
                    metadata=DocumentMetadata(),
                    error_message=f"Unable to read file: {e}",
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
        elif isinstance(file_input, bytes):
            file_bytes = file_input
            file_size = len(file_bytes)
            if file_size == 0:
                ext = Path(resolved_name).suffix.lower().lstrip(".")
                return DocumentExtractionResult(
                    filename=resolved_name,
                    file_type=ext or "unknown",
                    status=ExtractionStatus.EMPTY,
                    metadata=DocumentMetadata(file_size_bytes=0),
                    error_message="Document byte stream is empty (0 bytes)",
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
        else:
            return DocumentExtractionResult(
                filename=resolved_name,
                file_type="unknown",
                status=ExtractionStatus.FAILED,
                metadata=DocumentMetadata(),
                error_message="Unsupported input type: must be file path (str, Path) or raw bytes",
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Sniff format and category
        file_type, category = self.sniff_format(file_bytes, resolved_name)

        # Guard: Unsupported format
        if category == self.CATEGORY_UNSUPPORTED:
            ext = Path(resolved_name).suffix.lower()
            supported_list = sorted(list(self.SUPPORTED_EXTENSIONS.keys()))
            return DocumentExtractionResult(
                filename=resolved_name,
                file_type=ext.lstrip(".") if ext else "unknown",
                status=ExtractionStatus.FAILED,
                metadata=DocumentMetadata(file_size_bytes=file_size),
                error_message=(
                    f"Unsupported document format '{ext or file_type}'. "
                    f"Supported formats: {', '.join(supported_list)}"
                ),
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Route to appropriate parser engine
        if category == self.CATEGORY_PDF:
            parser: BaseParser = self.pdf_parser
        elif category == self.CATEGORY_IMAGE:
            parser = self.image_parser
        elif category == self.CATEGORY_SPREADSHEET:
            parser = self.spreadsheet_parser
        else:
            # Fallback guard
            return DocumentExtractionResult(
                filename=resolved_name,
                file_type=file_type,
                status=ExtractionStatus.FAILED,
                metadata=DocumentMetadata(file_size_bytes=file_size),
                error_message=f"No suitable parser found for category '{category}'",
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Prepare normalized filename for sub-parser if generic/mismatched extension was provided
        ext = Path(resolved_name).suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS or ext == "":
            parser_filename = f"{Path(resolved_name).stem}.{file_type}"
        else:
            parser_filename = resolved_name

        # Execute parsing with full error isolation
        try:
            result = parser.parse(file_bytes, filename=parser_filename)
            # Restore caller's original filename and verified file_type
            result.filename = resolved_name
            result.file_type = file_type
            # Ensure metadata captures byte size if not set
            if result.metadata and result.metadata.file_size_bytes == 0:
                result.metadata.file_size_bytes = file_size
            return result
        except Exception as e:
            return DocumentExtractionResult(
                filename=resolved_name,
                file_type=file_type,
                status=ExtractionStatus.FAILED,
                metadata=DocumentMetadata(file_size_bytes=file_size),
                error_message=f"Unhandled parser exception during ingestion: {e}",
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )
