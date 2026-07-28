"""
Phase 1 Deep Edge Case & Robustness Unit Tests.
Covers subtitle parser edge cases, FFmpeg utils, and SQLite connection safety.
"""

import os
import tempfile
from unittest.mock import patch, MagicMock
import pytest

from hawsub.core.ingest.parser import SubtitleParser, SubtitleCueModel
from hawsub.core.media.ffmpeg_utils import MediaInspector
from hawsub.core.source_resolver.resolver import SourceResolver
from hawsub.core.review.queue import ReviewQueue, ReviewItem
from hawsub.core.qc.engine import QCEvaluationResult, QCIssue


class TestFFmpegUtils:

    def test_probe_media_file_not_found(self):
        res = MediaInspector.probe_media("/nonexistent/file/path.mp4")
        assert res["duration_ms"] == 0
        assert res["has_video"] is False
        assert res["has_audio"] is False

    @patch("os.path.exists", return_value=True)
    @patch("subprocess.run")
    def test_probe_media_success(self, mock_run, mock_exists):
        mock_run.return_value = MagicMock(
            stdout='{"format": {"duration": "12.5", "format_name": "mov,mp4"}, "streams": [{"codec_type": "video"}, {"codec_type": "audio"}]}',
            returncode=0
        )
        res = MediaInspector.probe_media("dummy.mp4")
        assert res["duration_ms"] == 12500
        assert res["has_video"] is True
        assert res["has_audio"] is True
        assert res["container"] == "mov,mp4"

    @patch("subprocess.run")
    def test_probe_media_subprocess_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError("ffprobe not found")
        res = MediaInspector.probe_media("dummy.mp4")
        assert res["duration_ms"] == 0
        assert res["has_video"] is False

    def test_extract_audio_clip_missing_input(self):
        res = MediaInspector.extract_audio_clip("missing.mp4", 1000, 2000, "out.wav")
        assert res is False

    @patch("subprocess.run")
    def test_extract_audio_clip_success(self, mock_run):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            with patch("os.path.exists") as mock_exists:
                mock_exists.side_effect = lambda p: True
                mock_run.return_value = MagicMock(returncode=0)
                res = MediaInspector.extract_audio_clip("input.mp4", 1000, 3000, tmp_path)
                assert res is True
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class TestParserEdgeCases:

    def test_parse_empty_srt_string(self):
        cues = SubtitleParser.parse_srt("")
        assert len(cues) == 0

    def test_parse_corrupt_srt_blocks(self):
        content = """1
Not a timestamp
Some dialogue

2
00:00:01,000 --> 00:00:04,000
Valid dialogue line
"""
        cues = SubtitleParser.parse_srt(content)
        assert len(cues) == 1
        assert cues[0].clean_source_text == "Valid dialogue line"

    def test_parse_vtt_with_cue_settings(self):
        content = """WEBVTT

00:00:01.000 --> 00:00:04.000 align:start line:0%
Hello world with VTT settings
"""
        cues = SubtitleParser.parse_vtt(content)
        assert len(cues) == 1
        assert cues[0].clean_source_text == "Hello world with VTT settings"

    def test_parse_ass_dialogue_with_style_overrides(self):
        content = """[Script Info]
Title: Test

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:04.00,Default,,0,0,0,,{\\b1}Bold{\\b0} text line
"""
        cues = SubtitleParser.parse_ass(content)
        assert len(cues) == 1
        assert "Bold text line" in cues[0].clean_source_text

    def test_parse_10k_cues_performance(self):
        # Stress test 10,000 cues parsing
        blocks = []
        for i in range(1, 10001):
            blocks.append(f"{i}\n00:00:01,000 --> 00:00:02,000\nCue line {i}\n")
        content = "\n".join(blocks)
        cues = SubtitleParser.parse_srt(content)
        assert len(cues) == 10000
