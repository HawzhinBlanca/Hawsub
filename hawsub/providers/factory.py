"""
Provider Factory for Hawsub.
"""

from typing import Optional
from hawsub.providers.base import SemanticModel
from hawsub.providers.mock import MockSemanticModel
from hawsub.providers.generic_api import GenericAPIModel


def get_provider(
    provider_name: str = "google",
    model_name: str = "gemini-2.5-pro",
    temperature: float = 0.2,
    api_key: Optional[str] = None,
    allow_mock_fallback: bool = True,
) -> SemanticModel:
    """Instantiate and return the requested LLM provider."""
    provider_name_clean = provider_name.lower().strip()

    if provider_name_clean == "mock":
        return MockSemanticModel(model_name=model_name, temperature=temperature)

    if provider_name_clean in ["google", "openai", "anthropic", "openrouter", "local"]:
        return GenericAPIModel(
            provider_name=provider_name_clean,
            model_name=model_name,
            api_key=api_key,
            temperature=temperature,
        )

    if allow_mock_fallback:
        return MockSemanticModel(model_name=model_name, temperature=temperature)

    raise ValueError(f"Unknown provider: {provider_name}")
