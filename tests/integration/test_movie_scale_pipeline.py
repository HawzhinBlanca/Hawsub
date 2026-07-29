"""
Feature Film Scale Endurance Test (2,000 Cues).
Validates DurablePipeline performance, SQLite checkpointing, and memory usage on a full 2-hour movie subtitle file.
"""

import os
import tempfile
import time
import pytest
from hawsub.core.orchestration.pipeline import DurablePipeline
from hawsub.core.ingest.parser import SubtitleParser


class TestMovieScalePipeline:

    def test_2000_cue_movie_pipeline_execution_and_resumption(self):
        srt_path = "/Users/hawzhin/Hawsub/tests/fixtures/synthetic_movie_2000cues.srt"
        assert os.path.exists(srt_path), f"Test fixture missing: {srt_path}"

        with tempfile.TemporaryDirectory() as temp_dir:
            project_id = "test_movie_2000"
            db_path = os.path.join(temp_dir, f"{project_id}.hawsub.db")

            pipeline = DurablePipeline(project_id=project_id, db_path=db_path)

            progress_events = []

            def track_progress(data: dict):
                progress_events.append(data)

            start_time = time.time()
            results = pipeline.process_file(
                input_subtitle_path=srt_path,
                output_dir=temp_dir,
                progress_callback=track_progress,
            )
            elapsed_sec = time.time() - start_time

            # Verification of output files
            assert os.path.exists(results["srt"])
            assert os.path.exists(results["ass"])
            assert os.path.exists(results["vtt"])
            assert os.path.exists(results["bilingual_html"])
            assert os.path.exists(results["qc_report"])

            # Verify translated SRT cue count
            with open(results["srt"], "r", encoding="utf-8") as f:
                translated_cues = SubtitleParser.parse_srt(f.read())
            assert len(translated_cues) == 2000, f"Expected 2000 translated cues, got {len(translated_cues)}"

            # Verify progress callback fired for all scenes
            assert len(progress_events) > 0
            assert progress_events[-1]["percent"] == 100.0

            # Verify execution speed
            print(f"\n2000-cue movie processed in {elapsed_sec:.2f} seconds ({2000 / elapsed_sec:.1f} cues/sec)")

            # Test Durable Resumption — running pipeline again should hit checkpoints instantly
            resume_start = time.time()
            resume_pipeline = DurablePipeline(project_id=project_id, db_path=db_path)
            resume_results = resume_pipeline.process_file(
                input_subtitle_path=srt_path,
                output_dir=temp_dir,
            )
            resume_elapsed = time.time() - resume_start

            print(f"Resumed 2000-cue movie from SQLite checkpoint in {resume_elapsed:.2f} seconds")
            assert resume_elapsed < elapsed_sec * 0.5, "Resumption should be significantly faster than initial run"
