"""
Semantic Interpreter for Hawsub.
Executes Pass 1 (Narrative analysis & subtext extraction) using versioned prompts.
"""

import os
from pathlib import Path
from typing import List, Dict, Optional, Any
from hawsub.providers.base import SemanticModel, SemanticInterpretationResponse, SemanticInterpretationItem
from hawsub.core.ingest.parser import SubtitleCueModel
from hawsub.core.context.bible import ContextPackage


class SemanticInterpreter:
    """Performs Pass 1 narrative & semantic interpretation on cue batches."""

    def __init__(self, provider: SemanticModel, prompt_file: str = "prompts/semantic_v1.txt"):
        self.provider = provider
        self.prompt_template = self._load_prompt(prompt_file)

    def _load_prompt(self, prompt_file: str) -> str:
        if os.path.exists(prompt_file):
            with open(prompt_file, "r", encoding="utf-8") as f:
                return f.read()
        return "Analyze intended meaning, tone, register, and subtext before translating."

    def analyze_batch(
        self, scene_id: str, cues: List[SubtitleCueModel], context: ContextPackage
    ) -> SemanticInterpretationResponse:
        cues_data = [
            {"id": c.id, "source_text": c.clean_source_text, "speaker": c.speaker}
            for c in cues
        ]
        ctx_data = context.model_dump()
        return self.provider.analyze_scene(scene_id, cues_data, ctx_data)
