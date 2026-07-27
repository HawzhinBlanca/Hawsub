"""
Unit tests for SoraniCulturalComplianceEngine and TranslationEnsembleEngine.
"""

import pytest
from hawsub.core.qc.profanity import SoraniCulturalComplianceEngine
from hawsub.core.translation.ensemble import TranslationEnsembleEngine
from hawsub.providers.mock import MockSemanticModel


class TestSoraniCulturalComplianceEngine:

    def test_audit_cue_no_issues(self):
        engine = SoraniCulturalComplianceEngine()
        issues = engine.audit_cue(1, "سڵاو چۆنیت هاوڕێم؟")
        assert len(issues) == 0

    def test_audit_cue_flagged_term(self):
        engine = SoraniCulturalComplianceEngine()
        issues = engine.audit_cue(1, "ئەم سگە کێیە؟")
        assert len(issues) == 1
        assert issues[0].flagged_term == "سگ"
        assert issues[0].suggested_replacement == "نەفرەتی"


class TestTranslationEnsembleEngine:

    def test_ensemble_single_model(self):
        model = MockSemanticModel()
        ensemble = TranslationEnsembleEngine(primary_model=model)
        cues_data = [{"id": 1, "source_text": "You're pushing your luck."}]
        res, reports = ensemble.translate_scene_with_consensus("S01", cues_data)

        assert len(res.translations) == 1
        assert reports[0].agreed is True
        assert reports[0].consensus_score == 1.0

    def test_ensemble_dual_model_consensus(self):
        m1 = MockSemanticModel()
        m2 = MockSemanticModel()
        ensemble = TranslationEnsembleEngine(primary_model=m1, secondary_model=m2)
        cues_data = [{"id": 1, "source_text": "You're pushing your luck."}]
        res, reports = ensemble.translate_scene_with_consensus("S01", cues_data)

        assert len(reports) == 1
        assert reports[0].agreed is True
