"""
Base abstractions, schemas, and interfaces for document ingestion.
Independent of Django models/views to maintain modularity.
"""
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class ExtractionStatus(str, Enum):
    """Extraction outcome state for ingested documents."""
    SUCCESS = "SUCCESS"               # High-confidence digital or OCR-recovered text extracted across all non-blank pages
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS" # Mixed document where some pages were extracted and others failed or yielded sparse text
    NEEDS_OCR = "NEEDS_OCR"           # Document has image-only pages requiring OCR (or OCR completed with 0 text)
    EMPTY = "EMPTY"                   # Document contains 0 pages, completely blank pages, or clean OCR yielded 0 text
    CORRUPTED = "CORRUPTED"           # File is malformed, truncated, or unreadable
    FAILED = "FAILED"                 # Unhandled processing failure or fatal engine crash


class PageExtraction(BaseModel):
    """Extraction details for an individual document page."""
    page_number: int = Field(..., description="1-indexed page number")
    text: str = Field(default="", description="Extracted textual content")
    word_count: int = Field(default=0, description="Total word count on page")
    tables: List[List[List[Optional[str]]]] = Field(
        default_factory=list,
        description="Extracted table grids: [table_idx][row_idx][col_idx]"
    )
    has_text: bool = Field(default=False, description="True if text word count >= threshold")
    has_images: bool = Field(default=False, description="True if embedded raster images are detected")
    char_count: int = Field(default=0, description="Character count on page")
    is_blank: bool = Field(default=False, description="True if page has zero text and zero images")
    needs_ocr: bool = Field(default=False, description="True if page requires OCR processing")
    ocr_applied: bool = Field(default=False, description="True if OCR was executed on this page")
    ocr_confidence: Optional[float] = Field(default=None, description="Average OCR confidence score 0.0-1.0")


class DocumentMetadata(BaseModel):
    """Extracted file and document container metadata."""
    page_count: int = Field(default=0)
    title: Optional[str] = None
    author: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    creation_date: Optional[str] = None
    modification_date: Optional[str] = None
    file_size_bytes: int = Field(default=0)
    is_encrypted: bool = Field(default=False)


class DocumentExtractionResult(BaseModel):
    """Standardized result returned by any modular ingestion parser."""
    filename: str
    file_type: str = Field(..., description="e.g. pdf, png, xlsx, csv")
    status: ExtractionStatus
    metadata: DocumentMetadata
    pages: List[PageExtraction] = Field(default_factory=list)
    full_text: str = Field(default="", description="Consolidated document text across all pages")
    tables_extracted: int = Field(default=0, description="Total count of tables found")
    error_message: Optional[str] = None
    table_extraction_warning: Optional[str] = Field(
        default=None,
        description="Diagnostic warning if table extraction encountered an issue without breaking text extraction"
    )
    ocr_warnings: List[str] = Field(
        default_factory=list,
        description="Page-level or engine-level diagnostic warnings encountered during OCR processing"
    )
    processing_time_ms: float = Field(default=0.0, description="Elapsed execution time in milliseconds")


class BaseParser(ABC):
    """Abstract interface for all format-specific document parsers."""

    @abstractmethod
    def parse(self, file_path_or_bytes: Union[str, Path, bytes], filename: Optional[str] = None) -> DocumentExtractionResult:
        """
        Parse the specified file input and return a DocumentExtractionResult.
        Must handle malformed files gracefully without unhandled exceptions.
        """
        pass
