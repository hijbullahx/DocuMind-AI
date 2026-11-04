"""
Modular LLM Extraction Client for Structured Invoice Intelligence.
Integrates with Gemini, OpenAI, or Mock providers using JSON Schema enforcement,
robust error handling, exponential backoff retries, and evidence-grounded heuristic scoring.
"""
from abc import ABC, abstractmethod
import copy
from decimal import Decimal
from enum import Enum
import json
import logging
import os
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.error
import urllib.request

from .prompts import build_prompt_messages
from .schemas import ExtractionSchemaError, InvoiceExtraction

logger = logging.getLogger(__name__)

# Common English stopwords to ignore when evaluating partial word overlap
_GROUNDING_STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "to", "in", "of", "on", "at",
    "by", "from", "with", "is", "are", "was", "were", "this", "that", "our",
}


class LLMConfigurationError(Exception):
    """Raised when an LLM provider is improperly configured or missing required credentials."""
    pass


class ExtractionResultStatus(str, Enum):
    """Status outcomes for an LLM extraction attempt."""
    SUCCESS = "SUCCESS"
    SCHEMA_VALIDATION_ERROR = "SCHEMA_VALIDATION_ERROR"
    MALFORMED_OUTPUT = "MALFORMED_OUTPUT"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    TIMEOUT = "TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    CONFIG_ERROR = "CONFIG_ERROR"


class EvidenceAlignmentStatus(str, Enum):
    """Alignment classification of model-claimed evidence quote against source document text."""
    EXACT_MATCH = "EXACT_MATCH"        # Verbatim contiguous substring in document
    HIGH_OVERLAP = "HIGH_OVERLAP"      # >= 80% non-stopword token overlap
    PARTIAL_OVERLAP = "PARTIAL_OVERLAP"# 40% - 79% token overlap
    UNMATCHED = "UNMATCHED"            # < 40% token overlap or completely unrelated
    MISSING_QUOTE = "MISSING_QUOTE"    # Field extracted non-null, but no quote was provided in raw_text_evidence
    NOT_APPLICABLE = "NOT_APPLICABLE"  # Field is explicitly null (no value to ground)


class ProviderRawResponse:
    """Standardized response container returned by lower-level LLM providers."""

    def __init__(
        self,
        content: str,
        token_usage: Optional[Dict[str, int]] = None,
        raw_metadata: Optional[Dict[str, Any]] = None,
    ):
        self.content = content
        self.token_usage = token_usage or {}
        self.raw_metadata = raw_metadata or {}


class LLMExtractionResult:
    """
    Standardized result contract for document extraction.
    Holds validated invoice model, extraction status, heuristic evidence-grounding scores,
    provenance citations, and execution diagnostics.

    Heuristic Grounding Disclosure:
    confidence_score and field_confidences are heuristic evidence-grounding metrics reflecting
    source-text quotation alignment. They do NOT represent calibrated Bayesian posterior probabilities
    or LLM token log-likelihoods.
    """

    def __init__(
        self,
        status: ExtractionResultStatus,
        invoice: Optional[InvoiceExtraction] = None,
        raw_response: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        confidence_score: Optional[float] = None,
        field_confidences: Optional[Dict[str, Optional[float]]] = None,
        evidence_statuses: Optional[Dict[str, str]] = None,
        error_message: Optional[str] = None,
        token_usage: Optional[Dict[str, int]] = None,
        latency_ms: Optional[float] = None,
        retry_count: int = 0,
        source_text_evaluated: Optional[str] = None,
    ):
        self.status = status
        self.invoice = invoice
        self.raw_response = raw_response
        self.model = model
        self.provider = provider
        # Composite heuristic evidence-grounding score [0.0, 1.0] across non-null fields
        self.confidence_score = confidence_score
        # Per-field heuristic evidence-grounding scores (None for null fields)
        self.field_confidences = field_confidences or {}
        # Per-field alignment status (EXACT_MATCH, HIGH_OVERLAP, UNMATCHED, etc.)
        self.evidence_statuses = evidence_statuses or {}
        self.error_message = error_message
        self.token_usage = token_usage or {}
        self.latency_ms = latency_ms
        self.retry_count = retry_count
        self.source_text_evaluated = source_text_evaluated

    @property
    def evidence_grounding_score(self) -> Optional[float]:
        """Alias for confidence_score explicitly identifying it as a heuristic grounding score."""
        return self.confidence_score

    @property
    def field_grounding_scores(self) -> Dict[str, Optional[float]]:
        """Alias for field_confidences explicitly identifying them as heuristic grounding scores."""
        return self.field_confidences

    def to_dict(self) -> Dict[str, Any]:
        """Serializes result to a dictionary."""
        return {
            "status": self.status.value,
            "invoice": self.invoice.model_dump() if self.invoice else None,
            "raw_response": self.raw_response,
            "model": self.model,
            "provider": self.provider,
            "confidence_score": self.confidence_score,
            "field_confidences": self.field_confidences,
            "evidence_statuses": self.evidence_statuses,
            "error_message": self.error_message,
            "token_usage": self.token_usage,
            "latency_ms": self.latency_ms,
            "retry_count": self.retry_count,
        }


def compute_evidence_confidence(
    invoice: InvoiceExtraction,
    document_text: str,
) -> Tuple[Optional[float], Dict[str, Optional[float]], Dict[str, str]]:
    """
    Computes heuristic field-level and overall evidence-grounding scores.

    Grounding Scoring Rules (heuristic, not calibrated probabilities):
      - EXACT_MATCH (1.00): Verbatim quote exists contiguously in normalized document text.
      - HIGH_OVERLAP (0.75): Non-stopword token overlap >= 80%.
      - PARTIAL_OVERLAP (0.40): Non-stopword token overlap 40% - 79%.
      - UNMATCHED (0.00): Token overlap < 40% or quote completely absent.
      - MISSING_QUOTE: Field is non-null, but no quote was provided in raw_text_evidence.
                       (0.50 if field value string appears in document, else 0.20).
      - NOT_APPLICABLE (None): Field is explicitly null. Null fields are NOT awarded 1.0;
                               they represent absent values and are excluded from the composite score.

    Returns:
      (composite_grounding_score, field_scores_dict, evidence_statuses_dict)
    """
    fields_to_check = [
        "invoice_number",
        "invoice_date",
        "due_date",
        "supplier_name",
        "supplier_address",
        "customer_name",
        "customer_address",
        "subtotal",
        "tax",
        "total",
        "currency",
    ]

    doc_normalized = " ".join(document_text.split()).lower()
    doc_tokens = set(re.findall(r"\b[a-zA-Z0-9_\-\.\$€£¥₹]{2,}\b", doc_normalized)) - _GROUNDING_STOPWORDS

    field_scores: Dict[str, Optional[float]] = {}
    evidence_statuses: Dict[str, str] = {}
    evaluated_scores: List[float] = []

    for field in fields_to_check:
        val = getattr(invoice, field, None)
        evidence = invoice.raw_text_evidence.get(field)

        if val is None:
            # Null field: no extracted value to ground in text
            field_scores[field] = None
            evidence_statuses[field] = EvidenceAlignmentStatus.NOT_APPLICABLE.value
            continue

        if evidence and evidence.strip():
            ev_clean = " ".join(evidence.split()).lower()
            if ev_clean in doc_normalized:
                score = 1.0
                status = EvidenceAlignmentStatus.EXACT_MATCH.value
            else:
                # Token-based overlap excluding stopwords
                ev_tokens = [
                    w for w in re.findall(r"\b[a-zA-Z0-9_\-\.\$€£¥₹]{2,}\b", ev_clean)
                    if w not in _GROUNDING_STOPWORDS
                ]
                if not ev_tokens:
                    matched = ev_clean in doc_normalized
                    score = 1.0 if matched else 0.0
                    status = EvidenceAlignmentStatus.EXACT_MATCH.value if matched else EvidenceAlignmentStatus.UNMATCHED.value
                else:
                    matched_count = sum(1 for w in ev_tokens if w in doc_tokens)
                    ratio = matched_count / len(ev_tokens)
                    if ratio >= 0.8:
                        score = 0.75
                        status = EvidenceAlignmentStatus.HIGH_OVERLAP.value
                    elif ratio >= 0.4:
                        score = 0.40
                        status = EvidenceAlignmentStatus.PARTIAL_OVERLAP.value
                    else:
                        score = 0.0
                        status = EvidenceAlignmentStatus.UNMATCHED.value
        else:
            # Non-null value with NO quote in raw_text_evidence
            val_str = str(val).lower()
            if val_str in doc_normalized:
                score = 0.50
            else:
                score = 0.20
            status = EvidenceAlignmentStatus.MISSING_QUOTE.value

        field_scores[field] = score
        evidence_statuses[field] = status
        evaluated_scores.append(score)

    # Line items evaluation
    if invoice.line_items:
        item_scores: List[float] = []
        for item in invoice.line_items:
            desc_clean = " ".join(item.description.split()).lower()
            if desc_clean in doc_normalized:
                item_scores.append(1.0)
            else:
                item_tokens = [
                    w for w in re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", desc_clean)
                    if w not in _GROUNDING_STOPWORDS
                ]
                matched = sum(1 for w in item_tokens if w in doc_tokens)
                ratio = matched / max(len(item_tokens), 1)
                item_scores.append(0.75 if ratio >= 0.8 else (0.40 if ratio >= 0.4 else 0.0))

        line_item_avg = sum(item_scores) / len(item_scores)
        field_scores["line_items"] = round(line_item_avg, 2)
        evidence_statuses["line_items"] = (
            EvidenceAlignmentStatus.EXACT_MATCH.value if line_item_avg >= 0.95
            else (EvidenceAlignmentStatus.HIGH_OVERLAP.value if line_item_avg >= 0.70
                  else EvidenceAlignmentStatus.PARTIAL_OVERLAP.value)
        )
        evaluated_scores.append(line_item_avg)
    else:
        field_scores["line_items"] = None
        evidence_statuses["line_items"] = EvidenceAlignmentStatus.NOT_APPLICABLE.value

    if evaluated_scores:
        overall = round(sum(evaluated_scores) / len(evaluated_scores), 3)
    else:
        overall = None

    return overall, field_scores, evidence_statuses


def _inline_json_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inlines all $defs references into the schema and removes top-level $defs.
    Required for Google Gemini responseSchema, which does not support $defs or $ref.
    Does NOT mutate the input schema.
    """
    s = copy.deepcopy(schema)
    defs = s.pop("$defs", {})

    def _resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref_name = node["$ref"].split("/")[-1]
                if ref_name in defs:
                    resolved = copy.deepcopy(defs[ref_name])
                    return _resolve(resolved)
            return {k: _resolve(v) for k, v in node.items()}
        elif isinstance(node, list):
            return [_resolve(item) for item in node]
        return node

    return _resolve(s)


def _adapt_schema_for_openai_strict(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adapts a Pydantic JSON Schema for OpenAI Strict Structured Outputs mode.
    OpenAI strict mode requirements:
      1. Every object MUST have 'additionalProperties': false.
      2. Dynamic maps ({type: object, additionalProperties: {type: string}}) are forbidden.
         Therefore, raw_text_evidence is adapted to an object with explicit optional properties
         matching known invoice fields.
      3. Every property declared in an object MUST be listed in 'required'.
         Nullable fields must be explicitly nullable via anyOf: [..., {"type": "null"}].
      4. Unsupported keywords like 'default' and 'title' must be stripped to prevent
         OpenAI strict schema validation rejection.
    Does NOT mutate the input schema.
    """
    s = copy.deepcopy(schema)

    # 1. Adapt raw_text_evidence from dynamic dictionary to explicit property object
    evidence_fields = [
        "invoice_number", "invoice_date", "due_date",
        "supplier_name", "supplier_address", "customer_name", "customer_address",
        "subtotal", "tax", "total", "currency", "line_items",
    ]
    if "properties" in s and "raw_text_evidence" in s["properties"]:
        ev_props = {
            f: {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": f"Verbatim source quote grounding {f}. null if field absent.",
            }
            for f in evidence_fields
        }
        s["properties"]["raw_text_evidence"] = {
            "type": "object",
            "properties": ev_props,
            "required": evidence_fields,
            "additionalProperties": False,
            "description": s["properties"]["raw_text_evidence"].get("description", ""),
        }

    # 2. Recursively ensure additionalProperties: false, required: list(properties.keys()), and strip unsupported keywords
    def _enforce_strict(node: Any) -> None:
        if isinstance(node, dict):
            # Strip keywords unsupported in OpenAI strict mode
            node.pop("default", None)
            node.pop("title", None)

            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            for v in list(node.values()):
                _enforce_strict(v)
        elif isinstance(node, list):
            for item in node:
                _enforce_strict(item)

    _enforce_strict(s)
    return s


class BaseLLMProvider(ABC):
    """Abstract Base Class for LLM API Providers."""

    def __init__(self, model_name: str, timeout: float = 30.0):
        self.model_name = model_name
        self.timeout = timeout

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique provider identifier string."""
        pass

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        json_schema: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> ProviderRawResponse:
        """
        Executes raw generation with structured output enforcement.
        Raises urllib.error.URLError, TimeoutError, or Exception on network/API failure.
        """
        pass


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock provider for unit tests, offline development, and CI.
    Allows injecting predetermined completions, call counters, or exceptions.
    """

    def __init__(
        self,
        model_name: str = "mock-model",
        canned_response: Optional[str] = None,
        side_effect: Optional[Callable[[List[Dict[str, str]]], str]] = None,
        exception_to_raise: Optional[Exception] = None,
        timeout: float = 30.0,
    ):
        super().__init__(model_name, timeout)
        self.canned_response = canned_response
        self.side_effect = side_effect
        self.exception_to_raise = exception_to_raise
        self.call_count = 0
        self.last_messages: Optional[List[Dict[str, str]]] = None

    @property
    def provider_name(self) -> str:
        return "mock"

    def generate(
        self,
        messages: List[Dict[str, str]],
        json_schema: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> ProviderRawResponse:
        self.call_count += 1
        self.last_messages = messages

        if self.exception_to_raise:
            raise self.exception_to_raise

        if self.side_effect:
            content = self.side_effect(messages)
            return ProviderRawResponse(content=content)

        if self.canned_response is not None:
            return ProviderRawResponse(content=self.canned_response)

        return ProviderRawResponse(content="{}")


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini API Provider using native REST API with Structured JSON output mode.
    Requires GEMINI_API_KEY or GOOGLE_API_KEY environment variable.
    Inlines schema definitions because Gemini responseSchema does not support $defs or $ref.
    """

    DEFAULT_MODEL = "gemini-1.5-flash"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: float = 30.0,
    ):
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise LLMConfigurationError(
                "GeminiProvider requires GEMINI_API_KEY or GOOGLE_API_KEY environment variable."
            )
        self.api_key = key
        model = model_name or os.getenv("DOCUMIND_LLM_MODEL") or self.DEFAULT_MODEL
        super().__init__(model, timeout)

    @property
    def provider_name(self) -> str:
        return "gemini"

    def generate(
        self,
        messages: List[Dict[str, str]],
        json_schema: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> ProviderRawResponse:
        call_timeout = timeout or self.timeout
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent?key={self.api_key}"
        )

        system_instruction = None
        contents = []

        for msg in messages:
            role = msg.get("role")
            text = msg.get("content", "")
            if role == "system":
                system_instruction = {"parts": [{"text": text}]}
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": text}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": text}]})

        generation_config: Dict[str, Any] = {
            "responseMimeType": "application/json",
            "temperature": 0.0,
        }

        if json_schema:
            # Gemini responseSchema rejects $defs/$ref; must be inlined
            generation_config["responseSchema"] = _inline_json_schema(json_schema)

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=call_timeout) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            redacted_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key=[REDACTED]"
            raise urllib.error.HTTPError(
                url=redacted_url,
                code=e.code,
                msg=f"Gemini API HTTP Error {e.code}: {e.reason}",
                hdrs=e.hdrs,
                fp=None,
            ) from None

        candidates = resp_data.get("candidates", [])
        if not candidates:
            prompt_feedback = resp_data.get("promptFeedback", {})
            block_reason = prompt_feedback.get("blockReason")
            if block_reason:
                raise RuntimeError(f"Gemini output blocked by content filters: {block_reason}")
            return ProviderRawResponse(content="")

        content_parts = candidates[0].get("content", {}).get("parts", [])
        text_content = "".join(part.get("text", "") for part in content_parts)

        usage = resp_data.get("usageMetadata", {})
        token_usage = {
            "prompt_tokens": usage.get("promptTokenCount", 0),
            "completion_tokens": usage.get("candidatesTokenCount", 0),
            "total_tokens": usage.get("totalTokenCount", 0),
        }

        return ProviderRawResponse(content=text_content, token_usage=token_usage)


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI API Provider using native REST API with strict Structured Outputs mode.
    Requires OPENAI_API_KEY environment variable.
    When json_schema is supplied, enforces strict provider-side schema validation via:
    response_format: {"type": "json_schema", "json_schema": {"strict": True, "schema": ...}}.
    """

    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: float = 30.0,
    ):
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise LLMConfigurationError("OpenAIProvider requires OPENAI_API_KEY environment variable.")
        self.api_key = key
        model = model_name or os.getenv("DOCUMIND_LLM_MODEL") or self.DEFAULT_MODEL
        super().__init__(model, timeout)

    @property
    def provider_name(self) -> str:
        return "openai"

    def generate(
        self,
        messages: List[Dict[str, str]],
        json_schema: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> ProviderRawResponse:
        call_timeout = timeout or self.timeout
        endpoint = "https://api.openai.com/v1/chat/completions"

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.0,
        }

        if json_schema:
            strict_schema = _adapt_schema_for_openai_strict(json_schema)
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "InvoiceExtraction",
                    "strict": True,
                    "schema": strict_schema,
                },
            }
        else:
            payload["response_format"] = {"type": "json_object"}

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=call_timeout) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))

        choices = resp_data.get("choices", [])
        if not choices:
            return ProviderRawResponse(content="")

        text_content = choices[0].get("message", {}).get("content", "")
        usage = resp_data.get("usage", {})
        token_usage = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

        return ProviderRawResponse(content=text_content, token_usage=token_usage)


class LLMExtractionClient:
    """
    Main entry point for AI Information Extraction.
    Coordinating prompt generation, provider execution, retry policies,
    Pydantic schema validation, and evidence-grounding assessment.
    """

    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        max_retries: int = 2,
        retry_delay_seconds: float = 0.5,
    ):
        self.provider = provider or self._discover_provider()
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

    @classmethod
    def _discover_provider(cls) -> BaseLLMProvider:
        """
        Dynamically selects provider based on environment variables:
        - DOCUMIND_LLM_PROVIDER: 'gemini' | 'openai' | 'mock'
        - Fallbacks to GEMINI_API_KEY or OPENAI_API_KEY if present.
        """
        pref = os.getenv("DOCUMIND_LLM_PROVIDER", "").lower().strip()

        if pref == "mock":
            return MockLLMProvider()

        if pref == "openai" or (not pref and os.getenv("OPENAI_API_KEY")):
            return OpenAIProvider()

        if pref == "gemini" or (not pref and (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))):
            return GeminiProvider()

        raise LLMConfigurationError(
            "No LLM provider configured. Set DOCUMIND_LLM_PROVIDER='mock' for offline testing, "
            "or set GEMINI_API_KEY / OPENAI_API_KEY."
        )

    def extract(
        self,
        document_text: str,
        timeout: Optional[float] = None,
    ) -> LLMExtractionResult:
        """
        Extracts structured InvoiceExtraction from document text.
        Guarantees zero-hallucination boundary isolation and defensive schema validation.
        """
        if not self.provider:
            return LLMExtractionResult(
                status=ExtractionResultStatus.CONFIG_ERROR,
                error_message="No LLM provider available.",
            )

        if not document_text or not document_text.strip():
            return LLMExtractionResult(
                status=ExtractionResultStatus.EMPTY_RESPONSE,
                error_message="Document text is empty or whitespace-only.",
                provider=self.provider.provider_name,
                model=self.provider.model_name,
                source_text_evaluated=document_text,
            )

        messages = build_prompt_messages(document_text)
        schema = InvoiceExtraction.model_json_schema()

        attempts = 0
        last_error_msg = None
        raw_text = None
        token_usage = {}
        start_time = time.perf_counter()

        while attempts <= self.max_retries:
            try:
                provider_resp = self.provider.generate(
                    messages=messages,
                    json_schema=schema,
                    timeout=timeout,
                )
                raw_text = provider_resp.content
                token_usage = provider_resp.token_usage
                break

            except (TimeoutError, urllib.error.URLError) as e:
                is_timeout = isinstance(e, TimeoutError) or "timed out" in str(e).lower()
                attempts += 1
                last_error_msg = f"{'Timeout' if is_timeout else 'Network'} error: {e}"

                if isinstance(e, urllib.error.HTTPError) and e.code in (400, 401, 403):
                    # Non-retriable client errors
                    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    return LLMExtractionResult(
                        status=ExtractionResultStatus.PROVIDER_ERROR,
                        provider=self.provider.provider_name,
                        model=self.provider.model_name,
                        error_message=f"Non-retriable HTTP {e.code}: {e.reason}",
                        retry_count=attempts - 1,
                        latency_ms=elapsed_ms,
                        source_text_evaluated=document_text,
                    )

                if attempts <= self.max_retries:
                    time.sleep(self.retry_delay_seconds * (2 ** (attempts - 1)))
                else:
                    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    status = ExtractionResultStatus.TIMEOUT if is_timeout else ExtractionResultStatus.PROVIDER_ERROR
                    return LLMExtractionResult(
                        status=status,
                        provider=self.provider.provider_name,
                        model=self.provider.model_name,
                        error_message=f"Failed after {attempts} attempts. Last error: {last_error_msg}",
                        retry_count=attempts - 1,
                        latency_ms=elapsed_ms,
                        source_text_evaluated=document_text,
                    )

            except Exception as e:
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                return LLMExtractionResult(
                    status=ExtractionResultStatus.PROVIDER_ERROR,
                    provider=self.provider.provider_name,
                    model=self.provider.model_name,
                    error_message=f"Provider call failed: {e}",
                    retry_count=attempts,
                    latency_ms=elapsed_ms,
                    source_text_evaluated=document_text,
                )

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        if not raw_text or not raw_text.strip():
            return LLMExtractionResult(
                status=ExtractionResultStatus.EMPTY_RESPONSE,
                raw_response=raw_text,
                provider=self.provider.provider_name,
                model=self.provider.model_name,
                error_message="Provider returned empty completion content.",
                token_usage=token_usage,
                retry_count=attempts,
                latency_ms=elapsed_ms,
                source_text_evaluated=document_text,
            )

        try:
            invoice = InvoiceExtraction.from_raw_json(raw_text)
        except ExtractionSchemaError as e:
            err_str = str(e)
            if "Malformed JSON" in err_str or "JSONDecodeError" in err_str:
                status = ExtractionResultStatus.MALFORMED_OUTPUT
            else:
                status = ExtractionResultStatus.SCHEMA_VALIDATION_ERROR

            return LLMExtractionResult(
                status=status,
                raw_response=raw_text,
                provider=self.provider.provider_name,
                model=self.provider.model_name,
                error_message=err_str,
                token_usage=token_usage,
                retry_count=attempts,
                latency_ms=elapsed_ms,
                source_text_evaluated=document_text,
            )

        # Compute heuristic evidence-grounding scores and alignment statuses
        overall_conf, field_confs, evidence_statuses = compute_evidence_confidence(invoice, document_text)

        return LLMExtractionResult(
            status=ExtractionResultStatus.SUCCESS,
            invoice=invoice,
            raw_response=raw_text,
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            confidence_score=overall_conf,
            field_confidences=field_confs,
            evidence_statuses=evidence_statuses,
            token_usage=token_usage,
            retry_count=attempts,
            latency_ms=elapsed_ms,
            source_text_evaluated=document_text,
        )
