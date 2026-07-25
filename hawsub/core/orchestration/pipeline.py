"""
Durable Pipeline Orchestrator & Checkpoint Engine.
Manages stage transitions, SQLite project state, scene checkpoints, and crash recovery.
"""

import os
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from hawsub.config.schema import HawsubConfig
from hawsub.config.loader import load_config
from hawsub.core.ingest.parser import SubtitleParser, SubtitleCueModel
from hawsub.core.source_resolver.resolver import SourceResolver, SubtitleTrackInfo
from hawsub.core.context.bible import ProjectBible
from hawsub.core.scene.segmenter import SceneSegmenter, SceneBatchModel
from hawsub.providers.factory import get_provider
from hawsub.providers.base import SemanticModel
from hawsub.core.routing.foreign_dialogue import ForeignDialogueRouter
from hawsub.core.adaptation.engine import AdaptationEngine
from hawsub.core.qc.engine import QCEngine, QCEvaluationResult
from hawsub.core.qc.verifier import SecondModelVerifier, VerificationAuditRecord
from hawsub.core.review.queue import ReviewQueue
from hawsub.core.export.exporters import SubtitleExporter
from hawsub.utils.logging import setup_logger

logger = setup_logger("hawsub.orchestrator")


class DurablePipeline:
    """Orchestrates end-to-end Hawsub localization job with scene-level SQLite checkpoints."""

    def __init__(
        self,
        project_id: str,
        config: Optional[HawsubConfig] = None,
        db_path: Optional[str] = None,
    ):
        self.project_id = project_id
        self.config = config or load_config()
        self.db_path = db_path or f"{project_id}.hawsub.db"
        
        self.normalizer_config = self.config.sorani
        self.provider: SemanticModel = get_provider(
            provider_name=self.config.translation.provider,
            model_name=self.config.translation.model,
            temperature=self.config.semantic.temperature,
        )
        self.verifier_provider: SemanticModel = get_provider(
            provider_name=self.config.verification.provider,
            model_name=self.config.verification.model,
        )

        self.segmenter = SceneSegmenter(
            min_cues=self.config.translation.scene_batch_min_cues,
            max_cues=self.config.translation.scene_batch_max_cues,
        )
        self.foreign_router = ForeignDialogueRouter()
        self.adaptation_engine = AdaptationEngine(self.config.profiles.get("house_standard"))
        self.qc_engine = QCEngine(self.config.qc, self.config.profiles.get("house_standard"))
        self.verifier = SecondModelVerifier(self.verifier_provider, self.config.verification.trigger_threshold)
        self.review_queue = ReviewQueue()

        self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initialize project SQLite database schema for state checkpointing."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_state (
                    project_id TEXT PRIMARY KEY,
                    status TEXT,
                    current_stage TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scene_checkpoints (
                    scene_id TEXT PRIMARY KEY,
                    project_id TEXT,
                    status TEXT,
                    translations_json TEXT,
                    qc_results_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

    def set_stage_status(self, stage: str, status: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO project_state (project_id, status, current_stage) VALUES (?, ?, ?)",
                (self.project_id, status, stage),
            )
            conn.commit()

    def get_scene_checkpoint(self, scene_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status, translations_json, qc_results_json FROM scene_checkpoints WHERE scene_id = ?",
                (scene_id,),
            )
            row = cursor.fetchone()
            if row and row[0] == "completed":
                return {
                    "translations": json.loads(row[1]),
                    "qc_results": json.loads(row[2]),
                }
        return None

    def save_scene_checkpoint(
        self, scene_id: str, translations: List[Dict[str, Any]], qc_results: List[Dict[str, Any]]
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO scene_checkpoints (scene_id, project_id, status, translations_json, qc_results_json) VALUES (?, ?, 'completed', ?, ?)",
                (scene_id, self.project_id, json.dumps(translations, ensure_ascii=False), json.dumps(qc_results, ensure_ascii=False)),
            )
            conn.commit()

    def process_file(
        self, input_subtitle_path: str, output_dir: str = "output"
    ) -> Dict[str, str]:
        """Execute full end-to-end subtitle localization pipeline."""
        logger.info(f"Starting Hawsub pipeline for project {self.project_id}")
        self.set_stage_status("INGEST", "in_progress")

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 1. Ingest
        with open(input_subtitle_path, "r", encoding="utf-8") as f:
            content = f.read()

        ext = os.path.splitext(input_subtitle_path)[1].lower()
        if ext == ".vtt":
            cues = SubtitleParser.parse_vtt(content)
        else:
            cues = SubtitleParser.parse_srt(content)

        logger.info(f"Ingested {len(cues)} subtitle cues from {input_subtitle_path}")
        self.set_stage_status("INGEST", "completed")

        # 2. Context & Scene Segmentation
        self.set_stage_status("SCENE_SEGMENTATION", "in_progress")
        bible = ProjectBible(project_id=self.project_id, title="Movie Subtitle")
        scene_batches = self.segmenter.segment_cues(cues, bible)
        logger.info(f"Segmented {len(cues)} cues into {len(scene_batches)} scene batches")
        self.set_stage_status("SCENE_SEGMENTATION", "completed")

        # 3. Process Scenes (with durable checkpointing)
        self.set_stage_status("TRANSLATION_QC", "in_progress")
        all_qc_results: List[QCEvaluationResult] = []

        for batch in scene_batches:
            checkpoint = self.get_scene_checkpoint(batch.scene_id)
            if checkpoint:
                logger.info(f"Resuming scene {batch.scene_id} from durable checkpoint")
                # Restore checkpoint target text
                tr_map = {item["cue_id"]: item["translation"] for item in checkpoint["translations"]}
                for cue in batch.cues:
                    if cue.id in tr_map:
                        cue.target_text = tr_map[cue.id]
                all_qc_results.extend([QCEvaluationResult(**r) for r in checkpoint["qc_results"]])
                continue

            # Process scene
            cues_data = [
                {"id": c.id, "source_text": c.clean_source_text, "start_ms": c.start_ms, "end_ms": c.end_ms}
                for c in batch.cues
            ]
            
            # Check foreign dialogue routing
            for cue in batch.cues:
                route = self.foreign_router.route_cue(cue)
                if route.case_type == "B" and route.sorani_indicator:
                    cue.target_text = route.sorani_indicator

            # Translate unrouted cues
            untranslated_cues = [c for c in batch.cues if not c.target_text]
            if untranslated_cues:
                untr_data = [
                    {"id": c.id, "source_text": c.clean_source_text} for c in untranslated_cues
                ]
                tr_resp = self.provider.translate_scene(
                    scene_id=batch.scene_id,
                    cues_data=untr_data,
                    interpretations=None,
                    context_data=batch.context.model_dump(),
                )
                tr_dict = {item.cue_ids[0]: item.translation for item in tr_resp.translations if item.cue_ids}
                for cue in untranslated_cues:
                    if cue.id in tr_dict:
                        cue.target_text = tr_dict[cue.id]

            # Selective retiming & Adaptation
            scene_qc_results = []
            scene_translations_data = []

            for idx, cue in enumerate(batch.cues):
                next_c = batch.cues[idx + 1] if idx < len(batch.cues) - 1 else None
                cue = self.adaptation_engine.apply_selective_retiming(cue, next_c)

                # Format line breaks if needed
                if cue.target_text:
                    cue.target_text = self.adaptation_engine.format_semantic_line_breaks(cue.target_text)

                qc_res = self.qc_engine.evaluate_cue(cue, next_c)
                scene_qc_results.append(qc_res)
                all_qc_results.append(qc_res)

                # Second model verification if needed
                audit = self.verifier.verify_cue_if_needed(cue, qc_res, meaning_summary="", context_data=batch.context.model_dump())
                
                if qc_res.requires_review or audit.escalated_to_human:
                    self.review_queue.add_cue_for_review(cue, qc_res, batch.scene_id, audit)

                scene_translations_data.append({"cue_id": cue.id, "translation": cue.target_text or ""})

            # Checkpoint completed scene
            self.save_scene_checkpoint(
                scene_id=batch.scene_id,
                translations=scene_translations_data,
                qc_results=[r.model_dump() for r in scene_qc_results],
            )
            logger.info(f"Completed and checkpointed scene {batch.scene_id}")

        self.set_stage_status("TRANSLATION_QC", "completed")

        # 4. Export
        self.set_stage_status("EXPORT", "in_progress")
        srt_path = os.path.join(output_dir, f"{self.project_id}.ckb.srt")
        ass_path = os.path.join(output_dir, f"{self.project_id}.ckb.ass")
        vtt_path = os.path.join(output_dir, f"{self.project_id}.ckb.vtt")
        html_path = os.path.join(output_dir, f"{self.project_id}.bilingual.html")
        qc_report_path = os.path.join(output_dir, f"{self.project_id}.qc_report.json")

        SubtitleExporter.export_srt(cues, srt_path)
        SubtitleExporter.export_ass(cues, ass_path, title=self.project_id)
        SubtitleExporter.export_vtt(cues, vtt_path)
        SubtitleExporter.export_bilingual_debug_html(cues, all_qc_results, html_path)
        SubtitleExporter.export_qc_report(self.project_id, all_qc_results, qc_report_path)

        self.set_stage_status("EXPORT", "completed")
        logger.info(f"Hawsub pipeline finished successfully for project {self.project_id}")

        return {
            "srt": srt_path,
            "ass": ass_path,
            "vtt": vtt_path,
            "bilingual_html": html_path,
            "qc_report": qc_report_path,
        }
