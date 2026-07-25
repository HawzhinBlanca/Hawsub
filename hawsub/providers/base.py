"""
Provider Base Interface & Response Schemas for Hawsub.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class SemanticInterpretationItem(BaseModel):
    cue_ids: List[int]
    source_text: str
    intended_meaning: str
    tone: str = "neutral"
    speech_register: str = "informal"
    subtext: Optional[str] = None
    ambiguity_score: float = 0.0
    notes: Optional[str] = None


class SemanticInterpretationResponse(BaseModel):
    scene_id: str
    items: List[SemanticInterpretationItem]
    model_version: str = ""


class TranslationCueItem(BaseModel):
    cue_ids: List[int]
    meaning: str
    translation: str
    confidence: float = 0.95
    ambiguity: bool = False
    notes: Optional[str] = None


class TranslationResponse(BaseModel):
    scene_id: str
    translations: List[TranslationCueItem]
    model_name: str = ""
    prompt_version: str = "v1.0"


class VerificationResponse(BaseModel):
    cue_ids: List[int]
    decision: str  # agree | disagree | uncertain
    severity: str  # none | minor | major | critical
    reason: str
    alternative: Optional[str] = None
    confidence: float = 0.90


class SemanticModel(ABC):
    """Abstract interface for LLM providers (Gemini, OpenAI, Anthropic, OpenRouter, Local, Mock)."""

    def __init__(self, provider_name: str, model_name: str, temperature: float = 0.2):
        self.provider_name = provider_name
        self.model_name = model_name
        self.temperature = temperature

    @abstractmethod
    def analyze_scene(
        self, scene_id: str, cues_data: List[Dict[str, Any]], context_data: Dict[str, Any]
    ) -> SemanticInterpretationResponse:
        """Analyze narrative meaning and subtext before translating."""
        pass

    @abstractmethod
    def translate_scene(
        self,
        scene_id: str,
        cues_data: List[Dict[str, Any]],
        interpretations: Optional[List[SemanticInterpretationItem]],
        context_data: Dict[str, Any],
    ) -> TranslationResponse:
        """Translate meaning-first into Central Kurdish / Sorani (ckb)."""
        pass

    @abstractmethod
    def verify_translation(
        self,
        source_text: str,
        current_translation: str,
        meaning: str,
        context_data: Dict[str, Any],
    ) -> VerificationResponse:
        """Verify an existing translation for second-model consensus."""
        pass
