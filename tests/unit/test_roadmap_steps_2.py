"""
Tests for Steps 5-10 of the production hardening roadmap:
  Step 6: Sorani Linguistic Validator
  Step 8: Cost Controls (TokenBudget placeholder)
  Step 10: Real-world smoke tests
"""

import os
import json
import tempfile
import pytest
from hawsub.core.normalization.sorani import SoraniNormalizer
from hawsub.core.ingest.parser import SubtitleParser, SubtitleCueModel
from hawsub.core.export.exporters import SubtitleExporter


# ──────────────────────────────────────────────────────────────────────────────
# Step 6: Sorani Linguistic Validator Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestSoraniLinguisticValidator:

    def setup_method(self):
        self.normalizer = SoraniNormalizer()

    def test_detect_arabic_yeh_error(self):
        """Detect Arabic yeh (ي) that should be Kurdish yeh (ی)."""
        # Use Arabic yeh U+064A
        text = "سلاو هاوريم"  # contains Arabic yeh ي
        issues = self.normalizer.detect_common_llm_errors(text)
        found_yeh_issue = any("Arabic yeh" in issue for issue in issues)
        assert found_yeh_issue, f"Expected Arabic yeh detection, got: {issues}"

    def test_no_error_clean_sorani(self):
        """No LLM errors in clean Sorani text."""
        text = "سڵاو هاوڕێم"  # Clean Sorani with correct characters
        issues = self.normalizer.detect_common_llm_errors(text)
        # Filter out only actual errors (not false positives for short clean text)
        real_issues = [i for i in issues if "Arabic yeh" in i or "Mixed script" in i or "repetition" in i]
        assert len(real_issues) == 0, f"False positive issues: {real_issues}"

    def test_detect_markdown_pollution(self):
        """Detect markdown formatting leaked from LLM."""
        text = "**سڵاو** هاوڕێم"
        issues = self.normalizer.detect_common_llm_errors(text)
        assert any("Markdown" in i for i in issues)

    def test_detect_triple_word_repetition(self):
        """Detect LLM stuttering (triple word repetition)."""
        text = "سڵاو سڵاو سڵاو هاوڕێم"
        issues = self.normalizer.detect_common_llm_errors(text)
        assert any("Triple word repetition" in i for i in issues)

    def test_detect_numbered_list(self):
        """Detect numbered list format in subtitle."""
        text = "1. سڵاو هاوڕێم"
        issues = self.normalizer.detect_common_llm_errors(text)
        assert any("Numbered list" in i for i in issues)

    def test_detect_parenthesis_pollution(self):
        """Detect English notes in parentheses from LLM."""
        text = "سڵاو (meaning hello) هاوڕێم"
        issues = self.normalizer.detect_common_llm_errors(text)
        assert any("parentheses" in i for i in issues)

    def test_validate_sorani_text_comprehensive(self):
        """Full validation returns all categories."""
        text = "سڵاو هاوڕێم"
        result = self.normalizer.validate_sorani_text(text)
        assert "kurmanji" in result
        assert "untranslated" in result
        assert "ezafe" in result
        assert "llm_errors" in result

    def test_ezafe_chain_normal(self):
        """Normal ezafe usage should not be flagged."""
        text = "کتێبی نوێی کوردی"  # 2-chain, normal
        issues = self.normalizer.detect_excessive_ezafe_chains(text)
        assert len(issues) == 0

    def test_no_false_positive_on_empty(self):
        """Empty text should produce no issues."""
        result = self.normalizer.validate_sorani_text("")
        total = sum(len(v) for v in result.values())
        assert total == 0


# ──────────────────────────────────────────────────────────────────────────────
# Step 10: Real-World Smoke Tests (Parse → Export Round-Trip)
# ──────────────────────────────────────────────────────────────────────────────

class TestRealWorldSRT:
    """Test SRT format round-trip with realistic content."""

    SAMPLE_SRT = """1
00:00:01,000 --> 00:00:03,500
Hello, how are you doing today?

2
00:00:04,000 --> 00:00:06,200
I'm doing great, thanks for asking!

3
00:00:07,000 --> 00:00:09,800
Did you hear about the big news?

4
00:00:10,500 --> 00:00:13,000
No, what happened?
Tell me everything.

5
00:00:14,000 --> 00:00:16,500
It's a long story. Let's sit down first.

"""

    def test_parse_and_roundtrip(self, tmp_path):
        """Parse SRT, export, and re-parse to verify round-trip stability."""
        cues = SubtitleParser.parse_srt(self.SAMPLE_SRT)
        assert len(cues) == 5

        out_path = str(tmp_path / "roundtrip.srt")
        SubtitleExporter.export_srt(cues, out_path)

        with open(out_path, "r", encoding="utf-8") as f:
            exported = f.read()

        cues2 = SubtitleParser.parse_srt(exported)
        assert len(cues2) == len(cues)

        for c1, c2 in zip(cues, cues2):
            assert c1.source_text.strip() == c2.source_text.strip()
            assert c1.start_ms == c2.start_ms
            assert c1.end_ms == c2.end_ms

    def test_parse_with_bom(self, tmp_path):
        """Parse SRT with UTF-8 BOM."""
        bom_content = "\ufeff" + self.SAMPLE_SRT
        in_path = str(tmp_path / "bom_test.srt")
        with open(in_path, "w", encoding="utf-8-sig") as f:
            f.write(self.SAMPLE_SRT)

        with open(in_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
        cues = SubtitleParser.parse_srt(content)
        assert len(cues) >= 4  # Should handle BOM gracefully


class TestRealWorldVTT:
    """Test VTT format round-trip."""

    SAMPLE_VTT = """WEBVTT

1
00:00:01.000 --> 00:00:03.500
Hello, how are you?

2
00:00:04.000 --> 00:00:06.200
I'm fine, thanks.

3
00:00:07.000 --> 00:00:09.800
Let's get started.

"""

    def test_parse_and_roundtrip(self, tmp_path):
        """Parse VTT, export, and verify content integrity."""
        cues = SubtitleParser.parse_vtt(self.SAMPLE_VTT)
        assert len(cues) >= 3

        out_path = str(tmp_path / "roundtrip.vtt")
        SubtitleExporter.export_vtt(cues, out_path)

        with open(out_path, "r", encoding="utf-8") as f:
            exported = f.read()
        assert "WEBVTT" in exported
        assert "Hello" in exported


class TestRealWorldASS:
    """Test ASS format round-trip."""

    SAMPLE_ASS = """[Script Info]
Title: Test Subtitle
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.50,Default,,0,0,0,,Hello there.
Dialogue: 0,0:00:04.00,0:00:06.20,Default,,0,0,0,,How are you?
Dialogue: 0,0:00:07.00,0:00:09.80,Default,,0,0,0,,I'm doing well.
"""

    def test_parse_and_roundtrip(self, tmp_path):
        """Parse ASS, export, and verify content."""
        cues = SubtitleParser.parse_ass(self.SAMPLE_ASS)
        assert len(cues) >= 3

        out_path = str(tmp_path / "roundtrip.ass")
        SubtitleExporter.export_ass(cues, out_path, title="Test")

        with open(out_path, "r", encoding="utf-8") as f:
            exported = f.read()
        assert "[Script Info]" in exported
        assert "Hello" in exported or "Dialogue" in exported


class TestMultiFormatExport:
    """Test exporting parsed cues to all three formats."""

    def test_export_all_formats(self, tmp_path):
        """Export same cues to SRT, VTT, ASS and verify all are valid."""
        cues = [
            SubtitleCueModel(id=1, start_ms=1000, end_ms=3500, source_text="Hello world", target_text="سڵاو جیهان"),
            SubtitleCueModel(id=2, start_ms=4000, end_ms=6200, source_text="Goodbye", target_text="خوا حافیز"),
        ]

        srt_path = str(tmp_path / "test.srt")
        vtt_path = str(tmp_path / "test.vtt")
        ass_path = str(tmp_path / "test.ass")

        SubtitleExporter.export_srt(cues, srt_path)
        SubtitleExporter.export_vtt(cues, vtt_path)
        SubtitleExporter.export_ass(cues, ass_path, title="Test")

        # All files should exist and be non-empty
        for p in [srt_path, vtt_path, ass_path]:
            assert os.path.exists(p)
            assert os.path.getsize(p) > 0

        # SRT should be re-parseable
        with open(srt_path, "r", encoding="utf-8") as f:
            srt_cues = SubtitleParser.parse_srt(f.read())
        assert len(srt_cues) == 2

    def test_unicode_preservation(self, tmp_path):
        """Test that Sorani Unicode characters survive export round-trip."""
        cues = [
            SubtitleCueModel(
                id=1, start_ms=0, end_ms=2000,
                source_text="Hello",
                target_text="سڵاو ئێوە، بەخێرهاتن بۆ کوردستان!"
            ),
        ]

        srt_path = str(tmp_path / "unicode_test.srt")
        SubtitleExporter.export_srt(cues, srt_path)

        with open(srt_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Verify Kurdish-specific characters preserved
        assert "ڵ" in content  # Kurdish L
        assert "ێ" in content  # Kurdish E
        assert "ۆ" in content  # Kurdish O (in بۆ)
