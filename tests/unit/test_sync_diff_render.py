"""
Unit tests for SubtitleSyncEngine and TranslationDiffEngine.
"""

import pytest
from hawsub.core.ingest.parser import SubtitleCueModel
from hawsub.core.media.sync import SubtitleSyncEngine
from hawsub.core.review.diff import TranslationDiffEngine


class TestSubtitleSyncEngine:

    def test_apply_offset_positive(self):
        cues = [SubtitleCueModel(id=1, start_ms=1000, end_ms=3000, source_text="Test")]
        shifted = SubtitleSyncEngine.apply_offset(cues, offset_ms=500)
        assert shifted[0].start_ms == 1500
        assert shifted[0].end_ms == 3500

    def test_apply_offset_negative(self):
        cues = [SubtitleCueModel(id=1, start_ms=1000, end_ms=3000, source_text="Test")]
        shifted = SubtitleSyncEngine.apply_offset(cues, offset_ms=-500)
        assert shifted[0].start_ms == 500
        assert shifted[0].end_ms == 2500

    def test_convert_framerate(self):
        cues = [SubtitleCueModel(id=1, start_ms=23976, end_ms=47952, source_text="Test")]
        converted = SubtitleSyncEngine.convert_framerate(cues, source_fps=23.976, target_fps=25.0)
        assert converted[0].start_ms < 23976

    def test_two_point_sync(self):
        cues = [
            SubtitleCueModel(id=1, start_ms=10000, end_ms=12000, source_text="First"),
            SubtitleCueModel(id=2, start_ms=50000, end_ms=52000, source_text="Second"),
        ]
        # Point 1: 10s -> 11s (+1s shift), Point 2: 50s -> 55s (+5s shift, stretch)
        synced = SubtitleSyncEngine.align_two_point_sync(cues, (10000, 11000), (50000, 55000))
        assert synced[0].start_ms == 11000
        assert synced[1].start_ms == 55000


class TestTranslationDiffEngine:

    def test_no_changes_diff(self):
        engine = TranslationDiffEngine()
        diff = engine.compare_cues(1, "سڵاو هاوڕێم", "سڵاو هاوڕێم")
        assert diff.has_changes is False
        assert diff.word_error_rate == 0.0

    def test_word_change_diff(self):
        engine = TranslationDiffEngine()
        diff = engine.compare_cues(1, "سڵاو باشیت", "سڵاو هاوڕێم")
        assert diff.has_changes is True
        assert diff.word_error_rate > 0.0
        assert "<del" in diff.diff_html
        assert "<ins" in diff.diff_html

    def test_compute_wer(self):
        engine = TranslationDiffEngine()
        wer = engine.compute_wer("hello my friend", "hello my dear friend")
        assert 0.0 < wer < 1.0
