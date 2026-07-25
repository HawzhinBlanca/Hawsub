"""
Human Exception Review Queue & Decision Store.
Manages flagged subtitle cues requiring professional human approval or edit.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from hawsub.core.ingest.parser import SubtitleCueModel
from hawsub.core.qc.engine import QCEvaluationResult
from hawsub.core.qc.verifier import VerificationAuditRecord


class ReviewItem(BaseModel):
    cue_id: int
    source_text: str
    target_text: str
    alternative_text: Optional[str] = None
    scene_id: str
    overall_confidence: float
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    verifier_notes: Optional[str] = None
    status: str = "pending"  # pending | accepted | edited | rejected


class ReviewDecisionModel(BaseModel):
    cue_id: int
    reviewer: str = "human_editor"
    action: str  # accept | edit | choose_alternative | rerun | add_to_glossary | mark_source_wrong
    previous_text: str
    approved_text: str
    notes: Optional[str] = None


class ReviewQueue:
    """Manages flagged exception items and applies human reviewer decisions."""

    def __init__(self):
        self.pending_items: Dict[int, ReviewItem] = {}
        self.decisions: Dict[int, ReviewDecisionModel] = {}

    def add_cue_for_review(
        self,
        cue: SubtitleCueModel,
        qc_result: QCEvaluationResult,
        scene_id: str,
        audit_record: Optional[VerificationAuditRecord] = None,
    ) -> None:
        alt_text = audit_record.alternative_translation if audit_record else None
        v_notes = audit_record.reason if audit_record else None
        
        issue_dicts = [i.model_dump() for i in qc_result.issues]

        item = ReviewItem(
            cue_id=cue.id,
            source_text=cue.clean_source_text,
            target_text=cue.target_text or "",
            alternative_text=alt_text,
            scene_id=scene_id,
            overall_confidence=qc_result.overall_confidence,
            issues=issue_dicts,
            verifier_notes=v_notes,
            status="pending",
        )
        self.pending_items[cue.id] = item

    def get_pending_items(self, severity_filter: Optional[str] = None) -> List[ReviewItem]:
        items = list(self.pending_items.values())
        if severity_filter:
            filtered = []
            for item in items:
                severities = [i.get("severity") for i in item.issues]
                if severity_filter in severities:
                    filtered.append(item)
            return filtered
        return items

    def apply_decision(
        self,
        cue: SubtitleCueModel,
        action: str,
        approved_text: Optional[str] = None,
        reviewer: str = "human_editor",
        notes: Optional[str] = None,
    ) -> SubtitleCueModel:
        prev_text = cue.target_text or ""
        final_text = approved_text if approved_text is not None else prev_text

        if action == "accept":
            final_text = prev_text
        elif action == "choose_alternative":
            pending = self.pending_items.get(cue.id)
            if pending and pending.alternative_text:
                final_text = pending.alternative_text

        cue.target_text = final_text

        decision = ReviewDecisionModel(
            cue_id=cue.id,
            reviewer=reviewer,
            action=action,
            previous_text=prev_text,
            approved_text=final_text,
            notes=notes,
        )
        self.decisions[cue.id] = decision

        if cue.id in self.pending_items:
            self.pending_items[cue.id].status = "accepted" if action == "accept" else "edited"

        return cue
