"""
Hardening Tests — Input validation, error handling, edge cases, and robustness.
"""

import os
import json
import pytest
import tempfile
from pathlib import Path

from hawsub.core.ingest.parser import SubtitleParser, SubtitleCueModel, parse_timestamp_srt, parse_timestamp_vtt
from hawsub.core.normalization.sorani import SoraniNormalizer
from hawsub.core.routing.foreign_dialogue import ForeignDialogueRouter
from hawsub.core.export.exporters import SubtitleExporter
from hawsub.core.qc.engine import QCEngine, QCEvaluationResult
from hawsub.core.adaptation.engine import AdaptationEngine
from hawsub.core.orchestration.pipeline import DurablePipeline
from hawsub.config.loader import load_config
from hawsub.config.schema import HawsubConfig
from hawsub.providers.factory import get_provider


# ─── Input Validation ─────────────────────────────────────────────────────────

class TestInputValidation:

    def test_pipeline_empty_file_raises(self, tmp_path):
        """Empty input file should raise ValueError."""
        f = tmp_path / "empty.srt"
        f.write_text("")
        pipeline = DurablePipeline(project_id="empty_test", db_path=str(tmp_path / "t.db"))
        with pytest.raises(ValueError, match="empty"):
            pipeline.process_file(str(f), output_dir=str(tmp_path / "out"))

    def test_pipeline_missing_file_raises(self, tmp_path):
        """Missing input file should raise FileNotFoundError."""
        pipeline = DurablePipeline(project_id="missing_test", db_path=str(tmp_path / "t.db"))
        with pytest.raises(FileNotFoundError):
            pipeline.process_file(str(tmp_path / "nonexistent.srt"), output_dir=str(tmp_path / "out"))

    def test_pipeline_whitespace_only_file_raises(self, tmp_path):
        """Whitespace-only file should raise ValueError."""
        f = tmp_path / "spaces.srt"
        f.write_text("   \n\n  \n ")
        pipeline = DurablePipeline(project_id="space_test", db_path=str(tmp_path / "t.db"))
        with pytest.raises(ValueError, match="no content|No subtitle"):
            pipeline.process_file(str(f), output_dir=str(tmp_path / "out"))

    def test_pipeline_bom_file_parses(self, tmp_path):
        """BOM-prefixed UTF-8 file should parse correctly when read with utf-8-sig."""
        srt = "1\n00:00:01,000 --> 00:00:04,000\nHello BOM world.\n\n2\n00:00:05,000 --> 00:00:08,000\nSecond cue.\n"
        f = tmp_path / "bom.srt"
        # Write with BOM prefix
        with open(str(f), "w", encoding="utf-8-sig") as fh:
            fh.write(srt)
        # Verify reading with utf-8-sig strips the BOM
        with open(str(f), "r", encoding="utf-8-sig") as fh:
            content = fh.read()
        from hawsub.core.ingest.parser import SubtitleParser
        cues = SubtitleParser.parse_srt(content)
        assert len(cues) == 2
        assert cues[0].source_text == "Hello BOM world."
        assert cues[1].source_text == "Second cue."

    def test_parser_handles_bom_in_content(self):
        """Parser should handle BOM character in raw content string."""
        content = "\ufeff1\n00:00:01,000 --> 00:00:04,000\nBOM test.\n"
        from hawsub.core.ingest.parser import SubtitleParser
        cues = SubtitleParser.parse_srt(content)
        assert len(cues) == 1
        assert cues[0].source_text == "BOM test."


# ─── Parser Edge Cases ────────────────────────────────────────────────────────

class TestParserEdgeCases:

    def test_srt_with_extra_whitespace(self):
        """SRT with extra blank lines between blocks."""
        content = "\n\n1\n00:00:01,000 --> 00:00:03,000\nHello\n\n\n\n2\n00:00:04,000 --> 00:00:06,000\nWorld\n\n\n"
        cues = SubtitleParser.parse_srt(content)
        assert len(cues) == 2

    def test_srt_malformed_timestamp_skips(self):
        """SRT with malformed block should skip it gracefully."""
        content = "1\n00:00:01,000 --> 00:00:03,000\nGood\n\n2\nBAD TIMESTAMP\nSkipped\n\n3\n00:00:05,000 --> 00:00:07,000\nAlso good\n"
        cues = SubtitleParser.parse_srt(content)
        assert len(cues) == 2
        assert cues[0].source_text == "Good"
        assert cues[1].source_text == "Also good"

    def test_vtt_with_styles_block(self):
        """VTT with STYLE block should not crash."""
        content = "WEBVTT\n\nSTYLE\n::cue { color: white; }\n\n00:00:01.000 --> 00:00:03.000\nHello VTT\n"
        cues = SubtitleParser.parse_vtt(content)
        assert len(cues) >= 1

    def test_ass_with_no_format_line(self):
        """ASS with missing Format line should use default fields."""
        content = """[Script Info]
Title: Test

[Events]
Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Hello ASS no format
"""
        cues = SubtitleParser.parse_ass(content)
        assert len(cues) == 1
        assert "Hello ASS no format" in cues[0].source_text

    def test_srt_speaker_label_extraction(self):
        """Speaker labels should be extracted from SRT cues."""
        content = "1\n00:00:01,000 --> 00:00:03,000\nJOHN: This is my line\n"
        cues = SubtitleParser.parse_srt(content)
        assert cues[0].speaker == "JOHN"

    def test_srt_multiline_text(self):
        """Multi-line SRT text should preserve newlines."""
        content = "1\n00:00:01,000 --> 00:00:04,000\nLine one\nLine two\n"
        cues = SubtitleParser.parse_srt(content)
        assert "\n" in cues[0].source_text

    def test_timestamp_srt_invalid_format(self):
        """Invalid SRT timestamp format should raise."""
        with pytest.raises(ValueError):
            parse_timestamp_srt("invalid")

    def test_timestamp_vtt_invalid_format(self):
        """Invalid VTT timestamp format should raise."""
        with pytest.raises(ValueError):
            parse_timestamp_vtt("bad:timestamp")

    def test_parse_auto_unknown_extension(self):
        """Unknown extension should default to SRT parsing."""
        content = "1\n00:00:01,000 --> 00:00:03,000\nTest\n"
        cues = SubtitleParser.parse_auto(content, "file.xyz")
        assert len(cues) == 1

    def test_cue_clean_source_text_strips_tags(self):
        """clean_source_text should strip HTML-like tags."""
        cue = SubtitleCueModel(id=1, start_ms=0, end_ms=1000, source_text="<i>Italic</i> text")
        assert cue.clean_source_text == "Italic text"

    def test_cue_duration_ms_never_negative(self):
        """duration_ms should never be negative even with inverted times."""
        cue = SubtitleCueModel(id=1, start_ms=5000, end_ms=3000, source_text="Inverted")
        assert cue.duration_ms == 0


# ─── Normalizer Robustness ────────────────────────────────────────────────────

class TestNormalizerRobustness:

    def test_normalize_empty_string(self):
        norm = SoraniNormalizer()
        assert norm.normalize("") == ""

    def test_normalize_pure_english(self):
        norm = SoraniNormalizer()
        result = norm.normalize("Hello World")
        assert result == "Hello World"

    def test_normalize_mixed_script(self):
        norm = SoraniNormalizer()
        result = norm.normalize("ئەمە test يە")
        assert "ی" in result  # Arabic ya converted
        assert "test" in result  # English preserved

    def test_untranslated_english_allowlist(self):
        """Common abbreviations should not be flagged."""
        norm = SoraniNormalizer()
        assert norm.detect_untranslated_english("ئەم TV یە") == []
        assert norm.detect_untranslated_english("بۆ Facebook") == []
        assert norm.detect_untranslated_english("email ئەوە") == []

    def test_untranslated_english_catches_real_words(self):
        """Actual untranslated English should be flagged."""
        norm = SoraniNormalizer()
        result = norm.detect_untranslated_english("ئەمە adventure یە")
        assert "adventure" in result

    def test_kurmanji_contamination_detects_all(self):
        """All Kurmanji Latin characters should be detected."""
        norm = SoraniNormalizer()
        for char in "êîûşçÊÎÛŞÇ":
            found = norm.detect_kurmanji_contamination(f"test{char}test")
            assert char in found

    def test_digit_normalization(self):
        """Arabic and Persian digits should normalize to ASCII."""
        norm = SoraniNormalizer()
        assert norm.normalize_digits("٠١٢") == "012"
        assert norm.normalize_digits("۰۱۲") == "012"
        assert norm.normalize_digits("mixed٣ and ۴") == "mixed3 and 4"

    def test_rtl_safety_marks(self):
        """RTL marks should be applied correctly."""
        norm = SoraniNormalizer(add_rtl_marks=True)
        result = norm.normalize("سڵاو")
        assert result.startswith("\u200F")
        assert result.endswith("\u200F")

    def test_tatweel_removal(self):
        """Tatweel character should be removed."""
        norm = SoraniNormalizer()
        result = norm.normalize_unicode_chars("سـڵاو")
        assert "\u0640" not in result


# ─── Foreign Routing Robustness ───────────────────────────────────────────────

class TestForeignRoutingRobustness:

    def test_new_languages(self):
        """Expanded language map should cover Korean, Portuguese, etc."""
        router = ForeignDialogueRouter()
        cue = SubtitleCueModel(id=1, start_ms=0, end_ms=1000, source_text="[Speaking Korean]")
        result = router.route_cue(cue)
        assert result.case_type == "B"
        assert "کۆری" in result.sorani_indicator

    def test_case_insensitive_language(self):
        """Language detection should be case-insensitive."""
        router = ForeignDialogueRouter()
        cue = SubtitleCueModel(id=1, start_ms=0, end_ms=1000, source_text="[speaking FRENCH]")
        result = router.route_cue(cue)
        assert result.case_type == "B"
        assert "فەرەنسی" in result.sorani_indicator

    def test_unknown_language_passthrough(self):
        """Unknown languages should use the original name."""
        router = ForeignDialogueRouter()
        cue = SubtitleCueModel(id=1, start_ms=0, end_ms=1000, source_text="[Speaking Klingon]")
        result = router.route_cue(cue)
        assert result.case_type == "B"
        assert "Klingon" in result.sorani_indicator


# ─── Config Robustness ────────────────────────────────────────────────────────

class TestConfigRobustness:

    def test_malformed_yaml_returns_default(self, tmp_path):
        """Malformed YAML should not crash — returns defaults."""
        f = tmp_path / "bad.yaml"
        f.write_text(": invalid yaml\n  bad: [unclosed")
        config = load_config(str(f))
        assert isinstance(config, HawsubConfig)
        assert config.project.target_language == "ckb"

    def test_empty_yaml_returns_default(self, tmp_path):
        """Empty YAML file should return defaults."""
        f = tmp_path / "empty.yaml"
        f.write_text("")
        config = load_config(str(f))
        assert config.project.target_language == "ckb"

    def test_partial_yaml_fills_defaults(self, tmp_path):
        """Partial YAML should fill in missing fields with defaults."""
        f = tmp_path / "partial.yaml"
        f.write_text("project:\n  mode: fast\n")
        config = load_config(str(f))
        assert config.project.mode == "fast"
        assert config.project.target_language == "ckb"  # default
        assert config.translation.provider == "google"  # default


# ─── QC Engine Edge Cases ─────────────────────────────────────────────────────

class TestQCEdgeCases:

    def test_qc_with_no_target_text(self):
        """QC should handle cues with no target text without crashing."""
        engine = QCEngine()
        cue = SubtitleCueModel(id=1, start_ms=0, end_ms=3000, source_text="Hello", target_text=None)
        result = engine.evaluate_cue(cue)
        assert isinstance(result, QCEvaluationResult)

    def test_qc_with_empty_target(self):
        """QC should handle cues with empty string target."""
        engine = QCEngine()
        cue = SubtitleCueModel(id=1, start_ms=0, end_ms=3000, source_text="Hello", target_text="")
        result = engine.evaluate_cue(cue)
        assert isinstance(result, QCEvaluationResult)

    def test_qc_zero_duration(self):
        """QC should flag zero-duration cues."""
        engine = QCEngine()
        cue = SubtitleCueModel(id=1, start_ms=1000, end_ms=1000, source_text="Flash", target_text="فلاش")
        result = engine.evaluate_cue(cue)
        assert isinstance(result, QCEvaluationResult)
        # Should have technical issues flagged
        assert len(result.issues) >= 1
        issue_rules = [i.rule for i in result.issues]
        assert "min_duration" in issue_rules

    def test_adaptation_very_long_text(self):
        """Adaptation should handle very long text without crashing."""
        engine = AdaptationEngine()
        long_text = "کلمە " * 100  # 100 words
        result = engine.format_semantic_line_breaks(long_text)
        assert "\n" in result  # Should have line breaks


# ─── Provider Edge Cases ──────────────────────────────────────────────────────

class TestProviderEdgeCases:

    def test_factory_unknown_provider_with_fallback(self):
        """Unknown provider with fallback should return mock."""
        model = get_provider(provider_name="unknown_xyz", allow_mock_fallback=True)
        assert model.provider_name == "mock"

    def test_factory_unknown_provider_without_fallback_raises(self):
        """Unknown provider without fallback should raise."""
        with pytest.raises(ValueError):
            get_provider(provider_name="unknown_xyz", allow_mock_fallback=False)

    def test_mock_translate_unknown_phrase(self):
        """Mock should return fallback for unknown phrases."""
        model = get_provider(provider_name="mock")
        resp = model.translate_scene("S1", [{"id": 1, "source_text": "Completely random gibberish"}], None, {})
        assert resp.translations[0].translation.startswith("تەرجەمەی")

    def test_generic_api_parse_cue_ids(self):
        """GenericAPIModel._parse_cue_ids should handle ints, strings, lists, and missing IDs."""
        from hawsub.providers.generic_api import GenericAPIModel
        # Single int
        assert GenericAPIModel._parse_cue_ids({"cue_id": 5}) == [5]
        assert GenericAPIModel._parse_cue_ids({"cue_ids": 5}) == [5]
        # String int
        assert GenericAPIModel._parse_cue_ids({"cue_id": "12"}) == [12]
        # List of ints
        assert GenericAPIModel._parse_cue_ids({"cue_ids": [1, 2, 3]}) == [1, 2, 3]
        # List with string int
        assert GenericAPIModel._parse_cue_ids({"cue_ids": ["7", 8]}) == [7, 8]
        # Missing cue_ids -> default
        assert GenericAPIModel._parse_cue_ids({}, default_id=42) == [42]
        # Invalid string -> default
        assert GenericAPIModel._parse_cue_ids({"cue_ids": "invalid"}, default_id=10) == [10]

    def test_generic_api_safe_parse_json_markdown_blocks(self):
        """GenericAPIModel._safe_parse_json should handle markdown fences and surrounding text."""
        from hawsub.providers.generic_api import GenericAPIModel
        model = GenericAPIModel(provider_name="openai", model_name="gpt-4o", api_key="test-key")

        # Standard JSON
        assert model._safe_parse_json('{"key": "value"}') == {"key": "value"}

        # Markdown fenced block
        md_json = "```json\n{\"key\": \"value\"}\n```"
        assert model._safe_parse_json(md_json) == {"key": "value"}

        # Markdown block with surrounding commentary
        commentary_json = "Here is the response:\n```json\n{\"translations\": [{\"cue_id\": 1}]}\n```\nHope this helps!"
        assert model._safe_parse_json(commentary_json) == {"translations": [{"cue_id": 1}]}

        # Malformed text with embedded JSON object
        raw_text = "Analysis complete: {\"status\": \"ok\"} Thanks."
        assert model._safe_parse_json(raw_text) == {"status": "ok"}


# ─── Export Edge Cases ────────────────────────────────────────────────────────

class TestExportEdgeCases:

    def test_export_empty_cue_list(self, tmp_path):
        """Exporting empty cue list should not crash."""
        SubtitleExporter.export_srt([], str(tmp_path / "empty.srt"))
        assert os.path.exists(tmp_path / "empty.srt")

    def test_export_cues_without_targets(self, tmp_path):
        """Exporting cues with no target text should use source text."""
        cues = [SubtitleCueModel(id=1, start_ms=0, end_ms=1000, source_text="Source only")]
        SubtitleExporter.export_srt(cues, str(tmp_path / "notarget.srt"))
        content = (tmp_path / "notarget.srt").read_text()
        assert "Source only" in content

    def test_export_html_escapes_xss(self, tmp_path):
        """Debug HTML should escape potential XSS in subtitle text."""
        cues = [SubtitleCueModel(id=1, start_ms=0, end_ms=1000,
                source_text='Normal source text',
                target_text='<img src=x onerror=alert(1)>')]
        qc_results = [QCEvaluationResult(cue_id=1)]
        SubtitleExporter.export_bilingual_debug_html(cues, qc_results, str(tmp_path / "xss.html"))
        content = (tmp_path / "xss.html").read_text()
        # Target text should be HTML escaped — raw <img> tag must not appear
        assert "&lt;img" in content
        # The raw attribute should be escaped too
        assert "<img src=x" not in content

    def test_export_qc_report_empty_results(self, tmp_path):
        """QC report with empty results should have zero totals."""
        SubtitleExporter.export_qc_report("test", [], str(tmp_path / "empty_qc.json"))
        with open(tmp_path / "empty_qc.json") as f:
            data = json.load(f)
            assert data["total_cues"] == 0
            assert data["average_confidence"] == 0.0


# ─── Benchmark Robustness ────────────────────────────────────────────────────

class TestBenchmarkRobustness:

    def test_benchmark_mock_covers_all_gold(self):
        """Mock provider should cover all 200 gold benchmark items."""
        from hawsub.benchmark.suite import BenchmarkSuite
        model = get_provider(provider_name="mock")
        suite = BenchmarkSuite()
        report = suite.evaluate_model(model)
        assert report.total_items == 200
        assert report.literal_error_count == 0
        # Mock provider only covers 20 original idiom translations
        assert report.passed_items >= 5
        assert report.overall_benchmark_score >= 0.4

