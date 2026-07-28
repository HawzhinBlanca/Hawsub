"""
Phase 5 Performance & Memory Stress Profiling Integration Tests.
Executes 5,000+ cue normalization, parsing, and pipeline throughput tests under continuous load.
"""

import time
import pytest
from hawsub.core.normalization.sorani import SoraniNormalizer
from hawsub.core.ingest.parser import SubtitleParser, SubtitleCueModel
from hawsub.core.scene.segmenter import SceneSegmenter


class TestPhase5Performance:

    def test_sorani_normalizer_5k_cache_performance(self):
        normalizer = SoraniNormalizer()
        sample_texts = [
            "سڵاو كوردستان",
            "ئەمە تاقیکردنەوەی خێراییە!",
            "تۆ زێدەڕۆیی لە بەختت دەکەیت...",
            "چۆنیت هاوڕێم؟",
            "زۆر سوپاس بۆ هاوکاریت."
        ]

        t0 = time.perf_counter()
        # Process 5,000 iterations to verify memoization speedup
        for i in range(5000):
            text = sample_texts[i % len(sample_texts)]
            res = normalizer.normalize(text)
            assert len(res) > 0

        elapsed = time.perf_counter() - t0
        # 5,000 operations should complete in under 0.15 seconds with memoization
        assert elapsed < 0.15, f"Normalization too slow: {elapsed:.4f}s"

    def test_parser_5k_cues_throughput(self):
        blocks = []
        for i in range(1, 5001):
            blocks.append(f"{i}\n00:00:01,000 --> 00:00:03,000\nThis is subtitle dialogue line number {i}\n")
        content = "\n".join(blocks)

        t0 = time.perf_counter()
        cues = SubtitleParser.parse_srt(content)
        elapsed = time.perf_counter() - t0

        assert len(cues) == 5000
        # 5,000 SRT cue parsing should complete in under 0.50 seconds
        assert elapsed < 0.50, f"SRT parsing too slow: {elapsed:.4f}s"

    def test_scene_segmenter_5k_cues_performance(self):
        cues = [
            SubtitleCueModel(id=i, start_ms=i*2000, end_ms=i*2000+1500, source_text=f"Line {i}")
            for i in range(1, 5001)
        ]
        segmenter = SceneSegmenter(min_cues=20, max_cues=35)

        t0 = time.perf_counter()
        batches = segmenter.segment_cues(cues)
        elapsed = time.perf_counter() - t0

        assert len(batches) > 100
        assert elapsed < 0.20, f"Scene segmentation too slow: {elapsed:.4f}s"
