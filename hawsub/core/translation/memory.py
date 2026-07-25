"""
Translation Memory (TM) Engine for Hawsub.
Stores approved human translations and performs fuzzy matching to ensure terminology & style consistency.
"""

import sqlite3
import difflib
from pathlib import Path
from typing import List, Optional, Tuple
from pydantic import BaseModel


class TMEntry(BaseModel):
    id: Optional[int] = None
    source_text: str
    target_text: str
    context_notes: Optional[str] = None
    similarity_score: float = 1.0


class TranslationMemory:
    """SQLite-backed Translation Memory with fuzzy matching."""

    def __init__(self, db_path: str = "hawsub_tm.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS translation_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_text TEXT UNIQUE,
                    target_text TEXT,
                    context_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

    def store_translation(self, source_text: str, target_text: str, context_notes: Optional[str] = None) -> None:
        if not source_text or not target_text:
            return
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO translation_memory (source_text, target_text, context_notes) VALUES (?, ?, ?)",
                (source_text.strip(), target_text.strip(), context_notes),
            )
            conn.commit()

    def find_fuzzy_match(self, source_text: str, threshold: float = 0.85) -> Optional[TMEntry]:
        if not source_text:
            return None
        
        source_clean = source_text.strip().lower()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, source_text, target_text, context_notes FROM translation_memory")
            rows = cursor.fetchall()

        best_entry = None
        best_ratio = 0.0

        for row_id, src, trg, notes in rows:
            matcher = difflib.SequenceMatcher(None, source_clean, src.lower())
            ratio = matcher.ratio()
            if ratio >= threshold and ratio > best_ratio:
                best_ratio = ratio
                best_entry = TMEntry(
                    id=row_id,
                    source_text=src,
                    target_text=trg,
                    context_notes=notes,
                    similarity_score=round(ratio, 3),
                )

        return best_entry
