"""
Subtitle Timestamp Synchronization & Non-Linear Drift Correction Engine.
Corrects subtitle timing offsets, frame-rate mismatches (e.g. 23.976 -> 25 fps), and linear time drift.
"""

from typing import List, Tuple, Optional
from hawsub.core.ingest.parser import SubtitleCueModel


class SubtitleSyncEngine:
    """Corrects linear time drift, fixed time offsets, and frame-rate conversion for subtitle cues."""

    @staticmethod
    def apply_offset(cues: List[SubtitleCueModel], offset_ms: int) -> List[SubtitleCueModel]:
        """Apply a uniform time shift (positive = delay, negative = advance)."""
        adjusted = []
        for cue in cues:
            new_start = max(0, cue.start_ms + offset_ms)
            new_end = max(new_start + 100, cue.end_ms + offset_ms)
            adjusted.append(
                SubtitleCueModel(
                    id=cue.id,
                    start_ms=new_start,
                    end_ms=new_end,
                    source_text=cue.source_text,
                    target_text=cue.target_text,
                    speaker=cue.speaker,
                    source_confidence=cue.source_confidence,
                )
            )
        return adjusted

    @staticmethod
    def convert_framerate(
        cues: List[SubtitleCueModel], source_fps: float, target_fps: float
    ) -> List[SubtitleCueModel]:
        """Stretch or compress timestamps to account for frame-rate differences (e.g. 23.976 fps -> 25.0 fps)."""
        if source_fps <= 0 or target_fps <= 0 or source_fps == target_fps:
            return cues

        ratio = source_fps / target_fps
        adjusted = []
        for cue in cues:
            new_start = int(cue.start_ms * ratio)
            new_end = int(cue.end_ms * ratio)
            adjusted.append(
                SubtitleCueModel(
                    id=cue.id,
                    start_ms=new_start,
                    end_ms=new_end,
                    source_text=cue.source_text,
                    target_text=cue.target_text,
                    speaker=cue.speaker,
                    source_confidence=cue.source_confidence,
                )
            )
        return adjusted

    @staticmethod
    def align_two_point_sync(
        cues: List[SubtitleCueModel],
        ref_point_1: Tuple[int, int],  # (original_cue_1_start_ms, actual_sync_1_start_ms)
        ref_point_2: Tuple[int, int],  # (original_cue_2_start_ms, actual_sync_2_start_ms)
    ) -> List[SubtitleCueModel]:
        """
        Perform 2-point linear regression sync correction to solve progressive drift.
        Computes slope (stretch factor) and intercept (fixed shift).
        """
        orig_1, sync_1 = ref_point_1
        orig_2, sync_2 = ref_point_2

        if orig_1 == orig_2:
            offset = sync_1 - orig_1
            return SubtitleSyncEngine.apply_offset(cues, offset)

        slope = (sync_2 - sync_1) / float(orig_2 - orig_1)
        intercept = sync_1 - (slope * orig_1)

        adjusted = []
        for cue in cues:
            new_start = max(0, int(slope * cue.start_ms + intercept))
            duration = cue.duration_ms
            new_end = new_start + int(duration * slope)

            adjusted.append(
                SubtitleCueModel(
                    id=cue.id,
                    start_ms=new_start,
                    end_ms=new_end,
                    source_text=cue.source_text,
                    target_text=cue.target_text,
                    speaker=cue.speaker,
                    source_confidence=cue.source_confidence,
                )
            )
        return adjusted
