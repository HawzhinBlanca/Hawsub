import os
import pytest
from hawsub.core.orchestration.pipeline import DurablePipeline
from hawsub.benchmark.suite import BenchmarkSuite
from hawsub.providers.mock import MockSemanticModel
from hawsub.config.loader import load_config

SAMPLE_ENGLISH_SRT = """1
00:00:10,000 --> 00:00:13,500
JOHN: Hello my friend.

2
00:00:14,000 --> 00:00:17,000
You're pushing your luck.

3
00:00:18,000 --> 00:00:20,500
I told you to stop.

4
00:00:21,000 --> 00:00:23,000
[Speaking Spanish]

5
00:00:24,000 --> 00:00:26,000
Thank you very much.
"""


def test_full_pipeline_e2e(tmp_path):
    input_file = tmp_path / "test_movie.en.srt"
    input_file.write_text(SAMPLE_ENGLISH_SRT, encoding="utf-8")

    out_dir = tmp_path / "output"
    db_path = str(tmp_path / "test_proj.db")

    pipeline = DurablePipeline(project_id="test_movie", db_path=db_path)
    res = pipeline.process_file(str(input_file), output_dir=str(out_dir))

    # Verify generated output files
    assert os.path.exists(res["srt"])
    assert os.path.exists(res["ass"])
    assert os.path.exists(res["vtt"])
    assert os.path.exists(res["bilingual_html"])
    assert os.path.exists(res["qc_report"])

    # Inspect exported SRT content
    with open(res["srt"], "r", encoding="utf-8") as f:
        srt_content = f.read()
        assert "سڵاو" in srt_content
        assert "تۆ زێدەڕۆیی لە بەختت دەکەیت" in srt_content
        assert "[ئیسپانی دەدوێت]" in srt_content or "دەدوێت" in srt_content


def test_pipeline_resumability(tmp_path):
    input_file = tmp_path / "test_resumable.en.srt"
    input_file.write_text(SAMPLE_ENGLISH_SRT, encoding="utf-8")

    out_dir = tmp_path / "output_resume"
    db_path = str(tmp_path / "test_resume.db")

    pipeline = DurablePipeline(project_id="test_resumable", db_path=db_path)
    res1 = pipeline.process_file(str(input_file), output_dir=str(out_dir))

    # Run second time on same project database to verify resumption
    pipeline2 = DurablePipeline(project_id="test_resumable", db_path=db_path)
    res2 = pipeline2.process_file(str(input_file), output_dir=str(out_dir))

    assert res1["srt"] == res2["srt"]


def test_benchmark_suite():
    model = MockSemanticModel()
    suite = BenchmarkSuite(dataset_path="tests/gold/gold_dataset.json")
    report = suite.evaluate_model(model)

    assert report.total_items > 0
    assert report.overall_benchmark_score > 0.5
