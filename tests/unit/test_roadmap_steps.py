"""
Tests for Steps 1-3 of the production hardening roadmap:
  Step 1: Translation Memory integration into pipeline
  Step 2: Prompt file loading in GenericAPIModel
  Step 3: Expanded QC engine semantic checks
"""

import os
import json
import tempfile
import pytest
from hawsub.core.qc.engine import QCEngine, QCEvaluationResult, QCIssue
from hawsub.core.ingest.parser import SubtitleCueModel
from hawsub.core.translation.memory import TranslationMemory
from hawsub.core.context.glossary import GlossaryEngine
from hawsub.providers.generic_api import GenericAPIModel
from hawsub.config.schema import QCConfig


# ──────────────────────────────────────────────────────────────────────────────
# Step 1: Translation Memory Integration Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestTranslationMemoryIntegration:

    def test_tm_store_and_retrieve_exact(self, tmp_path):
        """TM stores a translation and retrieves it with exact match."""
        tm = TranslationMemory(db_path=str(tmp_path / "test.tm.db"))
        tm.store_translation("Hello my friend", "سڵاو هاوڕێم", context_notes="scene:1")
        match = tm.find_fuzzy_match("Hello my friend", threshold=0.90)
        assert match is not None
        assert match.target_text == "سڵاو هاوڕێم"
        assert match.similarity_score == 1.0

    def test_tm_fuzzy_match_high_threshold(self, tmp_path):
        """TM finds fuzzy match with high similarity."""
        tm = TranslationMemory(db_path=str(tmp_path / "test.tm.db"))
        tm.store_translation("Hello my friend", "سڵاو هاوڕێم")
        # Similar but not identical
        match = tm.find_fuzzy_match("Hello my friends", threshold=0.85)
        assert match is not None
        assert match.similarity_score >= 0.85

    def test_tm_fuzzy_match_below_threshold(self, tmp_path):
        """TM returns None when no match above threshold."""
        tm = TranslationMemory(db_path=str(tmp_path / "test.tm.db"))
        tm.store_translation("Hello my friend", "سڵاو هاوڕێم")
        match = tm.find_fuzzy_match("Completely different text", threshold=0.92)
        assert match is None

    def test_tm_empty_inputs(self, tmp_path):
        """TM handles empty inputs gracefully."""
        tm = TranslationMemory(db_path=str(tmp_path / "test.tm.db"))
        tm.store_translation("", "", context_notes=None)  # Should not crash
        match = tm.find_fuzzy_match("", threshold=0.85)
        assert match is None

    def test_tm_overwrite_existing(self, tmp_path):
        """TM overwrites existing translation for same source."""
        tm = TranslationMemory(db_path=str(tmp_path / "test.tm.db"))
        tm.store_translation("test source", "old translation")
        tm.store_translation("test source", "new translation")
        match = tm.find_fuzzy_match("test source", threshold=0.99)
        assert match is not None
        assert match.target_text == "new translation"


# ──────────────────────────────────────────────────────────────────────────────
# Step 2: Prompt Loading Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestPromptLoading:

    def test_load_translation_v2_prompt(self):
        """GenericAPIModel loads translation_v2.txt from prompts directory."""
        model = GenericAPIModel(
            provider_name="mock", model_name="test", api_key="test",
            prompt_dir="prompts",
        )
        assert model._translation_prompt != ""
        assert "Few-Shot" in model._translation_prompt or "FEW-SHOT" in model._translation_prompt

    def test_load_semantic_v2_prompt(self):
        """GenericAPIModel loads semantic_v2.txt from prompts directory."""
        model = GenericAPIModel(
            provider_name="mock", model_name="test", api_key="test",
            prompt_dir="prompts",
        )
        assert model._semantic_prompt != ""
        assert "narrative" in model._semantic_prompt.lower() or "tone" in model._semantic_prompt.lower()

    def test_load_verifier_prompt(self):
        """GenericAPIModel loads verifier_v1.txt from prompts directory."""
        model = GenericAPIModel(
            provider_name="mock", model_name="test", api_key="test",
            prompt_dir="prompts",
        )
        assert model._verifier_prompt != ""

    def test_fallback_when_prompt_dir_missing(self, tmp_path):
        """GenericAPIModel falls back gracefully when prompt dir doesn't exist."""
        model = GenericAPIModel(
            provider_name="mock", model_name="test", api_key="test",
            prompt_dir=str(tmp_path / "nonexistent"),
        )
        # Should not crash, prompts should be empty strings (fallback to hardcoded)
        assert model._translation_prompt == ""
        assert model._semantic_prompt == ""

    def test_v2_prompt_contains_orthographic_rules(self):
        """V2 translation prompt contains orthographic rules for correct Sorani script."""
        model = GenericAPIModel(
            provider_name="mock", model_name="test", api_key="test",
            prompt_dir="prompts",
        )
        prompt = model._translation_prompt
        assert "U+06A9" in prompt or "ک" in prompt  # Kurdish kaf
        assert "U+06CC" in prompt or "ی" in prompt  # Kurdish yeh

    def test_v2_prompt_contains_few_shot_examples(self):
        """V2 translation prompt contains few-shot gold examples."""
        model = GenericAPIModel(
            provider_name="mock", model_name="test", api_key="test",
            prompt_dir="prompts",
        )
        prompt = model._translation_prompt
        # Should have at least the idiom examples
        assert "Break a leg" in prompt or "pushing your luck" in prompt

    def test_glossary_injection_placeholder(self):
        """V2 translation prompt has glossary_terms placeholder."""
        model = GenericAPIModel(
            provider_name="mock", model_name="test", api_key="test",
            prompt_dir="prompts",
        )
        assert "{glossary_terms}" in model._translation_prompt


# ──────────────────────────────────────────────────────────────────────────────
# Step 3: Expanded QC Semantic Checks Tests
# ──────────────────────────────────────────────────────────────────────────────

def _make_cue(cue_id=1, source="Hello", target="سڵاو", start_ms=0, end_ms=2000, confidence=1.0):
    """Helper to create test cues."""
    return SubtitleCueModel(
        id=cue_id,
        start_ms=start_ms,
        end_ms=end_ms,
        source_text=source,
        target_text=target,
        source_confidence=confidence,
    )


class TestQCQuestionMarkConsistency:

    def test_question_mark_present(self):
        """No issue when question mark is preserved."""
        qc = QCEngine()
        cue = _make_cue(source="What happened?", target="چی بوو؟")
        result = qc.evaluate_cue(cue)
        rules = [i.rule for i in result.issues]
        assert "question_mark_missing" not in rules

    def test_question_mark_missing(self):
        """Flag when source has ? but target doesn't."""
        qc = QCEngine()
        cue = _make_cue(source="What happened?", target="چی بوو")
        result = qc.evaluate_cue(cue)
        rules = [i.rule for i in result.issues]
        assert "question_mark_missing" in rules


class TestQCMockFallbackDetection:

    def test_mock_fallback_detected(self):
        """Flag mock fallback prefix in translation."""
        qc = QCEngine()
        cue = _make_cue(source="Hello", target="تەرجەمەی: Hello")
        result = qc.evaluate_cue(cue)
        rules = [i.rule for i in result.issues]
        assert "mock_fallback_detected" in rules

    def test_real_translation_not_flagged(self):
        """Normal Sorani translation should not trigger mock detection."""
        qc = QCEngine()
        cue = _make_cue(source="Hello", target="سڵاو")
        result = qc.evaluate_cue(cue)
        rules = [i.rule for i in result.issues]
        assert "mock_fallback_detected" not in rules


class TestQCLengthRatioCheck:

    def test_suspiciously_short_translation(self):
        """Flag when translation is too short relative to source."""
        qc = QCEngine()
        cue = _make_cue(
            source="This is a very long sentence with many words in it that should produce a reasonable translation",
            target="ئەم بوو",  # Only 3 letters vs ~80 source chars
        )
        result = qc.evaluate_cue(cue)
        rules = [i.rule for i in result.issues]
        assert "length_ratio_too_short" in rules

    def test_normal_length_translation(self):
        """Normal length ratio should not trigger issue."""
        qc = QCEngine()
        cue = _make_cue(source="Hello my friend", target="سڵاو هاوڕێم")
        result = qc.evaluate_cue(cue)
        rules = [i.rule for i in result.issues]
        assert "length_ratio_too_short" not in rules
        assert "length_ratio_too_long" not in rules


class TestQCDuplicateTranslation:

    def test_duplicate_detected(self):
        """Flag when translation is identical to previous cue."""
        qc = QCEngine()
        cue = _make_cue(source="Run now", target="بڕۆ ئێستا")
        result = qc.evaluate_cue(cue, prev_translation="بڕۆ ئێستا")
        rules = [i.rule for i in result.issues]
        assert "duplicate_translation" in rules

    def test_different_translations_not_flagged(self):
        """Different translations should not trigger duplicate check."""
        qc = QCEngine()
        cue = _make_cue(source="Run now", target="بڕۆ ئێستا")
        result = qc.evaluate_cue(cue, prev_translation="وەرە بڕۆین")
        rules = [i.rule for i in result.issues]
        assert "duplicate_translation" not in rules

    def test_short_duplicate_not_flagged(self):
        """Very short duplicates (e.g., 'بەڵێ') should not be flagged."""
        qc = QCEngine()
        cue = _make_cue(source="Yes", target="بەڵێ")
        result = qc.evaluate_cue(cue, prev_translation="بەڵێ")
        rules = [i.rule for i in result.issues]
        assert "duplicate_translation" not in rules


class TestQCProperNounPreservation:

    def test_proper_noun_missing_detected(self):
        """Flag when a known character name is in source but target is empty."""
        qc = QCEngine()
        cue = _make_cue(source="John is coming.", target="")
        result = qc.evaluate_cue(cue, context_names=["John"])
        rules = [i.rule for i in result.issues]
        assert "proper_noun_missing" in rules

    def test_proper_noun_present_no_flag(self):
        """No flag when character name source has proper translation."""
        qc = QCEngine()
        cue = _make_cue(source="John is coming.", target="جۆن دێت.")
        result = qc.evaluate_cue(cue, context_names=["John"])
        rules = [i.rule for i in result.issues]
        assert "proper_noun_missing" not in rules


# ──────────────────────────────────────────────────────────────────────────────
# Step 4: Glossary Engine Enhancement Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestGlossaryEngineFull:

    def test_honorific_prepended(self):
        engine = GlossaryEngine()
        result = engine.apply_glossary("Dr. Smith is here.", "سمیث لێرەیە.")
        assert "دکتۆر" in result

    def test_custom_character_name(self):
        engine = GlossaryEngine(custom_terms={"Gotham": "گۆثەم"})
        assert "gotham" in engine.terms
        assert engine.terms["gotham"].target_sorani == "گۆثەم"

    def test_glossary_terms_serialization(self):
        """Glossary terms can be serialized for prompt injection."""
        engine = GlossaryEngine(custom_terms={"Batman": "باتمان"})
        lines = []
        for key, term in engine.terms.items():
            lines.append(f"  {term.source_term} → {term.target_sorani} ({term.category})")
        glossary_str = "\n".join(lines)
        assert "Batman → باتمان" in glossary_str
        assert "Mr. → بەڕێز" in glossary_str or "mr. → بەڕێز" in glossary_str.lower()

    def test_empty_translation_not_modified(self):
        engine = GlossaryEngine()
        result = engine.apply_glossary("Mr. Smith", "")
        assert result == ""
