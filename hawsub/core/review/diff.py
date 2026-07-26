"""
Kurdish Text Diff & Human Revision Analytics Engine.
Calculates word/character error rates (WER/CER), diff highlights, and feeds revisions back to Translation Memory.
"""

import difflib
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from hawsub.core.normalization.sorani import SoraniNormalizer


class DiffSummary(BaseModel):
    cue_id: int
    original_translation: str
    revised_translation: str
    word_error_rate: float
    character_error_rate: float
    diff_html: str
    has_changes: bool


class TranslationDiffEngine:
    """Computes character and word diffs between model output and human edits."""

    def __init__(self):
        self.normalizer = SoraniNormalizer()

    def compare_cues(self, cue_id: int, original: str, revised: str) -> DiffSummary:
        orig_norm = self.normalizer.normalize(original or "")
        rev_norm = self.normalizer.normalize(revised or "")

        has_changes = orig_norm != rev_norm
        if not has_changes:
            return DiffSummary(
                cue_id=cue_id,
                original_translation=orig_norm,
                revised_translation=rev_norm,
                word_error_rate=0.0,
                character_error_rate=0.0,
                diff_html=f"<span>{orig_norm}</span>",
                has_changes=False,
            )

        wer = self.compute_wer(orig_norm, rev_norm)
        cer = self.compute_cer(orig_norm, rev_norm)
        diff_html = self.generate_diff_html(orig_norm, rev_norm)

        return DiffSummary(
            cue_id=cue_id,
            original_translation=orig_norm,
            revised_translation=rev_norm,
            word_error_rate=wer,
            character_error_rate=cer,
            diff_html=diff_html,
            has_changes=True,
        )

    def compute_wer(self, reference: str, hypothesis: str) -> float:
        """Compute Word Error Rate using Levenshtein distance on words."""
        ref_words = reference.split()
        hyp_words = hypothesis.split()
        if not ref_words:
            return 1.0 if hyp_words else 0.0

        matcher = difflib.SequenceMatcher(None, ref_words, hyp_words)
        distance = sum(
            max(len(ref_words[i1:i2]), len(hyp_words[j1:j2]))
            for tag, i1, i2, j1, j2 in matcher.get_opcodes()
            if tag != "equal"
        )
        return round(min(1.0, distance / len(ref_words)), 3)

    def compute_cer(self, reference: str, hypothesis: str) -> float:
        """Compute Character Error Rate using Levenshtein distance on characters."""
        if not reference:
            return 1.0 if hypothesis else 0.0

        matcher = difflib.SequenceMatcher(None, reference, hypothesis)
        distance = sum(
            max(i2 - i1, j2 - j1)
            for tag, i1, i2, j1, j2 in matcher.get_opcodes()
            if tag != "equal"
        )
        return round(min(1.0, distance / len(reference)), 3)

    def generate_diff_html(self, reference: str, hypothesis: str) -> str:
        """Generate inline HTML with red deletions and green additions."""
        ref_words = reference.split()
        hyp_words = hypothesis.split()

        matcher = difflib.SequenceMatcher(None, ref_words, hyp_words)
        chunks = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                chunks.append(" ".join(ref_words[i1:i2]))
            elif tag == "replace":
                del_text = " ".join(ref_words[i1:i2])
                add_text = " ".join(hyp_words[j1:j2])
                chunks.append(f"<del style='background:#7f1d1d; color:#fca5a5;'>{del_text}</del> <ins style='background:#14532d; color:#86efac;'>{add_text}</ins>")
            elif tag == "delete":
                del_text = " ".join(ref_words[i1:i2])
                chunks.append(f"<del style='background:#7f1d1d; color:#fca5a5;'>{del_text}</del>")
            elif tag == "insert":
                add_text = " ".join(hyp_words[j1:j2])
                chunks.append(f"<ins style='background:#14532d; color:#86efac;'>{add_text}</ins>")

        return " ".join(chunks)
