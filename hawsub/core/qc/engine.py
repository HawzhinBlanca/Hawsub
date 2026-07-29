"""
Multi-Dimensional Quality Control (QC) Engine.
Evaluates Semantic, Linguistic, and Technical quality dimensions for Hawsub.
"""

import re
import unicodedata
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field
from hawsub.core.ingest.parser import SubtitleCueModel
from hawsub.core.normalization.sorani import SoraniNormalizer
from hawsub.core.adaptation.engine import AdaptationEngine
from hawsub.config.schema import QCConfig, QCProfile


class QCIssue(BaseModel):
    cue_id: int
    category: str  # semantic | linguistic | technical
    rule: str
    severity: str  # minor | major | critical
    score_impact: float
    message: str
    status: str = "open"  # open | resolved | ignored


class QCEvaluationResult(BaseModel):
    cue_id: int
    source_confidence: float = 1.0
    semantic_score: float = 1.0
    linguistic_score: float = 1.0
    technical_score: float = 1.0
    overall_confidence: float = 1.0
    passed: bool = True
    requires_review: bool = False
    issues: List[QCIssue] = Field(default_factory=list)


class QCEngine:
    """Evaluates subtitle cues across semantic, linguistic, and technical dimensions."""

    def __init__(self, qc_config: Optional[QCConfig] = None, profile: Optional[QCProfile] = None):
        self.qc_config = qc_config or QCConfig()
        self.profile = profile or QCProfile()
        self.normalizer = SoraniNormalizer()
        self.adaptation_engine = AdaptationEngine(self.profile)

    def evaluate_cue(
        self,
        cue: SubtitleCueModel,
        next_cue: Optional[SubtitleCueModel] = None,
        context_names: Optional[List[str]] = None,
        prev_translation: Optional[str] = None,
    ) -> QCEvaluationResult:
        issues: List[QCIssue] = []
        
        # 1. Technical Checks
        tech_score = 1.0
        if self.qc_config.technical:
            tech_issues, tech_score = self._run_technical_checks(cue, next_cue)
            issues.extend(tech_issues)

        # 2. Linguistic Checks
        ling_score = 1.0
        if self.qc_config.linguistic:
            ling_issues, ling_score = self._run_linguistic_checks(cue)
            issues.extend(ling_issues)

        # 3. Semantic Checks
        sem_score = 1.0
        if self.qc_config.semantic:
            sem_issues, sem_score = self._run_semantic_checks(cue, context_names, prev_translation)
            issues.extend(sem_issues)

        # Overall confidence calculation
        overall_confidence = round(
            (cue.source_confidence * 0.2) + (sem_score * 0.4) + (ling_score * 0.2) + (tech_score * 0.2), 3
        )

        has_critical = any(i.severity == "critical" for i in issues)
        requires_review = (overall_confidence < 0.88) or has_critical
        passed = (overall_confidence >= 0.85) and not has_critical

        return QCEvaluationResult(
            cue_id=cue.id,
            source_confidence=cue.source_confidence,
            semantic_score=sem_score,
            linguistic_score=ling_score,
            technical_score=tech_score,
            overall_confidence=overall_confidence,
            passed=passed,
            requires_review=requires_review,
            issues=issues,
        )

    def _run_technical_checks(
        self, cue: SubtitleCueModel, next_cue: Optional[SubtitleCueModel]
    ) -> Tuple[List[QCIssue], float]:
        issues = []
        score = 1.0
        metrics = self.adaptation_engine.compute_metrics(cue, next_cue)

        if metrics.cps_exceeded:
            issues.append(
                QCIssue(
                    cue_id=cue.id,
                    category="technical",
                    rule="hard_max_cps",
                    severity="major",
                    score_impact=0.15,
                    message=f"CPS ({metrics.cps}) exceeds hard limit ({self.profile.hard_max_cps})",
                )
            )
            score -= 0.15

        if metrics.cpl_exceeded:
            issues.append(
                QCIssue(
                    cue_id=cue.id,
                    category="technical",
                    rule="hard_max_cpl",
                    severity="minor",
                    score_impact=0.10,
                    message=f"CPL ({metrics.max_cpl}) exceeds limit ({self.profile.hard_max_cpl})",
                )
            )
            score -= 0.10

        if metrics.lines_exceeded:
            issues.append(
                QCIssue(
                    cue_id=cue.id,
                    category="technical",
                    rule="max_lines",
                    severity="major",
                    score_impact=0.20,
                    message=f"Line count ({metrics.line_count}) exceeds max ({self.profile.max_lines})",
                )
            )
            score -= 0.20

        if metrics.duration_too_short:
            issues.append(
                QCIssue(
                    cue_id=cue.id,
                    category="technical",
                    rule="min_duration",
                    severity="minor",
                    score_impact=0.05,
                    message=f"Duration ({metrics.duration_ms}ms) below minimum ({self.profile.min_duration_ms}ms)",
                )
            )
            score -= 0.05

        return issues, max(0.0, score)

    def _run_linguistic_checks(self, cue: SubtitleCueModel) -> Tuple[List[QCIssue], float]:
        issues = []
        score = 1.0
        target = cue.target_text or ""

        # Kurmanji contamination check
        kurmanji_chars = self.normalizer.detect_kurmanji_contamination(target)
        if kurmanji_chars:
            issues.append(
                QCIssue(
                    cue_id=cue.id,
                    category="linguistic",
                    rule="kurmanji_contamination",
                    severity="critical",
                    score_impact=0.40,
                    message=f"Detected Kurmanji contamination characters: {', '.join(kurmanji_chars)}",
                )
            )
            score -= 0.40

        # Untranslated English check
        untranslated = self.normalizer.detect_untranslated_english(target)
        if untranslated:
            issues.append(
                QCIssue(
                    cue_id=cue.id,
                    category="linguistic",
                    rule="untranslated_english",
                    severity="major",
                    score_impact=0.25,
                    message=f"Untranslated English words found: {', '.join(untranslated)}",
                )
            )
            score -= 0.25

        return issues, max(0.0, score)

    def _run_semantic_checks(
        self, cue: SubtitleCueModel, context_names: Optional[List[str]],
        prev_translation: Optional[str] = None,
    ) -> Tuple[List[QCIssue], float]:
        issues = []
        score = 1.0
        source = cue.clean_source_text
        target = cue.target_text or ""

        # Check 1: Number consistency (e.g. 5 in source vs target)
        src_numbers = set(re.findall(r"\b\d+\b", source))
        trg_numbers = set(re.findall(r"\b\d+\b", self.normalizer.normalize_digits(target)))
        
        if src_numbers and not src_numbers.issubset(trg_numbers):
            missing_nums = src_numbers - trg_numbers
            issues.append(
                QCIssue(
                    cue_id=cue.id,
                    category="semantic",
                    rule="number_inconsistency",
                    severity="critical",
                    score_impact=0.35,
                    message=f"Numbers missing or altered in translation: {', '.join(missing_nums)}",
                )
            )
            score -= 0.35

        # Check 2: Negation reversal check (e.g. "not" in source)
        has_src_negation = bool(re.search(r"\b(not|n't|never|no)\b", source, re.IGNORECASE))
        has_trg_negation = bool(re.search(r"(نە|نا|مە|نیت|نییە)", target))
        if has_src_negation and not has_trg_negation:
            issues.append(
                QCIssue(
                    cue_id=cue.id,
                    category="semantic",
                    rule="negation_reversal",
                    severity="critical",
                    score_impact=0.45,
                    message="Source contains negation but target translation might have lost it",
                )
            )
            score -= 0.45

        # Check 3: Question mark consistency
        src_has_question = "?" in source
        trg_has_question = "\u061F" in target or "?" in target  # ؟ or ?
        if src_has_question and not trg_has_question and len(target) > 2:
            issues.append(
                QCIssue(
                    cue_id=cue.id,
                    category="semantic",
                    rule="question_mark_missing",
                    severity="minor",
                    score_impact=0.10,
                    message="Source contains question mark but target translation is missing it",
                )
            )
            score -= 0.10

        # Check 4: Empty/placeholder/mock fallback detection
        if target.startswith("تەرجەمەی:") or target.startswith("تەرجەمەی :"):
            issues.append(
                QCIssue(
                    cue_id=cue.id,
                    category="semantic",
                    rule="mock_fallback_detected",
                    severity="critical",
                    score_impact=0.50,
                    message="Translation is a mock/fallback placeholder, not a real translation",
                )
            )
            score -= 0.50

        # Check 5: Length ratio anomaly
        if source and target and len(target) > 2:
            # Count actual characters (not whitespace/punctuation) for ratio
            src_alpha = len(re.findall(r'\w', source))
            trg_alpha = len([c for c in target if unicodedata.category(c).startswith('L')])
            if src_alpha > 3 and trg_alpha > 0:
                ratio = trg_alpha / src_alpha
                # Sorani is typically 0.5x to 2.0x English character count
                if ratio < 0.3:
                    issues.append(
                        QCIssue(
                            cue_id=cue.id,
                            category="semantic",
                            rule="length_ratio_too_short",
                            severity="major",
                            score_impact=0.20,
                            message=f"Translation suspiciously short (ratio: {ratio:.2f}). Possible omission.",
                        )
                    )
                    score -= 0.20
                elif ratio > 3.0:
                    issues.append(
                        QCIssue(
                            cue_id=cue.id,
                            category="semantic",
                            rule="length_ratio_too_long",
                            severity="minor",
                            score_impact=0.10,
                            message=f"Translation suspiciously long (ratio: {ratio:.2f}). Possible over-explanation.",
                        )
                    )
                    score -= 0.10

        # Check 6: Duplicate translation detection (same as previous cue)
        if prev_translation and target and target == prev_translation and len(target) > 5:
            issues.append(
                QCIssue(
                    cue_id=cue.id,
                    category="semantic",
                    rule="duplicate_translation",
                    severity="major",
                    score_impact=0.20,
                    message="Translation is identical to previous cue — possible copy error",
                )
            )
            score -= 0.20

        # Check 7: Proper noun preservation (names should appear transliterated)
        if context_names:
            for name in context_names:
                if name.lower() in source.lower() and len(name) > 2:
                    # Check if any transliteration of the name exists in target
                    # At minimum, the target should contain SOME non-generic text
                    if not target or len(target.strip()) < 3:
                        issues.append(
                            QCIssue(
                                cue_id=cue.id,
                                category="semantic",
                                rule="proper_noun_missing",
                                severity="major",
                                score_impact=0.15,
                                message=f"Character name '{name}' in source but target appears empty/truncated",
                            )
                        )
                        score -= 0.15

        return issues, max(0.0, score)
