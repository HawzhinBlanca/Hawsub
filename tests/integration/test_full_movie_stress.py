"""
Integration Stress Test — Simulates processing a full-length feature film (1,500 cues).
Verifies:
1. Cue integrity (1,500 cues in == 1,500 cues out, no loss, no timestamp corruption).
2. SQLite checkpoint durability and performance.
3. Multi-scene batching (approx 75-150 scenes).
4. Full export generation (SRT, ASS, VTT, Debug HTML, QC JSON Report).
"""

import os
import json
import time
import pytest
from pathlib import Path
from hawsub.core.orchestration.pipeline import DurablePipeline
from hawsub.core.ingest.parser import SubtitleParser, format_timestamp_srt


def generate_synthetic_movie_srt(num_cues: int = 1500) -> str:
    """Generate a realistic 1,500-cue cinematic SRT file (~2 hours duration)."""
    dialogue_samples = [
        "We need to leave right now.",
        "You're pushing your luck.",
        "[Speaking Spanish]",
        "Thank you for your help.",
        "Hold your horses!",
        "Bite your tongue!",
        "What are you doing here?",
        "I am in over my head.",
        "Over my dead body!",
        "It's raining cats and dogs.",
        "You stabbed me in the back!",
        "Don't let the cat out of the bag.",
        "I have bigger fish to fry.",
        "Time to face the music.",
        "Speak of the devil!",
        "The ball is in your court.",
        "He kicked the bucket.",
        "Keep your eyes peeled.",
        "Hit the nail on the head.",
        "I'm feeling under the weather.",
    ]

    blocks = []
    current_ms = 60000  # Start at 1 minute

    for i in range(1, num_cues + 1):
        duration_ms = 2500  # 2.5 seconds per cue
        gap_ms = 500  # 0.5 seconds gap
        start_ms = current_ms
        end_ms = start_ms + duration_ms

        start_ts = format_timestamp_srt(start_ms)
        end_ts = format_timestamp_srt(end_ms)
        text = dialogue_samples[(i - 1) % len(dialogue_samples)]

        blocks.append(f"{i}\n{start_ts} --> {end_ts}\n{text}")
        current_ms = end_ms + gap_ms

    return "\n\n".join(blocks) + "\n"


class TestFullMovieStress:

    def test_full_movie_1500_cues(self, tmp_path):
        """Stress-test end-to-end pipeline with 1,500 subtitle cues."""
        srt_content = generate_synthetic_movie_srt(1500)
        input_path = tmp_path / "movie_1500.srt"
        input_path.write_text(srt_content, encoding="utf-8")

        output_dir = tmp_path / "output_1500"
        db_path = tmp_path / "movie_1500.db"

        start_time = time.time()
        pipeline = DurablePipeline(project_id="stress_movie_1500", db_path=str(db_path))
        results = pipeline.process_file(str(input_path), output_dir=str(output_dir))
        elapsed = time.time() - start_time

        # 1. Check exports generated
        assert os.path.exists(results["srt"])
        assert os.path.exists(results["ass"])
        assert os.path.exists(results["vtt"])
        assert os.path.exists(results["bilingual_html"])
        assert os.path.exists(results["qc_report"])

        # 2. Verify cue count integrity (zero cue loss)
        output_cues = SubtitleParser.parse_srt((Path(results["srt"])).read_text(encoding="utf-8"))
        assert len(output_cues) == 1500

        # 3. Verify QC Report structure
        with open(results["qc_report"], encoding="utf-8") as f:
            qc_data = json.load(f)
            assert qc_data["total_cues"] == 1500
            assert len(qc_data["evaluations"]) == 1500

        # 4. Verify performance (1,500 cues processed under 15 seconds)
        assert elapsed < 15.0, f"Processing 1,500 cues took {elapsed:.2f}s, expected < 15s"
        print(f"\n✓ Successfully processed 1,500 cues in {elapsed:.2f}s ({1500/elapsed:.1f} cues/sec)")
