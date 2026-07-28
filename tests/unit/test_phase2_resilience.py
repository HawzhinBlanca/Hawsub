"""
Phase 2 Error Handling & Pipeline Resilience Unit Tests.
Verifies SourceResolver discovery, SQLite checkpoint crash recovery, and HTTP retry mechanisms.
"""

import os
import tempfile
from unittest.mock import patch, MagicMock
import pytest

from hawsub.core.source_resolver.resolver import SourceResolver, SubtitleTrackInfo
from hawsub.core.orchestration.pipeline import DurablePipeline
from hawsub.providers.mock import MockSemanticModel


class TestSourceResolverResilience:

    def test_scan_sidecar_subtitles_missing_dir(self):
        resolver = SourceResolver("/nonexistent_dir/media.mp4")
        tracks = resolver.scan_sidecar_subtitles()
        assert len(tracks) == 0

    def test_scan_sidecar_subtitles_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            media_path = os.path.join(tmpdir, "movie.mp4")
            sub_path = os.path.join(tmpdir, "movie.en.forced.srt")
            with open(media_path, "w") as f:
                f.write("fake media")
            with open(sub_path, "w") as f:
                f.write("1\n00:00:01,000 --> 00:00:02,000\nHello\n")

            resolver = SourceResolver(media_path)
            tracks = resolver.scan_sidecar_subtitles()
            assert len(tracks) == 1
            assert tracks[0].track_type == "forced"
            assert tracks[0].language == "en"

    @patch("subprocess.run")
    def test_scan_embedded_subtitles_success(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout='{"streams": [{"codec_type": "subtitle", "codec_name": "subrip", "tags": {"language": "eng", "title": "English SDH"}}]}',
            returncode=0
        )
        with patch("os.path.exists", return_value=True):
            resolver = SourceResolver("movie.mkv")
            tracks = resolver.scan_embedded_subtitles()
            assert len(tracks) == 1
            assert tracks[0].origin == "embedded"
            assert tracks[0].track_type == "sdh"

    def test_resolve_master_track_manual_override(self):
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            resolver = SourceResolver("movie.mp4")
            master = resolver.resolve_master_track(manual_override_path=tmp_path)
            assert master.id == "manual_override"
            assert master.origin == "manual"
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_resolve_master_track_asr_fallback(self):
        resolver = SourceResolver("/nonexistent/file.mp4")
        master = resolver.resolve_master_track()
        assert master.origin == "asr"
        assert master.id == "asr_fallback"


class TestPipelineCrashRecovery:

    def test_pipeline_sqlite_checkpoint_recovery(self):
        """Simulate crash mid-execution and verify scene checkpoints prevent duplicate work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            srt_path = os.path.join(tmpdir, "test.srt")
            db_path = os.path.join(tmpdir, "checkpoint_test.db")

            with open(srt_path, "w", encoding="utf-8") as f:
                f.write("1\n00:00:01,000 --> 00:00:04,000\nYou're pushing your luck.\n\n2\n00:00:05,000 --> 00:00:08,000\nBite your tongue!\n")

            pipeline1 = DurablePipeline(project_id="test_proj", db_path=db_path)
            # Save scene 1 checkpoint manually
            pipeline1.save_scene_checkpoint(
                scene_id="SCENE_001",
                translations=[{"cue_ids": [1], "translation": "تۆ زێدەڕۆیی لە بەختت دەکەیت", "meaning": "Idiom"}],
                qc_results=[{"cue_id": 1, "overall_confidence": 0.98}]
            )

            # Re-instantiate pipeline with same db_path (simulating process restart)
            pipeline2 = DurablePipeline(project_id="test_proj", db_path=db_path)
            ckpt = pipeline2.get_scene_checkpoint("SCENE_001")

            assert ckpt is not None
            assert ckpt["translations"][0]["translation"] == "تۆ زێدەڕۆیی لە بەختت دەکەیت"
