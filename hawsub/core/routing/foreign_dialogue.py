"""
Foreign-Language Dialogue Router.
Handles the 4 narrative opacity cases for non-English dialogue segments.
"""

import re
from typing import Optional
from pydantic import BaseModel
from hawsub.core.ingest.parser import SubtitleCueModel
from hawsub.core.normalization.sorani import SoraniNormalizer


class ForeignRoutingResult(BaseModel):
    cue_id: int
    case_type: str  # A | B | C | D
    narrative_opacity: bool
    sorani_indicator: Optional[str] = None
    action_required: str  # translate | preserve_opaque | flag_missing | transcribe_exception
    notes: str = ""


class ForeignDialogueRouter:
    """Routes non-English or foreign speech according to cinematic narrative opacity rules."""

    OPAQUE_INDICATOR_PATTERN = r"^\[(speaking|in|speaks)\s+([a-z\s]+)\]$"

    def __init__(self):
        self.normalizer = SoraniNormalizer()

    def route_cue(self, cue: SubtitleCueModel) -> ForeignRoutingResult:
        text = cue.clean_source_text.strip()
        
        # Check Case B: Intentionally hidden opaque dialogue e.g. [Speaking Spanish]
        match_opaque = re.match(self.OPAQUE_INDICATOR_PATTERN, text, re.IGNORECASE)
        if match_opaque:
            lang_name = match_opaque.group(2).strip()
            sorani_ind = self._format_sorani_opaque_indicator(lang_name)
            return ForeignRoutingResult(
                cue_id=cue.id,
                case_type="B",
                narrative_opacity=True,
                sorani_indicator=sorani_ind,
                action_required="preserve_opaque",
                notes=f"Preserved narrative opacity for foreign dialogue ({lang_name})",
            )

        # Check Case A: Subtitle translates foreign speech e.g. "[in Spanish] Hello my friend"
        match_translated = re.match(r"^\[(in|speaking)\s+([a-z\s]+)\]\s*(.*)", text, re.IGNORECASE)
        if match_translated and match_translated.group(3).strip():
            return ForeignRoutingResult(
                cue_id=cue.id,
                case_type="A",
                narrative_opacity=False,
                sorani_indicator=None,
                action_required="translate",
                notes="Foreign dialogue with English translation provided",
            )

        # Check Case C/D: Flag missing or exception foreign speech
        if cue.foreign_language and not text:
            return ForeignRoutingResult(
                cue_id=cue.id,
                case_type="D",
                narrative_opacity=False,
                sorani_indicator=None,
                action_required="transcribe_exception",
                notes="Foreign dialogue missing subtitle text, requiring exception transcription",
            )

        # Default standard dialogue
        return ForeignRoutingResult(
            cue_id=cue.id,
            case_type="A",
            narrative_opacity=False,
            sorani_indicator=None,
            action_required="translate",
            notes="Standard dialogue",
        )

    def _format_sorani_opaque_indicator(self, language: str) -> str:
        lang_map = {
            "spanish": "ئیسپانی",
            "french": "فەرەنسی",
            "german": "ئەڵمانی",
            "italian": "ئیتالی",
            "russian": "ڕوسی",
            "arabic": "عەرەبی",
            "turkish": "تورکی",
            "japanese": "ژاپۆنی",
            "chinese": "چینی",
        }
        sorani_lang = lang_map.get(language.lower(), language)
        return self.normalizer.normalize(f"[{sorani_lang} دەدوێت]")
