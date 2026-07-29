"""
Integration tests for real LLM translation benchmark.
These tests require actual API keys and are gated by the 'integration' marker.

Run with: pytest tests/integration/test_real_llm_benchmark.py -v -m integration

Requires one of:
  - GOOGLE_API_KEY environment variable
  - OPENAI_API_KEY environment variable
"""

import os
import json
import pytest
from hawsub.benchmark.suite import BenchmarkSuite
from hawsub.providers.factory import get_provider

# Gate all tests behind the 'integration' marker
pytestmark = pytest.mark.integration


def _get_available_provider():
    """Return (provider_name, model_name) for first available API key."""
    if os.environ.get("GOOGLE_API_KEY"):
        return "google", "gemini-2.5-flash"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai", "gpt-4o-mini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic", "claude-sonnet-4-20250514"
    if os.environ.get("OPENROUTER_API_KEY"):
        return "openrouter", "google/gemini-2.5-flash"
    return None, None


@pytest.fixture
def real_provider():
    """Create a real LLM provider from available API keys."""
    provider_name, model_name = _get_available_provider()
    if not provider_name:
        pytest.skip("No API key available (set GOOGLE_API_KEY, OPENAI_API_KEY, etc.)")
    return get_provider(provider_name=provider_name, model_name=model_name)


class TestRealLLMBenchmark:

    def test_benchmark_runs_with_real_llm(self, real_provider):
        """Run the gold benchmark against a real LLM and verify minimum score."""
        suite = BenchmarkSuite()
        assert len(suite.items) > 0, "Gold dataset is empty"

        report = suite.evaluate_model(real_provider)

        # Log results for visibility
        print(f"\n{'='*60}")
        print(f"Provider: {report.provider_name} | Model: {report.model_name}")
        print(f"Score: {report.overall_benchmark_score:.3f}")
        print(f"Passed: {report.passed_items}/{report.total_items}")
        print(f"Literal errors: {report.literal_error_count}")
        print(f"{'='*60}")

        for r in report.results:
            status = "✅" if r.exact_gold_match else ("⚠️" if r.acceptable_match else "❌")
            print(f"  {status} [{r.item_id}] {r.source[:40]}...")
            print(f"       Gold:  {r.gold_sorani}")
            print(f"       Model: {r.model_translation}")
            print()

        # Minimum threshold — real LLMs should score at least 0.70
        assert report.overall_benchmark_score >= 0.70, (
            f"Benchmark score {report.overall_benchmark_score} below minimum 0.70"
        )
        assert report.literal_error_count <= 3, (
            f"Too many literal translation errors: {report.literal_error_count}"
        )

    def test_single_idiom_translation(self, real_provider):
        """Test a single known idiom to verify LLM produces natural Sorani."""
        cues = [{"id": 1, "source_text": "Break a leg!"}]
        ctx = {"scene_summary": "A friend wishes good luck before a performance"}

        response = real_provider.translate_scene(
            scene_id="TEST_001",
            cues_data=cues,
            interpretations=None,
            context_data=ctx,
        )

        assert len(response.translations) > 0
        translation = response.translations[0].translation

        # Should NOT be literal "قاچت بشکێنە"
        assert "قاچ" not in translation, f"Literal translation detected: {translation}"
        # Should contain some Sorani text
        assert len(translation) > 2, f"Translation too short: {translation}"
        print(f"\nIdiom test: 'Break a leg!' → '{translation}'")

    def test_negation_preserved(self, real_provider):
        """Test that negation is preserved in translation."""
        cues = [{"id": 1, "source_text": "I don't know what to do."}]
        ctx = {"scene_summary": "Character expressing uncertainty"}

        response = real_provider.translate_scene(
            scene_id="TEST_002",
            cues_data=cues,
            interpretations=None,
            context_data=ctx,
        )

        translation = response.translations[0].translation
        # Should contain Sorani negation markers
        has_negation = any(marker in translation for marker in ["نە", "نا", "مە", "نیت", "نییە"])
        assert has_negation, f"Negation lost in translation: {translation}"
        print(f"\nNegation test: 'I don't know...' → '{translation}'")


class TestRealLLMBenchmarkSaving:

    def test_save_benchmark_results(self, real_provider, tmp_path):
        """Save benchmark results to JSON for tracking over time."""
        suite = BenchmarkSuite()
        report = suite.evaluate_model(real_provider)

        results_file = tmp_path / "benchmark_results.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(), f, ensure_ascii=False, indent=2)

        assert results_file.exists()
        with open(results_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["overall_benchmark_score"] == report.overall_benchmark_score
