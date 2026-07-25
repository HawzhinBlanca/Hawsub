"""
Narrative Context Engine: Bibles (Movie/Series/Season/Episode), Character Graphs, Glossaries, and Context Selectors.
"""

import hashlib
import json
from typing import List, Dict, Optional, Set
from pydantic import BaseModel, Field


class CharacterProfile(BaseModel):
    id: str
    name: str
    aliases: List[str] = Field(default_factory=list)
    target_name: str  # Sorani approved name
    speech_style: str = "standard"  # formal, casual, slang, archaic, military, etc.
    role: str = "supporting"
    relationship_notes: Optional[str] = None


class GlossaryEntryModel(BaseModel):
    id: str
    scope: str = "project"  # global | series | season | project
    source_term: str
    approved_target: str
    notes: Optional[str] = None
    case_sensitive: bool = False
    status: str = "approved"  # approved | draft


class ProjectBible(BaseModel):
    project_id: str
    title: str
    project_type: str = "movie"  # movie | episode
    synopsis: str = ""
    setting: str = ""
    period: str = ""
    characters: Dict[str, CharacterProfile] = Field(default_factory=dict)
    glossary: List[GlossaryEntryModel] = Field(default_factory=list)
    plot_summaries: Dict[str, str] = Field(default_factory=dict)

    def compute_context_hash(self) -> str:
        """Compute SHA-256 hash of the context state for request caching."""
        dumped = json.dumps(self.model_dump(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()

    def find_matching_glossary(self, text: str) -> List[GlossaryEntryModel]:
        """Find glossary terms present in the source text."""
        matches = []
        for entry in self.glossary:
            if entry.status != "approved":
                continue
            if entry.case_sensitive:
                if entry.source_term in text:
                    matches.append(entry)
            else:
                if entry.source_term.lower() in text.lower():
                    matches.append(entry)
        return matches

    def find_active_characters(self, text: str) -> List[CharacterProfile]:
        """Identify characters referenced or present in text."""
        active = []
        for char in self.characters.values():
            names_to_check = [char.name] + char.aliases
            for n in names_to_check:
                if n.lower() in text.lower():
                    active.append(char)
                    break
        return active


class ContextPackage(BaseModel):
    """Context bundle delivered alongside a cue batch to the LLM."""
    scene_id: str
    scene_summary: str = ""
    previous_scene_summary: Optional[str] = None
    next_scene_hint: Optional[str] = None
    active_characters: List[CharacterProfile] = Field(default_factory=list)
    relevant_glossary: List[GlossaryEntryModel] = Field(default_factory=list)
    context_hash: str = ""
