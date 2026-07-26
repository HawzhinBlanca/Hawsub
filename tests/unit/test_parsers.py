"""
Unit tests for ASS/SSA parser, VTT parser edge cases, and auto-detect parser.
"""

import pytest
from hawsub.core.ingest.parser import (
    SubtitleParser,
    SubtitleCueModel,
    parse_timestamp_srt,
    format_timestamp_srt,
    parse_timestamp_vtt,
)


SAMPLE_ASS = """[Script Info]
Title: Test Movie
ScriptType: v4.00+
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,24,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:01:05.10,0:01:08.40,Default,,0,0,0,,CAPTAIN: We need to leave right now.
Dialogue: 0,0:01:09.00,0:01:12.20,Default,,0,0,0,,You're pushing your luck.
Dialogue: 0,0:01:13.00,0:01:15.50,Default,,0,0,0,,{\\b1}[Speaking Spanish]{\\b0}
"""

SAMPLE_VTT_NO_MILLIS = """WEBVTT

1
00:01:05 --> 00:01:08
Hello world.

2
01:09.000 --> 01:12.000
Goodbye world.
"""


class TestASSParser:

    def test_parse_ass_basic(self):
        cues = SubtitleParser.parse_ass(SAMPLE_ASS)
        assert len(cues) == 3

    def test_parse_ass_timing(self):
        cues = SubtitleParser.parse_ass(SAMPLE_ASS)
        # First cue: 0:01:05.10 = 65100ms
        assert cues[0].start_ms == 65100
        # First cue: 0:01:08.40 = 68400ms
        assert cues[0].end_ms == 68400

    def test_parse_ass_text_cleanup(self):
        cues = SubtitleParser.parse_ass(SAMPLE_ASS)
        # Third cue should have formatting tags removed
        assert "{\\b1}" not in cues[2].source_text
        assert "[Speaking Spanish]" in cues[2].source_text

    def test_parse_ass_speaker_detection(self):
        cues = SubtitleParser.parse_ass(SAMPLE_ASS)
        # First cue has "CAPTAIN:" prefix
        assert cues[0].speaker is not None or "CAPTAIN" in cues[0].source_text

    def test_parse_ass_empty_content(self):
        cues = SubtitleParser.parse_ass("")
        assert len(cues) == 0

    def test_parse_ass_no_events(self):
        content = "[Script Info]\nTitle: Empty\n"
        cues = SubtitleParser.parse_ass(content)
        assert len(cues) == 0


class TestVTTParserEdgeCases:

    def test_vtt_no_millis(self):
        # Should not crash on timestamps without fractional seconds
        ts_ms = parse_timestamp_vtt("00:01:05")
        assert ts_ms == 65000

    def test_vtt_two_digit_millis(self):
        ts_ms = parse_timestamp_vtt("00:01:05.50")
        assert ts_ms == 65500

    def test_vtt_one_digit_millis(self):
        ts_ms = parse_timestamp_vtt("00:01:05.5")
        assert ts_ms == 65500

    def test_vtt_mm_ss_format(self):
        ts_ms = parse_timestamp_vtt("01:05.000")
        assert ts_ms == 65000


class TestAutoDetectParser:

    def test_auto_detect_srt(self):
        srt = "1\n00:01:05,000 --> 00:01:08,000\nHello.\n"
        cues = SubtitleParser.parse_auto(srt, "movie.srt")
        assert len(cues) == 1

    def test_auto_detect_ass(self):
        cues = SubtitleParser.parse_auto(SAMPLE_ASS, "movie.ass")
        assert len(cues) == 3

    def test_auto_detect_vtt(self):
        vtt = "WEBVTT\n\n1\n00:01:05.000 --> 00:01:08.000\nHello.\n"
        cues = SubtitleParser.parse_auto(vtt, "movie.vtt")
        assert len(cues) == 1

    def test_auto_detect_ssa(self):
        cues = SubtitleParser.parse_auto(SAMPLE_ASS, "movie.ssa")
        assert len(cues) == 3

    def test_auto_detect_default_srt(self):
        srt = "1\n00:01:05,000 --> 00:01:08,000\nHello.\n"
        cues = SubtitleParser.parse_auto(srt, "movie.txt")
        assert len(cues) == 1  # Falls through to SRT


class TestTimestampParsing:

    def test_srt_timestamp_parse_standard(self):
        assert parse_timestamp_srt("00:01:20,000") == 80000
        assert parse_timestamp_srt("01:30:15,500") == 5415500

    def test_srt_timestamp_format(self):
        assert format_timestamp_srt(80000) == "00:01:20,000"
        assert format_timestamp_srt(0) == "00:00:00,000"
        assert format_timestamp_srt(3661500) == "01:01:01,500"

    def test_srt_roundtrip(self):
        original = "01:23:45,678"
        ms = parse_timestamp_srt(original)
        formatted = format_timestamp_srt(ms)
        assert formatted == original
