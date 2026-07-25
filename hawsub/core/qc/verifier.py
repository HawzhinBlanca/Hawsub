"""
Second-Model Verifier & Consensus Arbitrator.
Performs dual-model verification for uncertain lines or critical flags without silent overwrites.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from hawsub.core.ingest.parser import SubtitleCueModel
from hawsub.core.qc.engine import QCEvaluationResult, QCIssue
from hawsub.providers.base import SemanticModel, VerificationResponse


class VerificationAuditRecord(BaseModel):
    cue_id: int
    primary_translation: str
    verifier_decision: str  # agree | disagree | uncertain
    verifier_severity: str
    reason: str
    alternative_translation: Optional[str] = None
    override_applied: bool = False
    escalated_to_human: bool = False


class SecondModelVerifier:
    """Invokes a secondary model for verification when primary confidence is low or critical flags exist."""

    def __init__(self, verifier_model: SemanticModel, trigger_threshold: float = 0.88):
        self.verifier_model = verifier_model
        self.trigger_threshold = trigger_threshold

    def verify_cue_if_needed(
        self,
        cue: SubtitleCueModel,
        qc_result: QCEvaluationResult,
        meaning_summary: str = "",
        context_data: Optional[Dict[str, Any]] = None,
    ) -> VerificationAuditRecord:
        has_critical = any(i.severity == "critical" for i in qc_result.issues)
        needs_verification = (qc_result.overall_confidence < self.trigger_threshold) or has_critical

        if not needs_verification:
            return VerificationAuditRecord(
                cue_id=cue.id,
                primary_translation=cue.target_text or "",
                verifier_decision="agree",
                verifier_severity="none",
                reason="Primary confidence high, verification skipped",
                override_applied=False,
                escalated_to_human=False,
            )

        # Call secondary verifier model
        v_response: VerificationResponse = self.verifier_model.verify_translation(
            source_text=cue.clean_source_text,
            current_translation=cue.target_text or "",
            meaning=meaning_summary,
            context_data=context_data or {},
        )

        escalate = v_response.decision in ["disagree", "uncertain"] or v_response.severity in ["major", "critical"]

        return VerificationAuditRecord(
            cue_id=cue.id,
            primary_translation=cue.target_text or "",
            verifier_decision=v_response.decision,
            verifier_severity=v_response.severity,
            reason=v_response.reason,
            alternative_translation=v_response.alternative,
            override_applied=False,  # Never overwrite primary translation silently
            escalated_to_human=escalate,
        )
