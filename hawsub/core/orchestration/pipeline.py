"""
Durable Pipeline Orchestrator & Checkpoint Engine.
Manages stage transitions, SQLite project state, scene checkpoints, and crash recovery.
"""

import os
import sqlite3
import json
import time
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
from hawsub.core.translation.memory import TranslationMemory
from hawsub.core.context.glossary import GlossaryEngine
from hawsub.utils.logging import setup_logger

logger = setup_logger("hawsub.orchestrator")

# Maximum file size (10 MB) to prevent memory issues
MAX_INPUT_FILE_SIZE = 10 * 1024 * 1024


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
        self.translation_memory = TranslationMemory(
            db_path=os.path.join(os.path.dirname(self.db_path), f"{project_id}.tm.db")
        )
        self.glossary = GlossaryEngine()

        # TM hit-rate tracking
        self._tm_hits = 0
        self._tm_lookups = 0

        self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initialize project SQLite database schema for state checkpointing."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            # Check if project_state table exists with old single-PK schema and migrate
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project_state'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(project_state)")
                columns = {row[1]: row[5] for row in cursor.fetchall()}  # name -> pk_index
                # Old schema had project_id as only PK (pk=1), current_stage as non-PK (pk=0)
                if columns.get("current_stage", 0) == 0:
                    cursor.execute("DROP TABLE project_state")
                    logger.info("Migrated project_state table to composite primary key schema")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_state (
                    project_id TEXT NOT NULL,
                    current_stage TEXT NOT NULL,
                    status TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (project_id, current_stage)
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
        finally:
            conn.close()

    def set_stage_status(self, stage: str, status: str) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO project_state (project_id, status, current_stage) VALUES (?, ?, ?)",
                (self.project_id, status, stage),
            )
            conn.commit()
        finally:
            conn.close()

    def get_stage_status(self, stage: str) -> Optional[str]:
        """Get the current status of a pipeline stage."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status FROM project_state WHERE project_id = ? AND current_stage = ?",
                (self.project_id, stage),
            )
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()


    def get_scene_checkpoint(self, scene_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
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
        finally:
            conn.close()
        return None

    def save_scene_checkpoint(
        self, scene_id: str, translations: List[Dict[str, Any]], qc_results: List[Dict[str, Any]]
    ) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO scene_checkpoints (scene_id, project_id, status, translations_json, qc_results_json) VALUES (?, ?, 'completed', ?, ?)",
                (scene_id, self.project_id, json.dumps(translations, ensure_ascii=False), json.dumps(qc_results, ensure_ascii=False)),
            )
            conn.commit()
        finally:
            conn.close()

    def process_file(
        self, input_subtitle_path: str, output_dir: str = "output"
    ) -> Dict[str, str]:
        """Execute full end-to-end subtitle localization pipeline."""
        logger.info(f"Starting Hawsub pipeline for project {self.project_id}")
        self.set_stage_status("INGEST", "in_progress")

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 1. Ingest — with input validation
        input_path = Path(input_subtitle_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_subtitle_path}")
        
        file_size = input_path.stat().st_size
        if file_size == 0:
            raise ValueError(f"Input file is empty: {input_subtitle_path}")
        if file_size > MAX_INPUT_FILE_SIZE:
            raise ValueError(f"Input file too large ({file_size} bytes, max {MAX_INPUT_FILE_SIZE}): {input_subtitle_path}")

        with open(input_subtitle_path, "r", encoding="utf-8-sig") as f:
            content = f.read()

        if not content.strip():
            raise ValueError(f"Input file contains no content: {input_subtitle_path}")

        cues = SubtitleParser.parse_auto(content, input_subtitle_path)

        if not cues:
            raise ValueError(f"No subtitle cues parsed from: {input_subtitle_path}")

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
            try:
                checkpoint = self.get_scene_checkpoint(batch.scene_id)
                if checkpoint:
                    logger.info(f"Resuming scene {batch.scene_id} from durable checkpoint")
                    tr_map = {item["cue_id"]: item["translation"] for item in checkpoint["translations"]}
                    for cue in batch.cues:
                        if cue.id in tr_map:
                            cue.target_text = tr_map[cue.id]
                    all_qc_results.extend([QCEvaluationResult(**r) for r in checkpoint["qc_results"]])
                    continue

                # Foreign dialogue routing
                for cue in batch.cues:
                    route = self.foreign_router.route_cue(cue)
                    if route.case_type == "B" and route.sorani_indicator:
                        cue.target_text = route.sorani_indicator

                # Semantic interpretation pass
                from hawsub.core.semantic.interpreter import SemanticInterpreter
                interpreter = SemanticInterpreter(self.provider)
                interp_result = interpreter.analyze_batch(batch.scene_id, batch.cues, batch.context)

                # Check Translation Memory before calling LLM
                untranslated_cues = [c for c in batch.cues if not c.target_text]
                tm_resolved_cues = []
                still_untranslated = []

                for cue in untranslated_cues:
                    self._tm_lookups += 1
                    tm_match = self.translation_memory.find_fuzzy_match(cue.clean_source_text, threshold=0.92)
                    if tm_match:
                        cue.target_text = tm_match.target_text
                        tm_resolved_cues.append(cue)
                        self._tm_hits += 1
                        logger.info(f"TM hit for cue {cue.id}: score={tm_match.similarity_score}")
                    else:
                        still_untranslated.append(cue)

                if tm_resolved_cues:
                    logger.info(f"TM resolved {len(tm_resolved_cues)}/{len(untranslated_cues)} cues in scene {batch.scene_id}")

                # Prepare glossary terms string for prompt injection
                glossary_lines = []
                for key, term in self.glossary.terms.items():
                    glossary_lines.append(f"  {term.source_term} → {term.target_sorani} ({term.category})")
                glossary_str = "\n".join(glossary_lines) if glossary_lines else None

                # Translate remaining unresolved cues via LLM
                if still_untranslated:
                    untr_data = [{"id": c.id, "source_text": c.clean_source_text} for c in still_untranslated]
                    tr_resp = self.provider.translate_scene(
                        scene_id=batch.scene_id,
                        cues_data=untr_data,
                        interpretations=interp_result.items if interp_result else None,
                        context_data=batch.context.model_dump(),
                        glossary_terms=glossary_str,
                    )
                    tr_dict = {item.cue_ids[0]: item.translation for item in tr_resp.translations if item.cue_ids}
                    for cue in still_untranslated:
                        if cue.id in tr_dict:
                            cue.target_text = tr_dict[cue.id]

                # Apply glossary enforcement post-translation
                for cue in batch.cues:
                    if cue.target_text:
                        cue.target_text = self.glossary.apply_glossary(cue.clean_source_text, cue.target_text)

                # Adaptation, QC & Verification
                scene_qc_results = []
                scene_translations_data = []
                prev_translation = None

                for idx, cue in enumerate(batch.cues):
                    next_c = batch.cues[idx + 1] if idx < len(batch.cues) - 1 else None
                    cue = self.adaptation_engine.apply_selective_retiming(cue, next_c)

                    if cue.target_text:
                        cue.target_text = self.adaptation_engine.format_semantic_line_breaks(cue.target_text)

                    qc_res = self.qc_engine.evaluate_cue(cue, next_c, prev_translation=prev_translation)
                    prev_translation = cue.target_text
                    scene_qc_results.append(qc_res)
                    all_qc_results.append(qc_res)

                    meaning_summary = ""
                    interp_items = interp_result.items if interp_result else []
                    for interp in interp_items:
                        if cue.id in interp.cue_ids:
                            meaning_summary = interp.intended_meaning
                            break

                    audit = self.verifier.verify_cue_if_needed(
                        cue, qc_res, meaning_summary=meaning_summary, context_data=batch.context.model_dump()
                    )

                    if qc_res.requires_review or audit.escalated_to_human:
                        self.review_queue.add_cue_for_review(cue, qc_res, batch.scene_id, audit)

                    scene_translations_data.append({"cue_id": cue.id, "translation": cue.target_text or ""})

                    # Store approved translations in Translation Memory
                    if qc_res.passed and cue.target_text and cue.clean_source_text:
                        self.translation_memory.store_translation(
                            source_text=cue.clean_source_text,
                            target_text=cue.target_text,
                            context_notes=f"scene:{batch.scene_id} project:{self.project_id}",
                        )

                self.save_scene_checkpoint(
                    scene_id=batch.scene_id,
                    translations=scene_translations_data,
                    qc_results=[r.model_dump() for r in scene_qc_results],
                )
                logger.info(f"Completed and checkpointed scene {batch.scene_id}")

            except Exception as e:
                # Per-scene retry with exponential backoff
                MAX_SCENE_RETRIES = 2
                retry_success = False

                for retry_num in range(1, MAX_SCENE_RETRIES + 1):
                    logger.warning(
                        f"Scene {batch.scene_id} failed (attempt {retry_num}/{MAX_SCENE_RETRIES}): {e}"
                    )
                    backoff_seconds = 2 ** retry_num
                    time.sleep(min(backoff_seconds, 10))

                    try:
                        # Re-attempt only the translation step for failed scene
                        untranslated = [c for c in batch.cues if not c.target_text]
                        if untranslated:
                            untr_data = [{"id": c.id, "source_text": c.clean_source_text} for c in untranslated]
                            tr_resp = self.provider.translate_scene(
                                scene_id=batch.scene_id,
                                cues_data=untr_data,
                                interpretations=None,
                                context_data={},
                            )
                            tr_dict = {item.cue_ids[0]: item.translation for item in tr_resp.translations if item.cue_ids}
                            for cue in untranslated:
                                if cue.id in tr_dict:
                                    cue.target_text = tr_dict[cue.id]

                        # Re-run QC on recovered cues
                        for cue in batch.cues:
                            qc_res = self.qc_engine.evaluate_cue(cue)
                            all_qc_results.append(qc_res)

                        self.save_scene_checkpoint(
                            scene_id=batch.scene_id,
                            translations=[{"cue_id": c.id, "translation": c.target_text or ""} for c in batch.cues],
                            qc_results=[r.model_dump() for r in all_qc_results[-len(batch.cues):]],
                        )
                        logger.info(f"Scene {batch.scene_id} recovered on retry {retry_num}")
                        retry_success = True
                        break
                    except Exception as retry_e:
                        logger.error(f"Scene {batch.scene_id} retry {retry_num} also failed: {retry_e}")
                        continue

                if not retry_success:
                    logger.error(f"Scene {batch.scene_id} failed after {MAX_SCENE_RETRIES} retries. Marking as failed.")
                    self.set_stage_status(f"SCENE_{batch.scene_id}", "failed")
                    # Generate placeholder QC results for failed scene cues
                    for cue in batch.cues:
                        all_qc_results.append(QCEvaluationResult(
                            cue_id=cue.id,
                            overall_confidence=0.0,
                            passed=False,
                            requires_review=True,
                        ))
                continue

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

        # Log TM hit-rate
        tm_hit_rate = round(self._tm_hits / self._tm_lookups * 100, 1) if self._tm_lookups > 0 else 0.0
        logger.info(f"TM hit rate: {self._tm_hits}/{self._tm_lookups} ({tm_hit_rate}%)")

        # Compute quality summary
        total_cues = len(all_qc_results)
        passed_cues = sum(1 for r in all_qc_results if r.passed)
        critical_issues = sum(1 for r in all_qc_results for i in r.issues if i.severity == "critical")
        failed_scenes = sum(1 for batch in scene_batches if self.get_stage_status(f"SCENE_{batch.scene_id}") == "failed")
        review_queue_size = len(self.review_queue.get_pending_items())

        pass_rate = round(passed_cues / total_cues * 100, 1) if total_cues > 0 else 0.0
        logger.info(
            f"Quality summary: {passed_cues}/{total_cues} passed ({pass_rate}%), "
            f"{critical_issues} critical issues, {failed_scenes} failed scenes, "
            f"{review_queue_size} pending reviews"
        )
        logger.info(f"Hawsub pipeline finished successfully for project {self.project_id}")

        return {
            "srt": srt_path,
            "ass": ass_path,
            "vtt": vtt_path,
            "bilingual_html": html_path,
            "qc_report": qc_report_path,
            "tm_hit_rate": tm_hit_rate,
            "quality_summary": {
                "total_cues": total_cues,
                "passed_cues": passed_cues,
                "pass_rate": pass_rate,
                "critical_issues": critical_issues,
                "failed_scenes": failed_scenes,
                "review_queue_size": review_queue_size,
            },
        }

