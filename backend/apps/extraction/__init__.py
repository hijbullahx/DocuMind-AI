"""
DocuMind AI Extraction Package.
Exports Pydantic schemas, validation errors, zero-hallucination prompt builders,
and modular LLM extraction clients.
"""
from .schemas import (
    ExtractionSchemaError,
    InvoiceExtraction,
    LineItemExtraction,
    _clean_decimal_str,
    _clean_numeric_input,
)
from .prompts import (
    INVOICE_EXTRACTION_SYSTEM_PROMPT,
    build_extraction_prompt,
    build_prompt_messages,
)
from .llm_client import (
    BaseLLMProvider,
    EvidenceAlignmentStatus,
    ExtractionResultStatus,
    GeminiProvider,
    LLMConfigurationError,
    LLMExtractionClient,
    LLMExtractionResult,
    MockLLMProvider,
    OpenAIProvider,
    ProviderRawResponse,
    _adapt_schema_for_openai_strict,
    _inline_json_schema,
    compute_evidence_confidence,
)

__all__ = [
    "InvoiceExtraction",
    "LineItemExtraction",
    "ExtractionSchemaError",
    "_clean_decimal_str",
    "_clean_numeric_input",
    "INVOICE_EXTRACTION_SYSTEM_PROMPT",
    "build_extraction_prompt",
    "build_prompt_messages",
    "BaseLLMProvider",
    "EvidenceAlignmentStatus",
    "ExtractionResultStatus",
    "GeminiProvider",
    "LLMConfigurationError",
    "LLMExtractionClient",
    "LLMExtractionResult",
    "MockLLMProvider",
    "OpenAIProvider",
    "ProviderRawResponse",
    "_adapt_schema_for_openai_strict",
    "_inline_json_schema",
    "compute_evidence_confidence",
]
