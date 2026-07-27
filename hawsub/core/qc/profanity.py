"""
Cultural Compliance & Broadcast Safety Engine for Central Kurdish (Sorani) Subtitles.
Detects taboo, inappropriate literal translations, or broadcast-prohibited terms, suggesting localized substitutes.
"""

from typing import List, Dict, Tuple
from pydantic import BaseModel


class ComplianceIssue(BaseModel):
    cue_id: int
    flagged_term: str
    suggested_replacement: str
    severity: str  # "high" | "medium" | "low"
    reason: str


class SoraniCulturalComplianceEngine:
    """Audits target Sorani translations for broadcast compliance and cultural adaptation rules."""

    # Curated dictionary of literal or culturally inappropriate translations -> broadcast safe equivalents
    RULES: Dict[str, Tuple[str, str, str]] = {
        # flagged_term: (suggested_replacement, severity, reason)
        "سگ": ("نەفرەتی", "medium", "Literal translation of 'bitch/dog' as insulting animal term; use localized curse equivalent"),
        "خوێنڕێژی": ("توندوتیژی", "low", "Excessively graphic violence description"),
    }

    def audit_cue(self, cue_id: int, target_text: str) -> List[ComplianceIssue]:
        issues = []
        if not target_text:
            return issues

        for term, (replacement, severity, reason) in self.RULES.items():
            if term in target_text:
                issues.append(
                    ComplianceIssue(
                        cue_id=cue_id,
                        flagged_term=term,
                        suggested_replacement=replacement,
                        severity=severity,
                        reason=reason,
                    )
                )

        return issues
