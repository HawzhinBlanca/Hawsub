"""
Unit tests for GlossaryEngine.
"""

import pytest
from hawsub.core.context.glossary import GlossaryEngine, GlossaryTerm


class TestGlossaryEngine:

    def test_default_honorifics_loaded(self):
        engine = GlossaryEngine()
        assert "mr." in engine.terms
        assert engine.terms["mr."].target_sorani == "بەڕێز"

    def test_custom_terms_added(self):
        engine = GlossaryEngine(custom_terms={"Gotham": "گۆثەم"})
        assert "gotham" in engine.terms
        assert engine.terms["gotham"].target_sorani == "گۆثەم"

    def test_apply_glossary_honorific_prepended(self):
        engine = GlossaryEngine()
        res = engine.apply_glossary("Mr. Wayne is here.", "وەین لێرەیە.")
        assert "بەڕێز" in res
