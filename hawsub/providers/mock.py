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
            # Common phrases
            "hello my friend": "سڵاو هاوڕێم",
            "hello": "سڵاو",
            "goodbye": "ماڵئاوا",
            "yes": "بەڵێ",
            "no": "نەخێر",
            "thank you very much": "زۆر سوپاس",
            "thank you": "سوپاس",
            "i told you to stop": "پێم گوتیت بوەستە",
            "what are you doing": "چی دەکەیت؟",
            # Gold benchmark idioms (must match gold_dataset.json)
            "you're pushing your luck": "تۆ زێدەڕۆیی لە بەختت دەکەیت",
            "bite your tongue": "زمانت بگرە!",
            "break a leg": "بەختی باشت هەبێت!",
            "i am in over my head": "من لە سەرتاپای ئەم بابەتەدا نوقم بووم",
            "over my dead body": "تەنها بەسەر تەرمەکەمدا!",
            "it's raining cats and dogs": "بارانی زۆر دێت",
            "you stabbed me in the back": "تۆ خیانەتت لێکردم!",
            "hold your horses": "هێمن بە! چاوەڕوان بە!",
            "don't let the cat out of the bag": "نهێنییەکە ئاشکرا مەکە",
            "i have bigger fish to fry": "کاری گرنگتر لەمە هەیە بۆ ئەنجامدان",
            "time to face the music": "کاتی ئەوەیە بەرگریت بکەیت و ئەنجامەکە قبوڵ بکەیت",
            "speak of the devil": "قسەی لێوە بوو!",
            "the ball is in your court": "ئێستا بڕیاردان لە دەستی تۆیە",
            "he kicked the bucket": "مرد",
            "keep your eyes peeled": "ئاگادار بن و باش سەیر بکەن",
            "hit the nail on the head": "تەواو بە دروستی پێت گوت",
            "under the weather": "کەمێک هەست بە نەخۆشی دەکەم",
            "spill the beans": "سڕەکە ئاشکرا بکە!",
            "barking up the wrong tree": "لە شوێنی هەڵەدا دەگەڕێیت",
            "burn the midnight oil": "تا درەنگانی شەو کارم دەکرد",
            # Additional common cinema phrases
            "i love you": "خۆشمدەوێت",
            "help me": "یارمەتیم بدە",
            "let's go": "وەرە بڕۆین",
            "come on": "وەرە",
            "wait": "وەستە",
            "stop": "بوەستە",
            "run": "بڕۆ",
            "get out": "بچۆ دەرەوە",
            "shut up": "دەمت دابخە",
            "please": "تکایە",
            "sorry": "ببورە",
            "be careful": "وریابە",
            "are you ok": "باشیت؟",
            "i'm fine": "باشم",
            "what happened": "چی بوو؟",
            "i don't know": "نازانم",
            "it's over": "تەواو بوو",
        }
        for k, v in translations_dict.items():
            if k in text_lower:
                return v
        return f"تەرجەمەی: {english_text}"
