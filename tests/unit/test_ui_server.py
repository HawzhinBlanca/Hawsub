"""
Tests for the Hawsub GUI server — endpoint coverage, auth, health checks.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the Hawsub API."""
    from hawsub.ui.server import app
    return TestClient(app)


@pytest.fixture
def sample_srt_content():
    return (
        "1\n"
        "00:00:01,000 --> 00:00:04,000\n"
        "Hello, world!\n\n"
        "2\n"
        "00:00:05,000 --> 00:00:08,000\n"
        "How are you?\n\n"
    )


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert "uptime_seconds" in data
        assert "python_version" in data
        assert "active_projects" in data

    def test_health_includes_uptime(self, client):
        resp = client.get("/api/health")
        data = resp.json()
        assert data["uptime_seconds"] >= 0


class TestStatsEndpoint:
    def test_stats_returns_200(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "uptime_seconds" in data
        assert "total_requests" in data
        assert "active_projects" in data


class TestGUIIndex:
    def test_index_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Hawsub" in resp.text

    def test_static_css_served(self, client):
        resp = client.get("/static/style.css")
        assert resp.status_code == 200
        assert "text/css" in resp.headers["content-type"]

    def test_static_js_served(self, client):
        resp = client.get("/static/app.js")
        assert resp.status_code == 200


class TestUploadEndpoint:
    def test_upload_srt_file(self, client, sample_srt_content):
        resp = client.post(
            "/api/upload",
            files={"file": ("test.srt", sample_srt_content.encode(), "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "project_id" in data
        assert data["total_cues"] == 2
        assert data["filename"] == "test.srt"
        assert len(data["cues"]) == 2

    def test_upload_empty_file_returns_400(self, client):
        resp = client.post(
            "/api/upload",
            files={"file": ("empty.srt", b"", "text/plain")},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    def test_upload_unsupported_extension_returns_400(self, client):
        resp = client.post(
            "/api/upload",
            files={"file": ("test.txt", b"some text", "text/plain")},
        )
        assert resp.status_code == 400
        assert "unsupported" in resp.json()["detail"].lower()

    def test_upload_whitespace_only_returns_400(self, client):
        resp = client.post(
            "/api/upload",
            files={"file": ("test.srt", b"   \n\n  ", "text/plain")},
        )
        assert resp.status_code == 400

    def test_upload_invalid_srt_returns_400(self, client):
        resp = client.post(
            "/api/upload",
            files={"file": ("test.srt", b"This is not SRT format at all.", "text/plain")},
        )
        assert resp.status_code == 400


class TestProjectEndpoints:
    def test_list_projects_empty(self, client):
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_nonexistent_project_returns_404(self, client):
        resp = client.get("/api/project/proj_nonexistent")
        assert resp.status_code == 404

    def test_invalid_project_id_returns_400(self, client):
        resp = client.get("/api/project/proj_with spaces!")
        assert resp.status_code == 400

    def test_project_lifecycle(self, client, sample_srt_content):
        # Upload
        upload_resp = client.post(
            "/api/upload",
            files={"file": ("lifecycle.srt", sample_srt_content.encode(), "text/plain")},
        )
        assert upload_resp.status_code == 200
        project_id = upload_resp.json()["project_id"]

        # Get project
        get_resp = client.get(f"/api/project/{project_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["total_cues"] == 2

        # List projects
        list_resp = client.get("/api/projects")
        assert list_resp.status_code == 200
        projects = list_resp.json()
        project_ids = [p["project_id"] for p in projects]
        assert project_id in project_ids


class TestCueEditEndpoint:
    def test_edit_cue_target_text(self, client, sample_srt_content):
        # Upload first
        upload_resp = client.post(
            "/api/upload",
            files={"file": ("edit.srt", sample_srt_content.encode(), "text/plain")},
        )
        project_id = upload_resp.json()["project_id"]

        # Edit cue
        edit_resp = client.patch(
            f"/api/cue/{project_id}/1",
            json={"target_text": "سڵاو جیهان!"},
        )
        assert edit_resp.status_code == 200
        assert edit_resp.json()["status"] == "updated"

    def test_edit_nonexistent_cue_returns_404(self, client, sample_srt_content):
        upload_resp = client.post(
            "/api/upload",
            files={"file": ("edit2.srt", sample_srt_content.encode(), "text/plain")},
        )
        project_id = upload_resp.json()["project_id"]

        edit_resp = client.patch(
            f"/api/cue/{project_id}/999",
            json={"target_text": "test"},
        )
        assert edit_resp.status_code == 404

    def test_edit_missing_target_text_returns_400(self, client, sample_srt_content):
        upload_resp = client.post(
            "/api/upload",
            files={"file": ("edit3.srt", sample_srt_content.encode(), "text/plain")},
        )
        project_id = upload_resp.json()["project_id"]

        edit_resp = client.patch(
            f"/api/cue/{project_id}/1",
            json={},
        )
        assert edit_resp.status_code == 400


class TestNormalizeEndpoint:
    def test_normalize_text(self, client):
        resp = client.post("/api/normalize", json={"text": "سڵاو"})
        assert resp.status_code == 200
        data = resp.json()
        assert "original" in data
        assert "normalized" in data

    def test_normalize_empty_text(self, client):
        resp = client.post("/api/normalize", json={"text": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert data["original"] == ""


class TestExportEndpoint:
    def test_export_nonexistent_project_returns_404(self, client):
        resp = client.get("/api/export/proj_nonexistent/srt")
        assert resp.status_code == 404

    def test_export_unknown_format_returns_400(self, client, sample_srt_content):
        upload_resp = client.post(
            "/api/upload",
            files={"file": ("export.srt", sample_srt_content.encode(), "text/plain")},
        )
        project_id = upload_resp.json()["project_id"]
        resp = client.get(f"/api/export/{project_id}/xyz")
        assert resp.status_code == 400

    def test_export_before_processing_returns_404(self, client, sample_srt_content):
        upload_resp = client.post(
            "/api/upload",
            files={"file": ("export2.srt", sample_srt_content.encode(), "text/plain")},
        )
        project_id = upload_resp.json()["project_id"]
        resp = client.get(f"/api/export/{project_id}/srt")
        assert resp.status_code == 404


class TestBenchmarkEndpoint:
    def test_benchmark_returns_200(self, client):
        resp = client.get("/api/benchmark")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_items" in data
        assert data["total_items"] >= 200
        assert "overall_benchmark_score" in data
        assert "overall_chrf_score" in data
        assert "category_results" in data
        assert len(data["category_results"]) == 10


class TestChrFScoring:
    """Test the chrF implementation directly."""

    def test_identical_strings_score_1(self):
        from hawsub.benchmark.suite import compute_chrf
        assert compute_chrf("hello world", "hello world") == 1.0

    def test_empty_vs_nonempty_score_0(self):
        from hawsub.benchmark.suite import compute_chrf
        assert compute_chrf("hello", "") == 0.0

    def test_both_empty_score_1(self):
        from hawsub.benchmark.suite import compute_chrf
        assert compute_chrf("", "") == 1.0

    def test_similar_strings_high_score(self):
        from hawsub.benchmark.suite import compute_chrf
        score = compute_chrf("سڵاو جیهان", "سڵاو جیهان!")
        assert score > 0.8

    def test_different_strings_low_score(self):
        from hawsub.benchmark.suite import compute_chrf
        score = compute_chrf("hello world", "xyz abc")
        assert score < 0.3

    def test_partial_overlap(self):
        from hawsub.benchmark.suite import compute_chrf
        score = compute_chrf("the cat sat", "the cat ran")
        assert 0.3 < score < 0.9
