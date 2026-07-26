"""
Unit tests for Scene Segmenter, Context Bible, Config Loader, ASR Adapter, and Review Queue.
"""

import pytest
from hawsub.core.scene.segmenter import SceneSegmenter, SceneBatchModel
from hawsub.core.context.bible import ProjectBible, ContextPackage
from hawsub.core.review.queue import ReviewQueue
from hawsub.core.asr.adapter import ASRAdapter, AlignmentResult
from hawsub.core.ingest.parser import SubtitleCueModel
from hawsub.config.loader import load_config
from hawsub.config.schema import HawsubConfig


# ─── Scene Segmenter Tests ────────────────────────────────────────────────────

class TestSceneSegmenter:

    def _make_cues(self, n=15):
        cues = []
        for i in range(1, n + 1):
            cues.append(SubtitleCueModel(
                id=i,
                start_ms=(i - 1) * 3000,
                end_ms=i * 3000 - 500,
                source_text=f"Dialogue line {i}.",
            ))
        return cues

    def test_segmentation_produces_batches(self):
        seg = SceneSegmenter(min_cues=3, max_cues=5)
        bible = ProjectBible(project_id="test", title="Test Movie")
        cues = self._make_cues(15)
        batches = seg.segment_cues(cues, bible)
        assert isinstance(batches, list)
        assert len(batches) >= 3  # 15 cues / max 5 per batch
        for batch in batches:
            assert isinstance(batch, SceneBatchModel)
            assert len(batch.cues) >= 3 or len(batch.cues) > 0

    def test_single_cue_segment(self):
        seg = SceneSegmenter(min_cues=1, max_cues=5)
        bible = ProjectBible(project_id="test", title="Test Movie")
        cues = self._make_cues(1)
        batches = seg.segment_cues(cues, bible)
        assert len(batches) >= 1

    def test_exact_batch_size(self):
        seg = SceneSegmenter(min_cues=5, max_cues=5)
        bible = ProjectBible(project_id="test", title="Test Movie")
        cues = self._make_cues(10)
        batches = seg.segment_cues(cues, bible)
        assert len(batches) == 2

    def test_batch_scene_ids_unique(self):
        seg = SceneSegmenter(min_cues=3, max_cues=5)
        bible = ProjectBible(project_id="test", title="Test Movie")
        cues = self._make_cues(15)
        batches = seg.segment_cues(cues, bible)
        scene_ids = [b.scene_id for b in batches]
        assert len(scene_ids) == len(set(scene_ids))


# ─── Context Bible Tests ──────────────────────────────────────────────────────

class TestProjectBible:

    def test_bible_creation(self):
        bible = ProjectBible(project_id="movie_001", title="The Dark Warrior")
        assert bible.project_id == "movie_001"
        assert bible.title == "The Dark Warrior"

    def test_context_package(self):
        ctx = ContextPackage(scene_id="S001")
        assert ctx.scene_id == "S001"
        dump = ctx.model_dump()
        assert "scene_id" in dump


# ─── Review Queue Tests ──────────────────────────────────────────────────────

class TestReviewQueue:

    def test_add_and_retrieve(self):
        from hawsub.core.qc.engine import QCEvaluationResult, QCIssue
        from hawsub.core.qc.verifier import VerificationAuditRecord

        queue = ReviewQueue()
        cue = SubtitleCueModel(id=1, start_ms=0, end_ms=3000, source_text="Hello.", target_text="سڵاو.")
        qc = QCEvaluationResult(cue_id=1, passed=False, overall_confidence=0.72, requires_review=True, issues=[
            QCIssue(cue_id=1, category="semantic", rule="meaning_fidelity", severity="major", score_impact=0.2, message="Possible meaning loss"),
        ])
        audit = VerificationAuditRecord(
            cue_id=1, primary_translation="سڵاو.", verifier_decision="disagree",
            verifier_severity="major", reason="Translation incorrect",
            escalated_to_human=True
        )

        queue.add_cue_for_review(cue, qc, "S001", audit)
        items = queue.get_pending_items()
        assert len(items) >= 1

    def test_empty_queue(self):
        queue = ReviewQueue()
        items = queue.get_pending_items()
        assert len(items) == 0


# ─── ASR Adapter Tests ────────────────────────────────────────────────────────

class TestASRAdapter:

    def test_mismatch_scoring(self):
        asr = ASRAdapter()
        score = asr.score_mismatch("hello world", "hello world")
        assert score == 0.0  # Identical

        score2 = asr.score_mismatch("hello world", "goodbye world")
        assert 0.0 < score2 < 1.0

        score3 = asr.score_mismatch("", "")
        assert score3 == 0.0

    def test_suspicious_name_detection(self):
        asr = ASRAdapter()
        names = asr.detect_suspicious_names("John told Captain Miller to stop.")
        assert "Captain" in names or "Miller" in names

    def test_no_suspicious_names(self):
        asr = ASRAdapter()
        names = asr.detect_suspicious_names("hello world how are you")
        assert len(names) == 0

    def test_verify_cue_without_audio(self):
        asr = ASRAdapter()
        cue = SubtitleCueModel(id=1, start_ms=0, end_ms=3000, source_text="Hello.")
        result = asr.verify_cue(cue, audio_path=None)
        assert isinstance(result, AlignmentResult)
        assert result.mismatch_score == 0.0


# ─── Config Loader Tests ──────────────────────────────────────────────────────

class TestConfigLoader:

    def test_default_config_loads(self):
        config = load_config()
        assert isinstance(config, HawsubConfig)
        assert config.project.target_language == "ckb"
        assert config.translation.provider == "google"

    def test_config_from_file(self):
        config = load_config("config/hawsub.yaml")
        assert isinstance(config, HawsubConfig)
        assert config.sorani.force_ckb is True

    def test_config_nonexistent_file_returns_default(self):
        config = load_config("/nonexistent/path.yaml")
        assert isinstance(config, HawsubConfig)

    def test_config_qc_profile_defaults(self):
        config = load_config()
        profile = config.profiles.get("house_standard")
        assert profile is not None
        assert profile.max_lines == 2
        assert profile.preferred_cps == 17.0
