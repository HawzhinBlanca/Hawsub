"""
Tests for CLI commands, GUI API endpoints, and project export.
"""

import os
import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from hawsub.ui.server import app


client = TestClient(app)


# ─── GUI API Tests ────────────────────────────────────────────────────────────

class TestGUIAPI:

    def test_index_returns_html(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Hawsub" in resp.text
        assert "text/html" in resp.headers["content-type"]

    def test_normalize_endpoint(self):
        resp = client.post("/api/normalize", json={"text": "ئەمە تاقيكردنەوەيە"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["normalized"] == "ئەمە تاقیکردنەوەیە"

    def test_normalize_empty(self):
        resp = client.post("/api/normalize", json={"text": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert data["normalized"] == ""

    def test_benchmark_endpoint(self):
        resp = client.get("/api/benchmark")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_benchmark_score" in data
        assert "total_items" in data
        assert data["total_items"] == 20

    def test_list_projects_empty(self):
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_upload_srt(self):
        srt_content = b"1\n00:01:05,100 --> 00:01:08,400\nHello.\n\n2\n00:01:09,000 --> 00:01:12,200\nGoodbye.\n"
        resp = client.post(
            "/api/upload",
            files={"file": ("test.srt", srt_content, "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "project_id" in data
        assert data["total_cues"] == 2
        assert len(data["cues"]) == 2

    def test_upload_process_pipeline(self):
        # Upload first
        srt_content = b"1\n00:01:05,100 --> 00:01:08,400\nHello world.\n"
        resp = client.post(
            "/api/upload",
            files={"file": ("test_proc.srt", srt_content, "text/plain")},
        )
        data = resp.json()
        pid = data["project_id"]

        # Run process
        resp2 = client.post(f"/api/process/{pid}")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["total_cues"] == 1

    def test_export_without_process_404(self):
        # Upload but don't process
        srt_content = b"1\n00:01:05,100 --> 00:01:08,400\nHello.\n"
        resp = client.post(
            "/api/upload",
            files={"file": ("test_noexport.srt", srt_content, "text/plain")},
        )
        pid = resp.json()["project_id"]
        resp2 = client.get(f"/api/export/{pid}/srt")
        # Should fail because pipeline hasn't run yet
        assert resp2.status_code in (404, 500)

    def test_process_nonexistent_project(self):
        resp = client.post("/api/process/nonexistent_id")
        assert resp.status_code == 404

    def test_export_nonexistent_project(self):
        resp = client.get("/api/export/nonexistent_id/srt")
        assert resp.status_code == 404

    def test_export_invalid_format(self):
        srt_content = b"1\n00:01:05,100 --> 00:01:08,400\nHello.\n"
        resp = client.post(
            "/api/upload",
            files={"file": ("test_fmt.srt", srt_content, "text/plain")},
        )
        pid = resp.json()["project_id"]
        resp2 = client.get(f"/api/export/{pid}/invalid_format")
        assert resp2.status_code == 400

    def test_upload_empty_file(self):
        resp = client.post(
            "/api/upload",
            files={"file": ("empty.srt", b"", "text/plain")},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    def test_upload_unsupported_extension(self):
        resp = client.post(
            "/api/upload",
            files={"file": ("test.txt", b"some content", "text/plain")},
        )
        assert resp.status_code == 400
        assert "Unsupported" in resp.json()["detail"]

    def test_upload_whitespace_only(self):
        resp = client.post(
            "/api/upload",
            files={"file": ("blank.srt", b"   \n  \n  ", "text/plain")},
        )
        assert resp.status_code == 400

    def test_upload_no_parseable_cues(self):
        resp = client.post(
            "/api/upload",
            files={"file": ("bad.srt", b"this is not a valid subtitle file", "text/plain")},
        )
        assert resp.status_code == 400

    def test_upload_bom_file(self):
        """Upload a BOM-prefixed file — should parse correctly."""
        bom_content = b"\xef\xbb\xbf1\n00:00:01,000 --> 00:00:04,000\nBOM test.\n"
        resp = client.post(
            "/api/upload",
            files={"file": ("bom.srt", bom_content, "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cues"] == 1


# ─── CLI Tests ────────────────────────────────────────────────────────────────

class TestCLI:

    def test_version_command(self):
        """Test that CLI module can be imported and version is correct."""
        from hawsub import __version__
        assert __version__ == "1.0.0"
        from hawsub.cli.main import cli
        assert cli is not None

    def test_normalize_cli(self):
        """Test that normalize function works programmatically."""
        from hawsub.core.normalization.sorani import SoraniNormalizer
        norm = SoraniNormalizer()
        result = norm.normalize("تاقيكردنەوە")
        assert "ی" in result  # Arabic ya → Kurdish ya

    def test_config_loader_direct(self):
        from hawsub.config.loader import load_config
        config = load_config()
        assert config.project.target_language == "ckb"
        assert config.translation.provider == "google"
        assert config.sorani.force_ckb is True
        assert config.sorani.forbid_kurmanji is True
        assert config.sorani.rtl_normalization is True

    def test_full_process_cli_mock(self, tmp_path):
        """Test end-to-end process with mock provider."""
        from hawsub.core.orchestration.pipeline import DurablePipeline

        srt_content = "1\n00:00:01,000 --> 00:00:04,000\nThis is a test.\n"
        input_file = str(tmp_path / "test.srt")
        with open(input_file, "w", encoding="utf-8") as f:
            f.write(srt_content)

        output_dir = str(tmp_path / "output")
        db_path = str(tmp_path / "test.db")

        pipeline = DurablePipeline(project_id="cli_test", db_path=db_path)
        results = pipeline.process_file(input_file, output_dir=output_dir)

        assert os.path.exists(results["srt"])
        assert os.path.exists(results["ass"])
        assert os.path.exists(results["vtt"])
        assert os.path.exists(results["bilingual_html"])
        assert os.path.exists(results["qc_report"])

        # Verify QC report
        with open(results["qc_report"], encoding="utf-8") as f:
            report = json.load(f)
            assert report["total_cues"] == 1
            assert report["passed_cues"] >= 0

    def test_process_multiple_cues(self, tmp_path):
        """Test pipeline with multiple cues."""
        from hawsub.core.orchestration.pipeline import DurablePipeline

        srt_content = """1
00:00:01,000 --> 00:00:04,000
You're pushing your luck.

2
00:00:05,000 --> 00:00:08,000
Bite your tongue!

3
00:00:09,000 --> 00:00:12,000
[Speaking Spanish]

4
00:00:13,000 --> 00:00:16,000
Break a leg!
"""
        input_file = str(tmp_path / "multi.srt")
        with open(input_file, "w", encoding="utf-8") as f:
            f.write(srt_content)

        output_dir = str(tmp_path / "multi_out")
        db_path = str(tmp_path / "multi.db")

        pipeline = DurablePipeline(project_id="multi_test", db_path=db_path)
        results = pipeline.process_file(input_file, output_dir=output_dir)

        # Read SRT output
        with open(results["srt"], encoding="utf-8") as f:
            content = f.read()
            # Foreign dialogue should be Sorani-ized
            assert "ئیسپانی" in content  # Spanish in Sorani
            assert len(content.strip()) > 0

        # Verify QC
        with open(results["qc_report"], encoding="utf-8") as f:
            report = json.load(f)
            assert report["total_cues"] == 4
