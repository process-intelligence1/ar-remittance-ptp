"""Optional hosted-LLM fallback for e-mails the rules cannot read (LLM_PROVIDER = none | gemini | groq).

INTERFACE ONLY - off by default and never required. A provider would receive the e-mail's text and
return lines in the same shape as the rules; nothing is sent anywhere while the setting is "none".
Free tiers only (zero-cost rule); a real provider is added later if the owner decides to.
"""
from app.extraction.extractor import ExtractionResult


class LlmNotConfigured(RuntimeError):
    pass


def provider_name(cfg: dict) -> str:
    return (cfg.get("llm_provider") or "none").lower()


def maybe_improve(result: ExtractionResult, cfg: dict) -> ExtractionResult:
    """Called when the rules found no lines. With provider "none" (default) the result is unchanged."""
    name = provider_name(cfg)
    if name == "none" or result.status not in ("NO_LINES",):
        return result
    raise LlmNotConfigured(f"LLM provider '{name}' is not implemented (interface only); set llm_provider to none")
