"""
Phase 3 Input Validation & Security Unit Tests.
Verifies API endpoint path traversal protection, upload validation, and XSS escaping.
"""

import io
import pytest
from starlette.testclient import TestClient
from hawsub.ui.server import app, active_projects, _validate_project_id
from fastapi import HTTPException


class TestSecurityAndValidation:

    def test_validate_project_id_valid(self):
        assert _validate_project_id("proj_12345") == "proj_12345"
        assert _validate_project_id("movie-project-01") == "movie-project-01"

    def test_validate_project_id_path_traversal(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_project_id("../../../etc/passwd")
        assert exc_info.value.status_code == 400

    def test_validate_project_id_special_chars(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_project_id("proj<script>alert(1)</script>")
        assert exc_info.value.status_code == 400

    def test_upload_invalid_file_extension(self):
        client = TestClient(app)
        files = {"file": ("malicious.exe", b"binary data", "application/octet-stream")}
        response = client.post("/api/upload", files=files)
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    def test_upload_empty_file(self):
        client = TestClient(app)
        files = {"file": ("test.srt", b"", "text/plain")}
        response = client.post("/api/upload", files=files)
        assert response.status_code == 400
        assert "file is empty" in response.json()["detail"].lower()

    def test_export_invalid_project_id_format(self):
        client = TestClient(app)
        response = client.get("/api/export/invalid_proj!$/srt")
        assert response.status_code == 400
