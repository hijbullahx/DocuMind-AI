"""
Modular OCR Engine Abstraction and Concrete Implementations.
Provides BaseOCREngine, EasyOCREngine, and MockOCREngine for test isolation.
"""
import io
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from pydantic import BaseModel, Field


class OCRResult(BaseModel):
    """Standardized result returned by any OCR engine implementation."""
    text: str = Field(default="", description="Recognized textual content")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Average token confidence score")
    word_count: int = Field(default=0, description="Count of recognized words")
    char_count: int = Field(default=0, description="Count of recognized characters")
    bounding_boxes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Bounding box polygons and per-token confidences"
    )
    engine_name: str = Field(default="mock", description="Name of the underlying OCR engine")
    processing_time_ms: float = Field(default=0.0, description="Inference latency in milliseconds")


class BaseOCREngine(ABC):
    """Abstract interface for all pluggable OCR engine implementations."""

    @abstractmethod
    def extract_text(self, image_input: Union[Image.Image, bytes, np.ndarray, Path, str]) -> OCRResult:
        """
        Extract text, confidence, and bounding boxes from an input image.
        Accepts PIL Image, raw bytes, numpy array, or file path.
        """
        pass


class EasyOCREngine(BaseOCREngine):
    """
    Production OCR engine utilizing EasyOCR (PyTorch CRAFT + CRNN).
    Uses lazy initialization so model weights (~80MB) are loaded into RAM
    only on the first call to extract_text(), keeping digital PDF processing fast.
    """

    def __init__(self, languages: Optional[List[str]] = None, use_gpu: bool = False):
        self.languages = languages or ["en"]
        self.use_gpu = use_gpu
        self._reader = None

    @property
    def reader(self):
        """Lazy loader for EasyOCR reader instance."""
        if self._reader is None:
            import easyocr
            self._reader = easyocr.Reader(self.languages, gpu=self.use_gpu)
        return self._reader

    def _normalize_image(self, image_input: Union[Image.Image, bytes, np.ndarray, Path, str]) -> Image.Image:
        """Converts heterogeneous inputs into an enhanced PIL Image."""
        if isinstance(image_input, Image.Image):
            pil_img = image_input
        elif isinstance(image_input, bytes):
            pil_img = Image.open(io.BytesIO(image_input))
        elif isinstance(image_input, np.ndarray):
            pil_img = Image.fromarray(image_input)
        elif isinstance(image_input, (str, Path)):
            pil_img = Image.open(image_input)
        else:
            raise ValueError(f"Unsupported image input type: {type(image_input)}")

        # Ensure RGB format
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")

        # Contrast enhancement for financial receipts / scans
        gray = ImageOps.grayscale(pil_img)
        enhanced = ImageEnhance.Contrast(gray).enhance(1.4)
        return enhanced.convert("RGB")

    def extract_text(self, image_input: Union[Image.Image, bytes, np.ndarray, Path, str]) -> OCRResult:
        start_time = time.perf_counter()
        pil_img = self._normalize_image(image_input)
        img_np = np.array(pil_img)

        # Execute EasyOCR readtext
        # readtext returns list of tuple: (bbox, text, prob)
        raw_results = self.reader.readtext(img_np)

        text_parts: List[str] = []
        confidences: List[float] = []
        boxes: List[Dict[str, Any]] = []

        for bbox, text, prob in raw_results:
            clean_text = text.strip()
            if clean_text:
                text_parts.append(clean_text)
                confidences.append(float(prob))
                boxes.append({
                    "text": clean_text,
                    "confidence": float(prob),
                    "bbox": [[int(coord) for coord in pt] for pt in bbox],
                })

        full_text = " ".join(text_parts)
        avg_confidence = float(np.mean(confidences)) if confidences else 0.0
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return OCRResult(
            text=full_text,
            confidence=avg_confidence,
            word_count=len(full_text.split()),
            char_count=len(full_text),
            bounding_boxes=boxes,
            engine_name="easyocr",
            processing_time_ms=elapsed_ms,
        )


class MockOCREngine(BaseOCREngine):
    """
    Deterministic mock OCR engine for fast, isolated, network-free unit tests.
    Allows simulating successful extractions, empty outputs, engine exceptions,
    or sequential per-page responses for multi-page test scenarios.
    """

    def __init__(
        self,
        canned_text: str = "INVOICE #INV-MOCK-001 TOTAL $1,250.00",
        confidence: float = 0.95,
        simulate_exception: Optional[Exception] = None,
        responses: Optional[List[Union[str, OCRResult, Exception]]] = None,
    ):
        self.canned_text = canned_text
        self.confidence = confidence
        self.simulate_exception = simulate_exception
        self.responses = list(responses) if responses is not None else None
        self.call_count = 0

    def extract_text(self, image_input: Union[Image.Image, bytes, np.ndarray, Path, str]) -> OCRResult:
        self.call_count += 1

        # Check if sequential response list is provided
        if self.responses is not None and len(self.responses) > 0:
            resp = self.responses.pop(0)
            if isinstance(resp, Exception):
                raise resp
            elif isinstance(resp, OCRResult):
                return resp
            elif isinstance(resp, str):
                text = resp.strip()
                words = text.split()
                return OCRResult(
                    text=text,
                    confidence=self.confidence if text else 0.0,
                    word_count=len(words),
                    char_count=len(text),
                    bounding_boxes=[],
                    engine_name="mock",
                    processing_time_ms=1.0,
                )

        if self.simulate_exception:
            raise self.simulate_exception

        text = self.canned_text.strip()
        words = text.split()
        return OCRResult(
            text=text,
            confidence=self.confidence if text else 0.0,
            word_count=len(words),
            char_count=len(text),
            bounding_boxes=[],
            engine_name="mock",
            processing_time_ms=1.0,
        )
