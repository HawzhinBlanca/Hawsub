"""
Tests for production hardening Phase 1-3:
  Phase 1: Critical bug fixes (composite PK, ASS timestamp, time import)
  Phase 2: CLI commands (estimate, validate, feedback)
  Phase 3: Provider robustness (JSON array parsing, token tracking)
"""

import os
import json
import sqlite3
import pytest
from click.testing import CliRunner
from hawsub.cli.main import cli
from hawsub.core.ingest.parser import SubtitleParser, _parse_ass_timestamp
from hawsub.providers.generic_api import GenericAPIModel
from hawsub.core.orchestration.pipeline import DurablePipeline
from hawsub.config.loader import load_config


# ──────────────────────────────────────────────────────────────────────────────
# Phase 1: Critical Bug Fixes
# ──────────────────────────────────────────────────────────────────────────────

class TestCompositeKeyBugFix:

    def test_stage_status_independent_stages(self, tmp_path):
        """Multiple stages should be stored independently (composite PK fix)."""
        db_path = str(tmp_path / "test_pipeline.db")
        cfg = load_config()
        pipeline = DurablePipeline(project_id="test_pk", config=cfg, db_path=db_path)
        
        pipeline.set_stage_status("INGEST", "completed")
        pipeline.set_stage_status("TRANSLATION_QC", "in_progress")
        pipeline.set_stage_status("EXPORT", "pending")

        assert pipeline.get_stage_status("INGEST") == "completed"
        assert pipeline.get_stage_status("TRANSLATION_QC") == "in_progress"
        assert pipeline.get_stage_status("EXPORT") == "pending"

    def test_stage_status_update(self, tmp_path):
        """Updating a stage should not affect other stages."""
        db_path = str(tmp_path / "test_pipeline2.db")
        cfg = load_config()
        pipeline = DurablePipeline(project_id="test_pk2", config=cfg, db_path=db_path)
        
        pipeline.set_stage_status("INGEST", "in_progress")
        pipeline.set_stage_status("INGEST", "completed")

        assert pipeline.get_stage_status("INGEST") == "completed"

    def test_nonexistent_stage_returns_none(self, tmp_path):
        """Querying nonexistent stage returns None."""
        db_path = str(tmp_path / "test_pipeline3.db")
        cfg = load_config()
        pipeline = DurablePipeline(project_id="test_pk3", config=cfg, db_path=db_path)
        
        assert pipeline.get_stage_status("NONEXISTENT") is None


class TestASSTimestampFix:

    def test_valid_timestamp(self):
        """Valid ASS timestamp parses correctly."""
        assert _parse_ass_timestamp("0:00:01.00") == 1000
        assert _parse_ass_timestamp("1:23:45.67") == (1*3600 + 23*60 + 45) * 1000 + 670

    def test_invalid_timestamp_raises(self):
        """Invalid ASS timestamp now raises ValueError instead of returning 0."""
        with pytest.raises(ValueError, match="Invalid ASS timestamp"):
            _parse_ass_timestamp("invalid")
        
        with pytest.raises(ValueError, match="Invalid ASS timestamp"):
            _parse_ass_timestamp("")


# ──────────────────────────────────────────────────────────────────────────────
# Phase 2: CLI Commands
# ──────────────────────────────────────────────────────────────────────────────

class TestCLIEstimate:

    def test_estimate_command(self, tmp_path):
        """Test hawsub estimate command."""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text("""1
00:00:01,000 --> 00:00:03,500
Hello there.

2
00:00:04,000 --> 00:00:06,200
How are you?
""")
        runner = CliRunner()
        result = runner.invoke(cli, ["estimate", "-i", str(srt_file)])
        assert result.exit_code == 0
        assert "Cost Estimate" in result.output
        assert "Total Cues" in result.output
        assert "Est. Cost" in result.output


class TestCLIValidate:

    def test_validate_command(self, tmp_path):
        """Test hawsub validate command."""
        srt_file = tmp_path / "test_sorani.srt"
        srt_file.write_text("""1
00:00:01,000 --> 00:00:03,500
سڵاو هاوڕێم

2
00:00:04,000 --> 00:00:06,200
چۆنیت؟
""")
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "-i", str(srt_file)])
        assert result.exit_code == 0
        assert "Validation Summary" in result.output


class TestCLIFeedback:

    def test_feedback_no_data(self, tmp_path):
        """Test feedback command with empty database."""
        db_path = str(tmp_path / "test_fb.db")
        runner = CliRunner()
        result = runner.invoke(cli, ["feedback", "--db", db_path])
        assert result.exit_code == 0
        assert "No corrections" in result.output

    def test_feedback_glossary_candidates(self, tmp_path):
        """Test feedback --glossary-candidates with empty database."""
        db_path = str(tmp_path / "test_fb2.db")
        runner = CliRunner()
        result = runner.invoke(cli, ["feedback", "--db", db_path, "--glossary-candidates"])
        assert result.exit_code == 0
        assert "No frequent correction" in result.output


class TestCLIInspect:

    def test_inspect_command(self, tmp_path):
        """Test hawsub inspect command."""
        srt_file = tmp_path / "inspect_test.srt"
        srt_file.write_text("""1
00:00:01,000 --> 00:00:03,500
Hello there.

2
00:00:04,000 --> 00:00:06,200
How are you?
""")
        runner = CliRunner()
        result = runner.invoke(cli, ["inspect", "-i", str(srt_file)])
        assert result.exit_code == 0
        assert "Total Cues" in result.output
        assert "2" in result.output


# ──────────────────────────────────────────────────────────────────────────────
# Phase 3: Provider Robustness — JSON Parsing
# ──────────────────────────────────────────────────────────────────────────────

class TestSafeParseJSON:

    def setup_method(self):
        self.model = GenericAPIModel.__new__(GenericAPIModel)
        # Minimal init for testing _safe_parse_json
        self.model.provider_name = "mock"
        self.model.model_name = "test"

    def test_parse_normal_json(self):
        result = self.model._safe_parse_json('{"translations": [{"cue_ids": [1], "translation": "سڵاو"}]}')
        assert "translations" in result

    def test_parse_markdown_fenced_json(self):
        result = self.model._safe_parse_json('```json\n{"translations": [{"cue_ids": [1]}]}\n```')
        assert "translations" in result

    def test_parse_bare_array(self):
        """LLM returns bare array without wrapper object."""
        result = self.model._safe_parse_json('[{"cue_ids": [1], "translation": "سڵاو"}]')
        assert "translations" in result
        assert isinstance(result["translations"], list)
        assert len(result["translations"]) == 1

    def test_parse_json_with_preamble(self):
        """JSON embedded in explanatory text."""
        result = self.model._safe_parse_json('Here is the translation:\n{"translations": []}')
        assert "translations" in result

    def test_parse_empty_returns_empty_dict(self):
        result = self.model._safe_parse_json("")
        assert result == {}

    def test_parse_garbage_returns_empty_dict(self):
        result = self.model._safe_parse_json("This is not JSON at all")
        assert result == {}

    def test_parse_array_in_text(self):
        """Array embedded in explanatory text — parser finds the JSON array."""
        result = self.model._safe_parse_json('Result:\n[{"cue_ids": [1], "translation": "test"}]')
        assert "translations" in result
