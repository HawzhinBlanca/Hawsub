"""
Content-Addressed Cache for LLM Requests & Provider Responses.
"""

import os
import hashlib
import json
from pathlib import Path
from typing import Optional, Dict, Any


class RequestCache:
    """Disk-backed content-addressed cache for LLM requests."""

    def __init__(self, cache_dir: str = ".hawsub_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def compute_cache_key(
        self,
        provider: str,
        model: str,
        prompt_version: str,
        source_text: str,
        context_hash: str = "",
        glossary_hash: str = "",
        config_hash: str = "",
    ) -> str:
        raw_key = f"{provider}:{model}:{prompt_version}:{source_text}:{context_hash}:{glossary_hash}:{config_hash}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        file_path = self.cache_dir / f"{cache_key}.json"
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def set(self, cache_key: str, data: Dict[str, Any]) -> None:
        file_path = self.cache_dir / f"{cache_key}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
