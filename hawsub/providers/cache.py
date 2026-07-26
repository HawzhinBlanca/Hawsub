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


class CachedSemanticModel:
    """Transparent caching wrapper around any SemanticModel."""

    def __init__(self, base_model, cache_dir: str = ".hawsub_cache"):
        self._base = base_model
        self._disk_cache = RequestCache(cache_dir)
        self._memory_cache: Dict[str, Any] = {}

    @property
    def provider_name(self) -> str:
        return self._base.provider_name

    @property
    def model_name(self) -> str:
        return self._base.model_name

    def _cache_key(self, method: str, **kwargs) -> str:
        raw = f"{method}:{json.dumps(kwargs, sort_keys=True, ensure_ascii=False)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def translate_scene(self, scene_id, cues_data, interpretations, context_data):
        key = self._cache_key(
            "translate", scene_id=scene_id,
            cues_data=cues_data, context_data=context_data,
        )
        if key in self._memory_cache:
            return self._memory_cache[key]

        result = self._base.translate_scene(scene_id, cues_data, interpretations, context_data)
        self._memory_cache[key] = result
        return result

    def analyze_scene(self, scene_id, cues_data, context_data):
        key = self._cache_key(
            "analyze", scene_id=scene_id,
            cues_data=cues_data, context_data=context_data,
        )
        if key in self._memory_cache:
            return self._memory_cache[key]

        result = self._base.analyze_scene(scene_id, cues_data, context_data)
        self._memory_cache[key] = result
        return result

    def verify_translation(self, source_text, current_translation, meaning, context_data):
        key = self._cache_key(
            "verify", source_text=source_text,
            current_translation=current_translation,
        )
        if key in self._memory_cache:
            return self._memory_cache[key]

        result = self._base.verify_translation(source_text, current_translation, meaning, context_data)
        self._memory_cache[key] = result
        return result

