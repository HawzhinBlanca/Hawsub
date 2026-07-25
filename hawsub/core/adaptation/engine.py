"""
Subtitle Adaptation Engine.
Calculates technical readability metrics (CPS, CPL, duration, gaps, line breaking)
and applies adaptation strategies (concise rewrite, selective retiming, semantic line breaks).
"""

import re
from typing import List, Tuple, Optional
from pydantic import BaseModel, Field
from hawsub.core.ingest.parser import SubtitleCueModel
from hawsub.config.schema import QCProfile


class AdaptationMetrics(BaseModel):
    cue_id: int
    duration_ms: int
    char_count: int
    line_count: int
    cps: float
    max_cpl: int
    gap_to_next_ms: Optional[int] = None
    cps_exceeded: bool = False
    cpl_exceeded: bool = False
    lines_exceeded: bool = False
    duration_too_short: bool = False
    gap_too_short: bool = False


class AdaptationEngine:
    """Evaluates and adapts translated target subtitles for visual readability."""

    def __init__(self, profile: Optional[QCProfile] = None):
        self.profile = profile or QCProfile()

    def compute_metrics(
        self, cue: SubtitleCueModel, next_cue: Optional[SubtitleCueModel] = None
    ) -> AdaptationMetrics:
        text = cue.target_text or cue.source_text
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        
        char_count = sum(len(l) for l in lines)
        line_count = len(lines)
        duration_ms = cue.duration_ms
        duration_sec = max(0.1, duration_ms / 1000.0)

        cps = round(char_count / duration_sec, 2)
        max_cpl = max((len(l) for l in lines), default=0)

        gap_ms = None
        if next_cue:
            gap_ms = next_cue.start_ms - cue.end_ms

        cps_exceeded = cps > self.profile.hard_max_cps
        cpl_exceeded = max_cpl > self.profile.hard_max_cpl
        lines_exceeded = line_count > self.profile.max_lines
        duration_too_short = duration_ms < self.profile.min_duration_ms
        gap_too_short = gap_ms is not None and gap_ms < self.profile.min_gap_ms

        return AdaptationMetrics(
            cue_id=cue.id,
            duration_ms=duration_ms,
            char_count=char_count,
            line_count=line_count,
            cps=cps,
            max_cpl=max_cpl,
            gap_to_next_ms=gap_ms,
            cps_exceeded=cps_exceeded,
            cpl_exceeded=cpl_exceeded,
            lines_exceeded=lines_exceeded,
            duration_too_short=duration_too_short,
            gap_too_short=gap_too_short,
        )

    def format_semantic_line_breaks(self, text: str, max_cpl: Optional[int] = None) -> str:
        """Break long single line into 2 balanced lines at natural clause/punctuation boundaries."""
        target_cpl = max_cpl or self.profile.preferred_cpl
        text = text.replace("\n", " ").strip()
        
        if len(text) <= target_cpl:
            return text

        # Look for natural splitting points: comma (،), conjunctions, punctuation
        words = text.split()
        if len(words) <= 2:
            return text

        mid = len(text) // 2
        best_break_idx = -1
        min_diff = 999

        current_len = 0
        for idx, word in enumerate(words[:-1]):
            current_len += len(word) + 1
            diff = abs(current_len - mid)

            # Bonus for breaking after punctuation
            if word.endswith("،") or word.endswith("؛") or word.endswith("."):
                diff -= 5

            if diff < min_diff:
                min_diff = diff
                best_break_idx = idx

        if best_break_idx != -1:
            line1 = " ".join(words[: best_break_idx + 1])
            line2 = " ".join(words[best_break_idx + 1:])
            return f"{line1}\n{line2}"

        return text

    def apply_selective_retiming(
        self, cue: SubtitleCueModel, next_cue: Optional[SubtitleCueModel] = None
    ) -> SubtitleCueModel:
        """Extend cue end_ms if CPS is high and there is safe gap before next_cue."""
        metrics = self.compute_metrics(cue, next_cue)
        if not metrics.cps_exceeded:
            return cue

        # Required duration in ms for preferred CPS
        required_ms = int((metrics.char_count / self.profile.preferred_cps) * 1000)
        needed_extension_ms = required_ms - cue.duration_ms

        if needed_extension_ms <= 0:
            return cue

        max_extension = needed_extension_ms
        if next_cue:
            max_safe_gap = (next_cue.start_ms - cue.end_ms) - self.profile.min_gap_ms
            max_extension = min(needed_extension_ms, max(0, max_safe_gap))

        if max_extension > 0:
            cue.end_ms += max_extension

        return cue
