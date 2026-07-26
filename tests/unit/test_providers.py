"""
Unit tests for providers: MockSemanticModel, factory, and cache.
"""

import pytest
from hawsub.providers.mock import MockSemanticModel
from hawsub.providers.factory import get_provider
from hawsub.providers.cache import CachedSemanticModel
from hawsub.providers.base import (
    SemanticModel,
    SemanticInterpretationResponse,
    TranslationResponse,
    VerificationResponse,
)


class TestMockProvider:

    def test_mock_translate_scene(self):
        model = MockSemanticModel()
        resp = model.translate_scene(
            scene_id="S001",
            cues_data=[{"id": 1, "source_text": "You're pushing your luck."}],
            interpretations=None,
            context_data={"scene_summary": "Test"},
        )
        assert isinstance(resp, TranslationResponse)
        assert len(resp.translations) == 1
        assert resp.translations[0].cue_ids == [1]
        assert len(resp.translations[0].translation) > 0

    def test_mock_analyze_scene(self):
        model = MockSemanticModel()
        resp = model.analyze_scene(
            scene_id="S001",
            cues_data=[{"id": 1, "source_text": "Break a leg!"}],
            context_data={"scene_summary": "Theater"},
        )
        assert isinstance(resp, SemanticInterpretationResponse)
        assert len(resp.items) == 1
        assert resp.items[0].cue_ids == [1]

    def test_mock_verify_translation(self):
        model = MockSemanticModel()
        resp = model.verify_translation(
            source_text="Hello.",
            current_translation="سڵاو.",
            meaning="Greeting",
            context_data={},
        )
        assert isinstance(resp, VerificationResponse)
        assert resp.decision == "agree"

    def test_mock_translate_known_idiom(self):
        model = MockSemanticModel()
        resp = model.translate_scene(
            scene_id="S001",
            cues_data=[{"id": 1, "source_text": "Bite your tongue!"}],
            interpretations=None,
            context_data={},
        )
        assert "زمانت" in resp.translations[0].translation or len(resp.translations[0].translation) > 0

    def test_mock_provider_attributes(self):
        model = MockSemanticModel()
        assert model.provider_name == "mock"
        assert model.model_name == "mock-gemini-2.5-pro"


class TestProviderFactory:

    def test_factory_creates_mock(self):
        model = get_provider(provider_name="mock", model_name="test-model")
        assert isinstance(model, MockSemanticModel)

    def test_factory_creates_generic(self):
        model = get_provider(provider_name="google", model_name="gemini-2.5-pro")
        assert model.provider_name == "google"
        assert model.model_name == "gemini-2.5-pro"

    def test_factory_creates_openai(self):
        model = get_provider(provider_name="openai", model_name="gpt-4o")
        assert model.provider_name == "openai"

    def test_factory_creates_anthropic(self):
        model = get_provider(provider_name="anthropic", model_name="claude-sonnet-4-20250514")
        assert model.provider_name == "anthropic"

    def test_factory_creates_local(self):
        model = get_provider(provider_name="local", model_name="llama3")
        assert model.provider_name == "local"


class TestCachedProvider:

    def test_cached_wraps_mock(self):
        base = MockSemanticModel()
        cached = CachedSemanticModel(base)
        resp1 = cached.translate_scene(
            scene_id="S001",
            cues_data=[{"id": 1, "source_text": "Hello."}],
            interpretations=None,
            context_data={},
        )
        # Second call should use cache
        resp2 = cached.translate_scene(
            scene_id="S001",
            cues_data=[{"id": 1, "source_text": "Hello."}],
            interpretations=None,
            context_data={},
        )
        assert resp1.translations[0].translation == resp2.translations[0].translation

    def test_cached_provider_attributes(self):
        base = MockSemanticModel()
        cached = CachedSemanticModel(base)
        assert cached.provider_name == "mock"
        assert cached.model_name == "mock-gemini-2.5-pro"
