"""
Modular Spreadsheet & CSV Ingestion Parser.
Converts multi-sheet XLSX, XLS, and CSV files into structured tabular grids
(PageExtraction.tables) and unified text representations (PageExtraction.text).
Adheres strictly to the BaseParser, PageExtraction, and DocumentExtractionResult contracts.
"""
import csv
import io
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .base import (
    BaseParser,
    DocumentExtractionResult,
    DocumentMetadata,
    ExtractionStatus,
    PageExtraction,
)


class SpreadsheetParser(BaseParser):
    """
    Parser for structured spreadsheets (.xlsx, .xls) and delimited text (.csv).
    - Multi-sheet Excel files map each worksheet to a 1-indexed PageExtraction.
    - CSV files map to a single PageExtraction.
    - Each sheet extracts 3D table grids and renders clean Markdown tabular text.
    - Fully handles empty sheets, sparse data, zero-byte files, and corrupted files.
    """

    SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv"}

    def __init__(self, min_words_threshold: int = 1):
        self.min_words_threshold = min_words_threshold

    def _render_table_to_markdown(self, sheet_name: str, table_rows: List[List[Optional[str]]]) -> str:
        """
        Renders a 2D table grid into a readable Markdown table format.
        Preserves headers and column alignments for downstream LLM & FTS ingestion.
        """
        if not table_rows:
            return ""

        # Filter out trailing completely empty rows
        clean_rows = []
        for r in table_rows:
            # Check if row has any non-empty cell
            if any(c is not None and str(c).strip() != "" for c in r):
                clean_rows.append([str(c).strip() if c is not None else "" for c in r])

        if not clean_rows:
            return ""

        # Find max columns
        max_cols = max(len(r) for r in clean_rows)
        # Pad all rows to max_cols
        padded_rows = [r + [""] * (max_cols - len(r)) for r in clean_rows]

        lines = [f"### Sheet: {sheet_name}", ""]

        # First row as header
        header = padded_rows[0]
        header_line = "| " + " | ".join(h if h else f"Col_{i+1}" for i, h in enumerate(header)) + " |"
        sep_line = "| " + " | ".join("---" for _ in range(max_cols)) + " |"
        lines.append(header_line)
        lines.append(sep_line)

        # Remaining rows
        for row in padded_rows[1:]:
            row_line = "| " + " | ".join(cell for cell in row) + " |"
            lines.append(row_line)

        return "\n".join(lines)

    def _parse_csv(self, file_bytes: bytes, resolved_name: str, file_size: int, start_time: float) -> DocumentExtractionResult:
        """Parses CSV files with encoding detection and delimiter sniffing."""
        # Try UTF-8 first, fallback to latin-1 / cp1252
        text_content: Optional[str] = None
        for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                text_content = file_bytes.decode(enc)
                break
            except (UnicodeDecodeError, Exception):
                continue

        if text_content is None:
            return DocumentExtractionResult(
                filename=resolved_name,
                file_type="csv",
                status=ExtractionStatus.CORRUPTED,
                metadata=DocumentMetadata(file_size_bytes=file_size),
                error_message="Unable to decode CSV file: unsupported character encoding.",
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Read rows using csv reader
        string_io = io.StringIO(text_content)
        try:
            # Sniff delimiter among standard delimiters, default to comma
            sample = text_content[:2048]
            delimiter = ","
            if sample.strip():
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
                    delimiter = dialect.delimiter
                except Exception:
                    delimiter = ","

            reader = csv.reader(string_io, delimiter=delimiter)
            raw_rows: List[List[Optional[str]]] = [row for row in reader]
        except Exception as e:
            return DocumentExtractionResult(
                filename=resolved_name,
                file_type="csv",
                status=ExtractionStatus.CORRUPTED,
                metadata=DocumentMetadata(file_size_bytes=file_size),
                error_message=f"Corrupted or malformed CSV content: {e}",
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Filter empty rows
        non_empty_rows = [r for r in raw_rows if any(cell.strip() != "" for cell in r)]

        if not non_empty_rows:
            page = PageExtraction(
                page_number=1,
                text="",
                word_count=0,
                char_count=0,
                has_text=False,
                has_images=False,
                is_blank=True,
                needs_ocr=False,
                ocr_applied=False,
                ocr_confidence=None,
                tables=[],
            )
            return DocumentExtractionResult(
                filename=resolved_name,
                file_type="csv",
                status=ExtractionStatus.EMPTY,
                metadata=DocumentMetadata(page_count=1, file_size_bytes=file_size, title="Sheet: Sheet1"),
                pages=[page],
                full_text="",
                tables_extracted=0,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        rendered_text = self._render_table_to_markdown("Sheet1", non_empty_rows)
        words = rendered_text.split()
        word_count = len(words)
        char_count = len(rendered_text)
        has_text = word_count >= self.min_words_threshold

        page = PageExtraction(
            page_number=1,
            text=rendered_text,
            word_count=word_count,
            char_count=char_count,
            has_text=has_text,
            has_images=False,
            is_blank=False,
            needs_ocr=False,
            ocr_applied=False,
            ocr_confidence=None,
            tables=[non_empty_rows],
        )

        return DocumentExtractionResult(
            filename=resolved_name,
            file_type="csv",
            status=ExtractionStatus.SUCCESS if has_text else ExtractionStatus.EMPTY,
            metadata=DocumentMetadata(page_count=1, file_size_bytes=file_size, title="Sheet: Sheet1"),
            pages=[page],
            full_text=rendered_text,
            tables_extracted=1,
            processing_time_ms=(time.perf_counter() - start_time) * 1000,
        )

    def _parse_xlsx(self, file_bytes: bytes, resolved_name: str, file_size: int, start_time: float) -> DocumentExtractionResult:
        """Parses modern XLSX workbooks using openpyxl."""
        import zipfile
        from openpyxl import load_workbook
        from openpyxl.utils.exceptions import InvalidFileException

        try:
            wb = load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
            sheet_names = wb.sheetnames
        except (zipfile.BadZipFile, InvalidFileException, OSError, Exception) as e:
            return DocumentExtractionResult(
                filename=resolved_name,
                file_type="xlsx",
                status=ExtractionStatus.CORRUPTED,
                metadata=DocumentMetadata(file_size_bytes=file_size),
                error_message=f"Corrupted or invalid XLSX workbook: {e}",
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        pages: List[PageExtraction] = []
        total_tables = 0
        all_sheet_texts: List[str] = []

        for idx, sname in enumerate(sheet_names, start=1):
            sheet = wb[sname]
            raw_rows: List[List[Optional[str]]] = []

            for row in sheet.iter_rows(values_only=True):
                # Convert cell values to string or None
                row_vals = [str(c).strip() if c is not None else "" for c in row]
                raw_rows.append(row_vals)

            # Filter out trailing/entirely empty rows
            non_empty_rows = [r for r in raw_rows if any(c != "" for c in r)]

            if not non_empty_rows:
                pages.append(PageExtraction(
                    page_number=idx,
                    text="",
                    word_count=0,
                    char_count=0,
                    has_text=False,
                    has_images=False,
                    is_blank=True,
                    needs_ocr=False,
                    ocr_applied=False,
                    ocr_confidence=None,
                    tables=[],
                ))
            else:
                md_text = self._render_table_to_markdown(sname, non_empty_rows)
                words = md_text.split()
                w_count = len(words)
                c_count = len(md_text)
                h_text = w_count >= self.min_words_threshold

                pages.append(PageExtraction(
                    page_number=idx,
                    text=md_text,
                    word_count=w_count,
                    char_count=c_count,
                    has_text=h_text,
                    has_images=False,
                    is_blank=False,
                    needs_ocr=False,
                    ocr_applied=False,
                    ocr_confidence=None,
                    tables=[non_empty_rows],
                ))
                total_tables += 1
                if md_text:
                    all_sheet_texts.append(md_text)

        wb.close()

        # Recompute overall workbook status
        page_count = len(pages)
        blank_pages = sum(1 for p in pages if p.is_blank)
        text_pages = sum(1 for p in pages if p.has_text)

        if page_count == 0 or blank_pages == page_count:
            status = ExtractionStatus.EMPTY
        elif text_pages > 0:
            status = ExtractionStatus.SUCCESS
        else:
            status = ExtractionStatus.EMPTY

        full_text = "\n\n--- Page Break ---\n\n".join(all_sheet_texts)

        return DocumentExtractionResult(
            filename=resolved_name,
            file_type="xlsx",
            status=status,
            metadata=DocumentMetadata(
                page_count=page_count,
                file_size_bytes=file_size,
                title=f"Sheets: {', '.join(sheet_names)}",
            ),
            pages=pages,
            full_text=full_text,
            tables_extracted=total_tables,
            processing_time_ms=(time.perf_counter() - start_time) * 1000,
        )

    def _parse_xls(self, file_bytes: bytes, resolved_name: str, file_size: int, start_time: float) -> DocumentExtractionResult:
        """Parses legacy binary XLS workbooks using xlrd."""
        import xlrd

        try:
            wb = xlrd.open_workbook(file_contents=file_bytes)
            sheet_names = wb.sheet_names()
        except (xlrd.biffh.XLRDError, Exception) as e:
            return DocumentExtractionResult(
                filename=resolved_name,
                file_type="xls",
                status=ExtractionStatus.CORRUPTED,
                metadata=DocumentMetadata(file_size_bytes=file_size),
                error_message=f"Corrupted or invalid legacy XLS workbook: {e}",
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        pages: List[PageExtraction] = []
        total_tables = 0
        all_sheet_texts: List[str] = []

        for idx, sname in enumerate(sheet_names, start=1):
            sheet = wb.sheet_by_name(sname)
            raw_rows: List[List[Optional[str]]] = []

            for row_idx in range(sheet.nrows):
                row_vals = [str(sheet.cell_value(row_idx, col_idx)).strip() for col_idx in range(sheet.ncols)]
                raw_rows.append(row_vals)

            non_empty_rows = [r for r in raw_rows if any(c != "" for c in r)]

            if not non_empty_rows:
                pages.append(PageExtraction(
                    page_number=idx,
                    text="",
                    word_count=0,
                    char_count=0,
                    has_text=False,
                    has_images=False,
                    is_blank=True,
                    needs_ocr=False,
                    ocr_applied=False,
                    ocr_confidence=None,
                    tables=[],
                ))
            else:
                md_text = self._render_table_to_markdown(sname, non_empty_rows)
                words = md_text.split()
                w_count = len(words)
                c_count = len(md_text)
                h_text = w_count >= self.min_words_threshold

                pages.append(PageExtraction(
                    page_number=idx,
                    text=md_text,
                    word_count=w_count,
                    char_count=c_count,
                    has_text=h_text,
                    has_images=False,
                    is_blank=False,
                    needs_ocr=False,
                    ocr_applied=False,
                    ocr_confidence=None,
                    tables=[non_empty_rows],
                ))
                total_tables += 1
                if md_text:
                    all_sheet_texts.append(md_text)

        # Recompute overall workbook status
        page_count = len(pages)
        blank_pages = sum(1 for p in pages if p.is_blank)
        text_pages = sum(1 for p in pages if p.has_text)

        if page_count == 0 or blank_pages == page_count:
            status = ExtractionStatus.EMPTY
        elif text_pages > 0:
            status = ExtractionStatus.SUCCESS
        else:
            status = ExtractionStatus.EMPTY

        full_text = "\n\n--- Page Break ---\n\n".join(all_sheet_texts)

        return DocumentExtractionResult(
            filename=resolved_name,
            file_type="xls",
            status=status,
            metadata=DocumentMetadata(
                page_count=page_count,
                file_size_bytes=file_size,
                title=f"Sheets: {', '.join(sheet_names)}",
            ),
            pages=pages,
            full_text=full_text,
            tables_extracted=total_tables,
            processing_time_ms=(time.perf_counter() - start_time) * 1000,
        )

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
            resolved_name = "spreadsheet.xlsx"

        ext = Path(resolved_name).suffix.lower()
        file_type = ext.lstrip(".") if ext else "xlsx"

        # Enforce supported extensions
        if ext and ext not in self.SUPPORTED_EXTENSIONS:
            return DocumentExtractionResult(
                filename=resolved_name,
                file_type=file_type,
                status=ExtractionStatus.FAILED,
                metadata=DocumentMetadata(),
                error_message=f"Unsupported spreadsheet file extension '{ext}'. Supported extensions: {sorted(self.SUPPORTED_EXTENSIONS)}",
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Resolve input bytes or path
        file_bytes: Optional[bytes] = None
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
                        error_message="Spreadsheet file is 0 bytes (empty file)",
                        processing_time_ms=(time.perf_counter() - start_time) * 1000,
                    )
                with open(path_obj, "rb") as f:
                    file_bytes = f.read()
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
            file_bytes = file_input
            file_size = len(file_bytes)
            if file_size == 0:
                return DocumentExtractionResult(
                    filename=resolved_name,
                    file_type=file_type,
                    status=ExtractionStatus.EMPTY,
                    metadata=DocumentMetadata(file_size_bytes=0),
                    error_message="Spreadsheet byte stream is empty (0 bytes)",
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

        # Route to format-specific parser
        if ext == ".csv":
            return self._parse_csv(file_bytes, resolved_name, file_size, start_time)
        elif ext == ".xls":
            return self._parse_xls(file_bytes, resolved_name, file_size, start_time)
        else:
            return self._parse_xlsx(file_bytes, resolved_name, file_size, start_time)
