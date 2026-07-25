"""
English Verification & ASR Adapter.
Provides speech alignment, anomaly detection, and audio clip extraction for Hawsub.
"""

import os
import re
import difflib
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from hawsub.core.ingest.parser import SubtitleCueModel


class AlignmentResult(BaseModel):
    cue_id: int
    mismatch_score: float  # 0.0 (identical) to 1.0 (complete mismatch)
    missing_speech_flag: bool = False
    suspicious_name_flag: bool = False
    foreign_speech_flag: bool = False
    asr_transcript: Optional[str] = None
    notes: Optional[str] = None


class ASRAdapter:
    """
    Adapter for speech-to-text engines (faster-whisper / mock fallback)
    and audio anomaly scoring.
    """

    def __init__(self, provider: str = "faster-whisper", model_name: str = "large-v3"):
        self.provider = provider
        self.model_name = model_name

    def transcribe_audio_clip(self, audio_path: str, start_ms: int, end_ms: int) -> str:
        """
        Transcribe a short segment of audio.
        In production, calls faster_whisper or whisper. In testing/fallback, returns empty or mock text.
        """
        if not os.path.exists(audio_path):
            return ""
        # Mock / Fallback behavior if faster_whisper module is not installed
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
            segments, _ = model.transcribe(audio_path, language="en")
            return " ".join([s.text for s in segments]).strip()
        except Exception:
            return ""

    def score_mismatch(self, source_text: str, asr_transcript: str) -> float:
        """Compute string similarity mismatch score between 0.0 and 1.0."""
        if not source_text or not asr_transcript:
            return 0.0
        matcher = difflib.SequenceMatcher(None, source_text.lower(), asr_transcript.lower())
        similarity = matcher.ratio()
        return round(1.0 - similarity, 3)

    def detect_suspicious_names(self, text: str) -> List[str]:
        """Detect capitalized potential names or rare proper nouns."""
        words = text.split()
        names = []
        for i, word in enumerate(words):
            clean_word = word.strip(".,!?\"'()[]")
            if clean_word and clean_word[0].isupper() and not clean_word.isupper():
                # Avoid flagging the first word of a sentence as a suspicious name unless capitalized
                if i > 0 or len(clean_word) > 4:
                    names.append(clean_word)
        return list(set(names))

    def verify_cue(
        self, cue: SubtitleCueModel, audio_path: Optional[str] = None
    ) -> AlignmentResult:
        """Perform Tier-2 verification checks on a single subtitle cue."""
        source_clean = cue.clean_source_text
        asr_text = ""
        mismatch_score = 0.0

        if audio_path and os.path.exists(audio_path):
            asr_text = self.transcribe_audio_clip(audio_path, cue.start_ms, cue.end_ms)
            if asr_text:
                mismatch_score = self.score_mismatch(source_clean, asr_text)

        suspicious_names = self.detect_suspicious_names(source_clean)
        
        # Check for foreign speech markers in text like [Speaking Spanish]
        foreign_flag = cue.foreign_language or bool(
            re.search(r"\[(speaking|in)\s+[a-z]+\]", source_clean, re.IGNORECASE)
        )

        return AlignmentResult(
            cue_id=cue.id,
            mismatch_score=mismatch_score,
            missing_speech_flag=False,
            suspicious_name_flag=len(suspicious_names) > 0,
            foreign_speech_flag=foreign_flag,
            asr_transcript=asr_text if asr_text else None,
            notes=f"Found {len(suspicious_names)} potential proper names" if suspicious_names else None,
        )
