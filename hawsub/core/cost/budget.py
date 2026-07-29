"""
Token Budget & Cost Estimation Engine for Hawsub.
Tracks API usage, estimates costs, and enforces spending limits.
"""

import logging
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field

logger = logging.getLogger("hawsub.cost")


# Approximate token cost per model (USD per 1K tokens)
MODEL_COSTS = {
    # Google
    "gemini-2.5-pro": {"input": 0.00125, "output": 0.005},
    "gemini-2.5-flash": {"input": 0.00015, "output": 0.0006},
    # OpenAI
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    # Anthropic
    "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
    "claude-3-5-haiku-20241022": {"input": 0.0008, "output": 0.004},
    # Default fallback
    "_default": {"input": 0.001, "output": 0.003},
}

# Rough estimate: 4 chars ≈ 1 token for English, 2 chars ≈ 1 token for Sorani/Arabic script
CHARS_PER_TOKEN_EN = 4.0
CHARS_PER_TOKEN_AR = 2.0


class CostEstimate(BaseModel):
    """Cost estimate for a pipeline run."""
    total_cues: int = 0
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    model_name: str = ""
    provider_name: str = ""


class TokenBudget:
    """Tracks token usage and enforces cost limits."""

    def __init__(self, max_cost_usd: float = 10.0, model_name: str = "gemini-2.5-flash"):
        self.max_cost_usd = max_cost_usd
        self.model_name = model_name
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost_usd = 0.0
        self._api_calls = 0

    @property
    def remaining_budget_usd(self) -> float:
        return max(0.0, self.max_cost_usd - self._total_cost_usd)

    @property
    def total_cost_usd(self) -> float:
        return self._total_cost_usd

    @property
    def api_calls(self) -> int:
        return self._api_calls

    def _get_model_cost(self) -> Dict[str, float]:
        """Get cost rates for the current model."""
        return MODEL_COSTS.get(self.model_name, MODEL_COSTS["_default"])

    def estimate_scene_cost(self, cues_data: list, system_prompt_len: int = 2000) -> float:
        """Estimate cost for translating a scene batch."""
        costs = self._get_model_cost()

        # Estimate input tokens: system prompt + cue texts
        total_chars = system_prompt_len
        for cue in cues_data:
            total_chars += len(cue.get("source_text", "")) + 50  # 50 chars overhead per cue JSON
        input_tokens = int(total_chars / CHARS_PER_TOKEN_EN)

        # Estimate output tokens: ~1.2x source length for Sorani translations
        output_chars = sum(len(cue.get("source_text", "")) * 1.2 for cue in cues_data)
        output_chars += 100  # JSON overhead
        output_tokens = int(output_chars / CHARS_PER_TOKEN_AR)

        cost = (input_tokens * costs["input"] / 1000) + (output_tokens * costs["output"] / 1000)
        return round(cost, 6)

    def record_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Record actual token usage from an API call."""
        costs = self._get_model_cost()
        cost = (input_tokens * costs["input"] / 1000) + (output_tokens * costs["output"] / 1000)

        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._total_cost_usd += cost
        self._api_calls += 1

        if self._total_cost_usd > self.max_cost_usd:
            logger.warning(
                f"Budget exceeded: ${self._total_cost_usd:.4f} > ${self.max_cost_usd:.2f}"
            )

    def check_budget(self, estimated_cost: float) -> bool:
        """Check if an estimated cost fits within remaining budget."""
        return (self._total_cost_usd + estimated_cost) <= self.max_cost_usd

    def estimate_full_file(self, total_cues: int, avg_source_length: int = 40) -> CostEstimate:
        """Estimate total cost for processing an entire file.
        
        Accounts for 3 API calls per scene batch:
        1. Semantic analysis
        2. Translation  
        3. Verification (for flagged cues ~20%)
        """
        costs = self._get_model_cost()

        # Assume ~20 cues per scene batch
        num_scenes = max(1, total_cues // 20)

        # Input tokens per scene: ~2000 (system prompt) + cues
        input_per_scene = 2000 + (20 * (avg_source_length + 50))
        input_tokens_total = int(input_per_scene * num_scenes * 2.5 / CHARS_PER_TOKEN_EN)  # 2.5 = analyze + translate + 50% verify

        # Output tokens: translations + analysis
        output_per_scene = 20 * avg_source_length * 1.2  # translations
        output_tokens_total = int(output_per_scene * num_scenes * 2.0 / CHARS_PER_TOKEN_AR)

        total_cost = (input_tokens_total * costs["input"] / 1000) + (output_tokens_total * costs["output"] / 1000)

        return CostEstimate(
            total_cues=total_cues,
            estimated_input_tokens=input_tokens_total,
            estimated_output_tokens=output_tokens_total,
            estimated_cost_usd=round(total_cost, 4),
            model_name=self.model_name,
        )

    def get_summary(self) -> Dict[str, Any]:
        """Get usage summary."""
        return {
            "model": self.model_name,
            "api_calls": self._api_calls,
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "total_cost_usd": round(self._total_cost_usd, 6),
            "max_budget_usd": self.max_cost_usd,
            "remaining_usd": round(self.remaining_budget_usd, 6),
        }
