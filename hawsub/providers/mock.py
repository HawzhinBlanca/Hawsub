"""
Mock Provider for Hawsub — Provides deterministic offline responses for testing and baseline pipelines.
"""

from typing import List, Dict, Any, Optional
from hawsub.providers.base import (
    SemanticModel,
    SemanticInterpretationResponse,
    SemanticInterpretationItem,
    TranslationResponse,
    TranslationCueItem,
    VerificationResponse,
)
from hawsub.core.normalization.sorani import SoraniNormalizer


class MockSemanticModel(SemanticModel):
    """Mock Provider that simulates high-quality Sorani translation offline."""

    def __init__(self, model_name: str = "mock-gemini-2.5-pro", temperature: float = 0.2):
        super().__init__("mock", model_name, temperature)
        self.normalizer = SoraniNormalizer()

    def analyze_scene(
        self, scene_id: str, cues_data: List[Dict[str, Any]], context_data: Dict[str, Any]
    ) -> SemanticInterpretationResponse:
        items = []
        for cue in cues_data:
            c_id = cue.get("id", 1)
            src = cue.get("source_text", "")
            items.append(
                SemanticInterpretationItem(
                    cue_ids=[c_id],
                    source_text=src,
                    intended_meaning=f"Intended meaning of '{src}' in scene {scene_id}",
                    tone="informal" if "you" in src.lower() else "neutral",
                    register="informal",
                    ambiguity_score=0.05,
                )
            )
        return SemanticInterpretationResponse(scene_id=scene_id, items=items, model_version=self.model_name)

    def translate_scene(
        self,
        scene_id: str,
        cues_data: List[Dict[str, Any]],
        interpretations: Optional[List[SemanticInterpretationItem]],
        context_data: Dict[str, Any],
    ) -> TranslationResponse:
        translations = []
        for cue in cues_data:
            c_id = cue.get("id", 1)
            src = cue.get("source_text", "")
            
            # Simple rule-based mock translation generator for basic English phrases
            sorani_text = self._mock_translate(src)
            normalized = self.normalizer.normalize(sorani_text)

            translations.append(
                TranslationCueItem(
                    cue_ids=[c_id],
                    meaning=f"Meaning of {src}",
                    translation=normalized,
                    confidence=0.96,
                    ambiguity=False,
                )
            )
        return TranslationResponse(scene_id=scene_id, translations=translations, model_name=self.model_name)

    def verify_translation(
        self,
        source_text: str,
        current_translation: str,
        meaning: str,
        context_data: Dict[str, Any],
    ) -> VerificationResponse:
        # Check if translation looks clean
        if "ک" in current_translation or "ی" in current_translation or len(current_translation) > 2:
            return VerificationResponse(
                cue_ids=[1],
                decision="agree",
                severity="none",
                reason="Translation matches natural Sorani usage",
                confidence=0.98,
            )
        return VerificationResponse(
            cue_ids=[1],
            decision="disagree",
            severity="major",
            reason="Translation missing or malformed",
            alternative="وەڕگێڕانی دروست",
            confidence=0.85,
        )

    def _mock_translate(self, english_text: str) -> str:
        text_lower = english_text.lower().strip(".,!?\"'")
        translations_dict = {
            "hello my friend": "سڵاو هاوڕێم",
            "hello": "سڵاو",
            "you're pushing your luck": "تۆ زێدەڕۆیی لە بەختت دەکەیت",
            "i told you to stop": "پێم گوتیت بوەستە",
            "what are you doing": "چی دەکەیت؟",
            "thank you very much": "زۆر سوپاس",
            "thank you": "سوپاس",
            "bite your tongue": "زمانت بگرە",
            "break a leg": "بەختی باشت هەبێت",
            "in over my head": "لە سەرتاپای ئەم بابەتەدا نوقم بووم",
            "over my dead body": "تەنها بەسەر تەرمەکەمدا",
            "goodbye": "ماڵئاوا",
            "yes": "بەڵێ",
            "no": "نەخێر",
        }
        for k, v in translations_dict.items():
            if k in text_lower:
                return v
        return f"تەرجەمەی: {english_text}"
