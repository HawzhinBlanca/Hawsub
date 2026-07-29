"""
Human Feedback & Correction Pipeline for Hawsub.
Captures human edits, tracks correction patterns, and exports training data.
"""

import json
import sqlite3
import os
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class HumanCorrection(BaseModel):
    """A single human correction record."""
    cue_id: int
    source_text: str
    original_translation: str
    corrected_translation: str
    correction_type: str = "edit"  # edit | accept | reject | add_glossary
    reviewer: str = "human_editor"
    project_id: Optional[str] = None
    scene_id: Optional[str] = None
    timestamp: Optional[str] = None


class FeedbackStore:
    """SQLite-backed store for human corrections and feedback data."""

    def __init__(self, db_path: str = "hawsub_feedback.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS human_corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cue_id INTEGER,
                    source_text TEXT,
                    original_translation TEXT,
                    corrected_translation TEXT,
                    correction_type TEXT DEFAULT 'edit',
                    reviewer TEXT DEFAULT 'human_editor',
                    project_id TEXT,
                    scene_id TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def record_correction(self, correction: HumanCorrection) -> None:
        """Store a human correction to the feedback database."""
        if not correction.source_text or not correction.corrected_translation:
            return

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO human_corrections 
                   (cue_id, source_text, original_translation, corrected_translation, 
                    correction_type, reviewer, project_id, scene_id) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    correction.cue_id,
                    correction.source_text,
                    correction.original_translation,
                    correction.corrected_translation,
                    correction.correction_type,
                    correction.reviewer,
                    correction.project_id,
                    correction.scene_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_corrections(self, project_id: Optional[str] = None, limit: int = 100) -> List[HumanCorrection]:
        """Retrieve stored corrections, optionally filtered by project."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            if project_id:
                cursor.execute(
                    "SELECT cue_id, source_text, original_translation, corrected_translation, "
                    "correction_type, reviewer, project_id, scene_id, timestamp "
                    "FROM human_corrections WHERE project_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (project_id, limit),
                )
            else:
                cursor.execute(
                    "SELECT cue_id, source_text, original_translation, corrected_translation, "
                    "correction_type, reviewer, project_id, scene_id, timestamp "
                    "FROM human_corrections ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                )
            rows = cursor.fetchall()
        finally:
            conn.close()

        return [
            HumanCorrection(
                cue_id=r[0],
                source_text=r[1],
                original_translation=r[2],
                corrected_translation=r[3],
                correction_type=r[4],
                reviewer=r[5],
                project_id=r[6],
                scene_id=r[7],
                timestamp=r[8],
            )
            for r in rows
        ]

    def get_frequent_corrections(self, min_count: int = 3) -> List[Dict[str, Any]]:
        """Find source phrases that are frequently corrected — candidates for glossary."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT source_text, corrected_translation, COUNT(*) as freq
                   FROM human_corrections 
                   WHERE correction_type = 'edit'
                   GROUP BY source_text, corrected_translation
                   HAVING freq >= ?
                   ORDER BY freq DESC""",
                (min_count,),
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

        return [
            {"source_text": r[0], "corrected_translation": r[1], "frequency": r[2]}
            for r in rows
        ]

    def export_training_data(self, output_path: str, project_id: Optional[str] = None) -> int:
        """Export corrections as JSONL for fine-tuning.
        
        Each line: {"source": "...", "translation": "...", "context": "..."}
        Returns number of records exported.
        """
        corrections = self.get_corrections(project_id=project_id, limit=10000)

        count = 0
        with open(output_path, "w", encoding="utf-8") as f:
            for c in corrections:
                if c.correction_type == "edit" and c.corrected_translation != c.original_translation:
                    record = {
                        "source": c.source_text,
                        "original": c.original_translation,
                        "corrected": c.corrected_translation,
                        "project_id": c.project_id,
                        "scene_id": c.scene_id,
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    count += 1

        return count
