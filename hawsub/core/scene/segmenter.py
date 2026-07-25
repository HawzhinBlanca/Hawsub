"""
Scene Segmentation & Cue Batching Engine.
Groups subtitle cues into 10-30 cue semantic scene batches while respecting narrative boundaries.
"""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from hawsub.core.ingest.parser import SubtitleCueModel
from hawsub.core.context.bible import ProjectBible, ContextPackage, CharacterProfile, GlossaryEntryModel


class SceneBatchModel(BaseModel):
    scene_id: str
    start_ms: int
    end_ms: int
    cues: List[SubtitleCueModel]
    context: ContextPackage


class SceneSegmenter:
    """Segments a full list of subtitle cues into manageable scene batches for LLM inference."""

    def __init__(
        self,
        min_cues: int = 10,
        max_cues: int = 30,
        scene_gap_threshold_ms: int = 3500,
    ):
        self.min_cues = min_cues
        self.max_cues = max_cues
        self.scene_gap_threshold_ms = scene_gap_threshold_ms

    def segment_cues(
        self, cues: List[SubtitleCueModel], bible: Optional[ProjectBible] = None
    ) -> List[SceneBatchModel]:
        if not cues:
            return []

        scene_batches: List[SceneBatchModel] = []
        current_cues: List[SubtitleCueModel] = []
        scene_counter = 1

        for i, cue in enumerate(cues):
            current_cues.append(cue)

            # Check if scene boundary is reached
            is_last_cue = i == len(cues) - 1
            is_max_reached = len(current_cues) >= self.max_cues

            gap_to_next = 0
            if not is_last_cue:
                gap_to_next = cues[i + 1].start_ms - cue.end_ms

            is_scene_break = (
                gap_to_next >= self.scene_gap_threshold_ms
                and len(current_cues) >= self.min_cues
            )

            if is_last_cue or is_max_reached or is_scene_break:
                scene_id = f"S{scene_counter:03d}"
                batch = self._build_scene_batch(
                    scene_id, current_cues, bible, scene_counter, scene_batches
                )
                scene_batches.append(batch)
                current_cues = []
                scene_counter += 1

        # Post-process previous/next scene links in context packages
        for idx, batch in enumerate(scene_batches):
            if idx > 0:
                batch.context.previous_scene_summary = f"Summary of Scene {scene_batches[idx-1].scene_id}"
            if idx < len(scene_batches) - 1:
                batch.context.next_scene_hint = f"Upcoming Scene {scene_batches[idx+1].scene_id}"

        return scene_batches

    def _build_scene_batch(
        self,
        scene_id: str,
        cues: List[SubtitleCueModel],
        bible: Optional[ProjectBible],
        scene_counter: int,
        previous_batches: List[SceneBatchModel],
    ) -> SceneBatchModel:
        start_ms = cues[0].start_ms
        end_ms = cues[-1].end_ms
        combined_text = " ".join([c.source_text for c in cues])

        active_chars: List[CharacterProfile] = []
        relevant_glossary: List[GlossaryEntryModel] = []

        if bible:
            active_chars = bible.find_active_characters(combined_text)
            relevant_glossary = bible.find_matching_glossary(combined_text)

        context_hash = ""
        if bible:
            context_hash = bible.compute_context_hash()

        context = ContextPackage(
            scene_id=scene_id,
            scene_summary=f"Scene {scene_id} containing {len(cues)} subtitle cues.",
            active_characters=active_chars,
            relevant_glossary=relevant_glossary,
            context_hash=context_hash,
        )

        return SceneBatchModel(
            scene_id=scene_id,
            start_ms=start_ms,
            end_ms=end_ms,
            cues=cues,
            context=context,
        )
