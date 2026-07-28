"""
Phase 4 Test Coverage Maximization Unit Tests.
Covers CLI commands, RequestCache, GenericAPIModel HTTP retry logic, and ReviewQueue severity filtering.
"""

import os
import json
import tempfile
from unittest.mock import patch, MagicMock
import pytest
from click.testing import CliRunner

from hawsub.cli.main import cli
from hawsub.providers.cache import RequestCache, CachedSemanticModel
from hawsub.providers.generic_api import GenericAPIModel
from hawsub.providers.mock import MockSemanticModel
from hawsub.core.review.queue import ReviewQueue, ReviewItem
from hawsub.core.ingest.parser import SubtitleCueModel
from hawsub.core.qc.engine import QCEvaluationResult, QCIssue


class TestCLICoverage:

    def test_cli_normalize_command(self):
        runner = CliRunner()
        res = runner.invoke(cli, ["normalize", "--text", "سڵاو كوردستان"])
        assert res.exit_code == 0
        assert "Normalized" in res.output

    def test_cli_inspect_command(self):
        runner = CliRunner()
        res = runner.invoke(cli, ["inspect", "-i", "tests/fixtures/sample_english.srt"])
        assert res.exit_code == 0
        assert "Hawsub Subtitle Inspector" in res.output

    def test_cli_benchmark_command(self):
        runner = CliRunner()
        res = runner.invoke(cli, ["benchmark", "--provider", "mock"])
        assert res.exit_code == 0
        assert "Hawsub Benchmark Results" in res.output

    def test_cli_process_command(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            res = runner.invoke(cli, [
                "process",
                "-i", "tests/fixtures/sample_english.srt",
                "-p", "cli_test_proj",
                "-o", tmpdir
            ])
            assert res.exit_code == 0
            assert "Localization complete" in res.output


class TestCacheCoverage:

    def test_request_cache_get_set(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = RequestCache(cache_dir=tmpdir)
            key = cache.compute_cache_key("mock", "m1", "v1", "hello")
            assert cache.get(key) is None

            cache.set(key, {"translation": "سڵاو"})
            data = cache.get(key)
            assert data == {"translation": "سڵاو"}

    def test_cached_semantic_model_wrapper(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = MockSemanticModel()
            cached = CachedSemanticModel(base, cache_dir=tmpdir)

            assert cached.provider_name == "mock"
            assert cached.model_name == "mock-gemini-2.5-pro"

            cues = [{"id": 1, "source_text": "Hello"}]
            r1 = cached.translate_scene("S1", cues, None, {})
            # Second call hits memory cache
            r2 = cached.translate_scene("S1", cues, None, {})
            assert r1 == r2

            a1 = cached.analyze_scene("S1", cues, {})
            a2 = cached.analyze_scene("S1", cues, {})
            assert a1 == a2

            v1 = cached.verify_translation("Hello", "سڵاو", "greeting", {})
            v2 = cached.verify_translation("Hello", "سڵاو", "greeting", {})
            assert v1 == v2


class TestGenericAPIModelCoverage:

    def test_build_chat_payload_formats(self):
        g_model = GenericAPIModel(provider_name="google", model_name="gemini-2.5-pro", api_key="fake")
        p_google = g_model._build_chat_payload("sys", "user")
        assert "contents" in p_google

        a_model = GenericAPIModel(provider_name="anthropic", model_name="claude-3-5-sonnet", api_key="fake")
        p_anthropic = a_model._build_chat_payload("sys", "user")
        assert p_anthropic["model"] == "claude-3-5-sonnet"

        o_model = GenericAPIModel(provider_name="openai", model_name="gpt-4o", api_key="fake")
        p_openai = o_model._build_chat_payload("sys", "user")
        assert "messages" in p_openai

    def test_extract_content_formats(self):
        model = GenericAPIModel(provider_name="openai", model_name="gpt-4o", api_key="fake")

        openai_resp = {"choices": [{"message": {"content": "OpenAI result"}}]}
        assert model._extract_content(openai_resp) == "OpenAI result"

        anthropic_resp = {"content": [{"text": "Anthropic result"}]}
        assert model._extract_content(anthropic_resp) == "Anthropic result"

        google_resp = {"candidates": [{"content": {"parts": [{"text": "Google result"}]}}]}
        assert model._extract_content(google_resp) == "Google result"

        assert model._extract_content({}) == ""

    @patch.object(GenericAPIModel, "_call_http_json")
    def test_generic_api_translate_and_analyze(self, mock_call):
        mock_call.return_value = {
            "choices": [{
                "message": {
                    "content": '{"scene_id": "S1", "translations": [{"cue_ids": [1], "meaning": "Idiom", "translation": "تۆ زێدەڕۆیی لە بەختت دەکەیت"}]}'
                }
            }]
        }
        model = GenericAPIModel(provider_name="openai", model_name="gpt-4o", api_key="fake")
        cues = [{"id": 1, "source_text": "You're pushing your luck."}]

        tr = model.translate_scene("S1", cues, None, {})
        assert len(tr.translations) == 1
        assert tr.translations[0].translation == "تۆ زێدەڕۆیی لە بەختت دەکەیت"

        mock_call.return_value = {
            "choices": [{
                "message": {
                    "content": '{"scene_id": "S1", "items": [{"cue_ids": [1], "source_text": "Test", "intended_meaning": "Meaning"}]}'
                }
            }]
        }
        an = model.analyze_scene("S1", cues, {})
        assert len(an.items) == 1

        mock_call.return_value = {
            "choices": [{
                "message": {
                    "content": '{"cue_ids": [1], "decision": "agree", "severity": "none", "reason": "Good"}'
                }
            }]
        }
        vf = model.verify_translation("Source", "Target", "Meaning", {})
        assert vf.decision == "agree"


class TestReviewQueueCoverage:

    def test_review_queue_severity_filtering(self):
        queue = ReviewQueue()
        cue = SubtitleCueModel(id=1, start_ms=1000, end_ms=3000, source_text="Hello", target_text="سڵاو")
        qc_result = QCEvaluationResult(
            cue_id=1,
            issues=[QCIssue(cue_id=1, category="technical", rule="cps", severity="critical", score_impact=0.3, message="Too fast")]
        )
        queue.add_cue_for_review(cue, qc_result, scene_id="S1")

        items_all = queue.get_pending_items()
        assert len(items_all) == 1

        items_critical = queue.get_pending_items(severity_filter="critical")
        assert len(items_critical) == 1

        items_minor = queue.get_pending_items(severity_filter="minor")
        assert len(items_minor) == 0

    def test_review_queue_apply_decision(self):
        queue = ReviewQueue()
        cue = SubtitleCueModel(id=1, start_ms=1000, end_ms=3000, source_text="Hello", target_text="سڵاو")
        
        updated = queue.apply_decision(cue, action="edit", approved_text="سڵاو هاوڕێم")
        assert updated.target_text == "سڵاو هاوڕێم"
        assert queue.decisions[1].action == "edit"
