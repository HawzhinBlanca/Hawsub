"""
Phase 4-5 Production Hardening Tests:
  - Logging module (JSONFormatter, setup_logger)
  - Exporter edge cases
  - Cost budget edge cases
  - Pipeline checkpoint edge cases
  - Normalizer edge cases
  - Provider cache
"""

import json
import logging
import os
import sqlite3
import tempfile
import pytest

from hawsub.utils.logging import JSONFormatter, setup_logger
from hawsub.core.export.exporters import (
    SubtitleExporter, format_timestamp_ass, format_timestamp_vtt
)
from hawsub.core.ingest.parser import (
    SubtitleParser, SubtitleCueModel, parse_timestamp_srt,
    parse_timestamp_vtt, format_timestamp_srt
)
from hawsub.core.cost.budget import TokenBudget, CostEstimate, MODEL_COSTS
from hawsub.core.normalization.sorani import SoraniNormalizer
from hawsub.providers.cache import CachedSemanticModel


# ──────────────────────────────────────────────────────────────────────────────
# Logging Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestJSONFormatter:

    def test_basic_format(self):
        """JSONFormatter produces valid JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="test.py", lineno=1,
            msg="Test message", args=(), exc_info=None
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Test message"
        assert parsed["logger"] == "test"

    def test_format_with_extra_fields(self):
        """JSONFormatter includes extra fields when present."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="hawsub", level=logging.WARNING,
            pathname="pipeline.py", lineno=10,
            msg="Scene processing", args=(), exc_info=None
        )
        record.project_id = "movie_001"
        record.stage = "TRANSLATION"
        record.scene_id = "scene_3"
        record.provider = "google"
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["project_id"] == "movie_001"
        assert parsed["stage"] == "TRANSLATION"
        assert parsed["scene_id"] == "scene_3"
        assert parsed["provider"] == "google"

    def test_format_with_exception(self):
        """JSONFormatter includes exception info."""
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test", level=logging.ERROR,
                pathname="test.py", lineno=1,
                msg="Error occurred", args=(), exc_info=exc_info
            )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]


class TestSetupLogger:

    def test_default_logger(self):
        """Default logger uses standard formatting."""
        logger = setup_logger("test_default_1234", level=logging.DEBUG)
        assert logger.name == "test_default_1234"
        assert logger.level == logging.DEBUG

    def test_json_logger(self):
        """JSON-enabled logger uses JSONFormatter."""
        logger = setup_logger("test_json_9876", json_format=True)
        assert len(logger.handlers) > 0
        assert isinstance(logger.handlers[-1].formatter, JSONFormatter)

    def test_no_duplicate_handlers(self):
        """Calling setup_logger twice doesn't add duplicate handlers."""
        logger = setup_logger("test_dup_5678")
        handler_count = len(logger.handlers)
        setup_logger("test_dup_5678")
        assert len(logger.handlers) == handler_count


# ──────────────────────────────────────────────────────────────────────────────
# Exporter Edge Cases
# ──────────────────────────────────────────────────────────────────────────────

class TestExporterFormats:

    def test_format_timestamp_ass(self):
        assert format_timestamp_ass(0) == "0:00:00.00"
        assert format_timestamp_ass(1000) == "0:00:01.00"
        assert format_timestamp_ass(3661500) == "1:01:01.50"
        assert format_timestamp_ass(150) == "0:00:00.15"

    def test_format_timestamp_vtt(self):
        assert format_timestamp_vtt(0) == "00:00:00.000"
        assert format_timestamp_vtt(1500) == "00:00:01.500"
        assert format_timestamp_vtt(3661500) == "01:01:01.500"

    def test_export_vtt(self, tmp_path):
        cues = [
            SubtitleCueModel(id=1, start_ms=1000, end_ms=3000, source_text="Hello", target_text="سڵاو"),
            SubtitleCueModel(id=2, start_ms=4000, end_ms=6000, source_text="Bye", target_text="ماڵئاوا"),
        ]
        path = str(tmp_path / "test.vtt")
        SubtitleExporter.export_vtt(cues, path)
        content = open(path, "r", encoding="utf-8").read()
        assert "WEBVTT" in content
        assert "سڵاو" in content
        assert "ماڵئاوا" in content

    def test_export_ass(self, tmp_path):
        cues = [
            SubtitleCueModel(id=1, start_ms=1000, end_ms=3000, source_text="Hello", target_text="سڵاو"),
        ]
        path = str(tmp_path / "test.ass")
        SubtitleExporter.export_ass(cues, path, title="Test Movie")
        content = open(path, "r", encoding="utf-8").read()
        assert "Test Movie" in content
        assert "[Events]" in content
        assert "Dialogue:" in content
        assert "سڵاو" in content

    def test_export_srt(self, tmp_path):
        cues = [
            SubtitleCueModel(id=1, start_ms=0, end_ms=2500, source_text="Test", target_text="تاقیکردنەوە"),
        ]
        path = str(tmp_path / "test.srt")
        SubtitleExporter.export_srt(cues, path)
        content = open(path, "r", encoding="utf-8").read()
        assert "00:00:00,000" in content
        assert "تاقیکردنەوە" in content


# ──────────────────────────────────────────────────────────────────────────────
# Parser Edge Cases
# ──────────────────────────────────────────────────────────────────────────────

class TestParserEdgeCases:

    def test_srt_without_sequence_numbers(self):
        """SRT files sometimes omit sequence numbers."""
        content = """00:00:01,000 --> 00:00:03,500
Hello there.

00:00:04,000 --> 00:00:06,200
How are you?
"""
        cues = SubtitleParser.parse_srt(content)
        assert len(cues) == 2
        assert cues[0].source_text == "Hello there."

    def test_vtt_minimal(self):
        """Minimal valid VTT file."""
        content = """WEBVTT

00:00:01.000 --> 00:00:03.500
Hello
"""
        cues = SubtitleParser.parse_vtt(content)
        assert len(cues) == 1
        assert cues[0].source_text == "Hello"

    def test_vtt_mm_ss_format(self):
        """VTT with MM:SS.mmm format (no hours)."""
        content = """WEBVTT

01:30.000 --> 01:35.000
Short format
"""
        cues = SubtitleParser.parse_vtt(content)
        assert len(cues) == 1
        assert cues[0].start_ms == 90000  # 1:30 = 90s

    def test_parse_auto_vtt(self):
        content = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello\n"
        cues = SubtitleParser.parse_auto(content, "test.vtt")
        assert len(cues) == 1

    def test_parse_auto_ass(self):
        content = """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Hello
"""
        cues = SubtitleParser.parse_auto(content, "test.ass")
        assert len(cues) == 1

    def test_parse_auto_unknown_extension(self):
        """Unknown extension defaults to SRT."""
        content = "1\n00:00:01,000 --> 00:00:03,000\nHello\n"
        cues = SubtitleParser.parse_auto(content, "test.xyz")
        assert len(cues) == 1

    def test_srt_bom(self):
        """SRT with UTF-8 BOM."""
        content = "\ufeff1\n00:00:01,000 --> 00:00:03,000\nHello\n"
        cues = SubtitleParser.parse_srt(content)
        assert len(cues) == 1

    def test_vtt_bom(self):
        """VTT with UTF-8 BOM."""
        content = "\ufeffWEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello\n"
        cues = SubtitleParser.parse_vtt(content)
        assert len(cues) == 1

    def test_ass_bom(self):
        """ASS with UTF-8 BOM."""
        content = """\ufeff[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Hello
"""
        cues = SubtitleParser.parse_ass(content)
        assert len(cues) == 1

    def test_srt_multiline_text(self):
        """SRT with multi-line subtitle text."""
        content = """1
00:00:01,000 --> 00:00:03,000
Line one
Line two
"""
        cues = SubtitleParser.parse_srt(content)
        assert len(cues) == 1
        assert "Line one\nLine two" == cues[0].source_text

    def test_ass_line_breaks(self):
        """ASS \\N line breaks converted to newlines."""
        content = """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Line one\\NLine two
"""
        cues = SubtitleParser.parse_ass(content)
        assert len(cues) == 1
        assert "\n" in cues[0].source_text

    def test_timestamp_parsing_edge_cases(self):
        """Timestamp edge cases: 2-digit millis, 1-digit millis."""
        assert parse_timestamp_srt("00:00:01,50") == 1500
        assert parse_timestamp_srt("00:00:01,5") == 1500
        assert parse_timestamp_srt("00:00:01.500") == 1500  # dot instead of comma

    def test_empty_blocks_skipped(self):
        """Empty blocks in SRT are skipped."""
        content = """1
00:00:01,000 --> 00:00:03,000
Hello



2
00:00:04,000 --> 00:00:06,000
World
"""
        cues = SubtitleParser.parse_srt(content)
        assert len(cues) == 2


# ──────────────────────────────────────────────────────────────────────────────
# Cost Budget Edge Cases  
# ──────────────────────────────────────────────────────────────────────────────

class TestTokenBudgetEdgeCases:

    def test_budget_exceeded_warning(self):
        """Record usage that exceeds budget."""
        tb = TokenBudget(max_cost_usd=0.001, model_name="gpt-4o")
        tb.record_usage(10000, 5000)
        assert tb.total_cost_usd > 0
        assert tb.remaining_budget_usd == 0.0  # clamped

    def test_check_budget_false(self):
        """check_budget returns False when exceeded."""
        tb = TokenBudget(max_cost_usd=0.001, model_name="gpt-4o")
        tb.record_usage(10000, 5000)
        assert tb.check_budget(0.01) is False

    def test_default_model_fallback(self):
        """Unknown model uses default pricing."""
        tb = TokenBudget(model_name="unknown-model-xyz")
        costs = tb._get_model_cost()
        assert costs == MODEL_COSTS["_default"]

    def test_estimate_scene_cost(self):
        """Estimate cost for a scene batch."""
        tb = TokenBudget(model_name="gemini-2.5-flash")
        cost = tb.estimate_scene_cost([
            {"source_text": "Hello there"},
            {"source_text": "How are you doing today?"},
        ])
        assert cost > 0
        assert cost < 0.01  # Should be very cheap

    def test_api_calls_tracking(self):
        tb = TokenBudget()
        assert tb.api_calls == 0
        tb.record_usage(100, 50)
        assert tb.api_calls == 1
        tb.record_usage(200, 100)
        assert tb.api_calls == 2


# ──────────────────────────────────────────────────────────────────────────────
# Normalizer Edge Cases
# ──────────────────────────────────────────────────────────────────────────────

class TestNormalizerEdgeCases:

    def test_normalize_empty(self):
        norm = SoraniNormalizer()
        assert norm.normalize("") == ""

    def test_normalize_with_digits(self):
        norm = SoraniNormalizer(convert_arabic_digits=True)
        result = norm.normalize("٢٠٢٦")
        assert result == "2026"

    def test_normalize_with_rtl_marks(self):
        norm = SoraniNormalizer(add_rtl_marks=True)
        result = norm.normalize("سڵاو")
        assert result.startswith("\u200F")
        assert result.endswith("\u200F")

    def test_normalize_caching(self):
        norm = SoraniNormalizer()
        result1 = norm.normalize("سڵاو")
        result2 = norm.normalize("سڵاو")
        assert result1 == result2
        assert "سڵاو" in norm._cache

    def test_tatweel_removal(self):
        norm = SoraniNormalizer()
        # ـ is tatweel
        result = norm.normalize_unicode_chars("سـڵاو")
        assert "\u0640" not in result

    def test_arabic_kaf_to_kurdish(self):
        norm = SoraniNormalizer()
        result = norm.normalize_unicode_chars("كوردي")  # Arabic kaf
        assert result[0] == "ک"  # Kurdish kaf

    def test_punctuation_normalization_arabic_text(self):
        norm = SoraniNormalizer()
        result = norm.normalize_punctuation_marks("سڵاو?")
        assert "؟" in result

    def test_punctuation_normalization_no_arabic(self):
        """Non-Arabic text shouldn't get Arabic punctuation."""
        norm = SoraniNormalizer()
        result = norm.normalize_punctuation_marks("Hello?")
        assert "?" in result  # Should stay as English ?

    def test_normalize_digits_persian(self):
        norm = SoraniNormalizer()
        result = norm.normalize_digits("۱۲۳۴۵")
        assert result == "12345"

    def test_multiple_question_marks(self):
        norm = SoraniNormalizer()
        result = norm.normalize_punctuation_marks("سڵاو؟؟؟")
        assert result.count("؟") == 1

    def test_multiple_exclamation_marks(self):
        norm = SoraniNormalizer()
        result = norm.normalize_punctuation_marks("سڵاو!!!")
        assert result.count("!") == 1


# ──────────────────────────────────────────────────────────────────────────────
# Provider Cache
# ──────────────────────────────────────────────────────────────────────────────

class TestProviderCache:

    def test_cached_model_hit(self, tmp_path):
        """CachedSemanticModel returns cached results for duplicate inputs."""
        from hawsub.providers.mock import MockSemanticModel
        mock = MockSemanticModel()
        cached = CachedSemanticModel(mock, cache_dir=str(tmp_path / ".cache"))

        result1 = cached.translate_scene(
            scene_id="s1",
            cues_data=[{"id": 1, "source_text": "Hello"}],
            interpretations=None,
            context_data={},
        )
        result2 = cached.translate_scene(
            scene_id="s1",
            cues_data=[{"id": 1, "source_text": "Hello"}],
            interpretations=None,
            context_data={},
        )
        # Should get same result
        assert result1.translations[0].translation == result2.translations[0].translation
