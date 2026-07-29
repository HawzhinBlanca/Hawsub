"""
Glossary & Terminology Management Engine for Hawsub.
Enforces character names, honorifics, proper nouns, and series-level term consistency.
"""

import re
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class GlossaryTerm(BaseModel):
    source_term: str
    target_sorani: str
    category: str = "general"  # character | place | honorific | technical | general
    notes: Optional[str] = None


class GlossaryEngine:
    """Manages project and series-level terminology translation rules."""

    DEFAULT_HONORIFICS = {
        "mr.": "بەڕێز",
        "mrs.": "خاتوونی",
        "ms.": "خاتوو",
        "dr.": "دکتۆر",
        "professor": "پڕۆفیسۆر",
        "captain": "کاپتن",
        "detective": "پشکنەر",
    }

    def __init__(self, custom_terms: Optional[Dict[str, str]] = None):
        self.terms: Dict[str, GlossaryTerm] = {}
        # Load default honorifics
        for src, trg in self.DEFAULT_HONORIFICS.items():
            self.add_term(src, trg, category="honorific")

        if custom_terms:
            for src, trg in custom_terms.items():
                self.add_term(src, trg)

    def add_term(self, source_term: str, target_sorani: str, category: str = "general", notes: Optional[str] = None) -> None:
        key = source_term.strip().lower()
        self.terms[key] = GlossaryTerm(
            source_term=source_term.strip(),
            target_sorani=target_sorani.strip(),
            category=category,
            notes=notes,
        )

    def apply_glossary(self, source_text: str, current_translation: str) -> str:
        """Enforce glossary replacements in target Sorani text where applicable."""
        if not current_translation:
            return current_translation

        result = current_translation
        source_lower = source_text.lower()

        for key, term in self.terms.items():
            # Check if source contains the glossary term
            pattern = r"(?:\b|^)" + re.escape(key) + r"(?:\b|$|\s)"
            if re.search(pattern, source_lower, re.IGNORECASE):
                # If target missing exact term, apply hint (for honorifics)
                if term.category == "honorific" and term.target_sorani not in result:
                    # Prepend honorific if missing
                    if not result.startswith(term.target_sorani):
                        result = f"{term.target_sorani} {result}"

        return result
