import pytest
from hawsub.core.semantic.interpreter import SemanticInterpreter
from hawsub.core.translation.memory import TranslationMemory, TMEntry
from hawsub.providers.mock import MockSemanticModel
from hawsub.core.ingest.parser import SubtitleCueModel
from hawsub.core.context.bible import ContextPackage


def test_semantic_interpreter():
    model = MockSemanticModel()
    interpreter = SemanticInterpreter(model)
    
    cues = [SubtitleCueModel(id=1, start_ms=1000, end_ms=3000, source_text="You're pushing your luck.")]
    ctx = ContextPackage(scene_id="S001")
    
    res = interpreter.analyze_batch("S001", cues, ctx)
    assert res.scene_id == "S001"
    assert len(res.items) == 1
    assert res.items[0].cue_ids == [1]


def test_translation_memory(tmp_path):
    db_file = str(tmp_path / "test_tm.db")
    tm = TranslationMemory(db_path=db_file)
    
    tm.store_translation("You're pushing your luck.", "تۆ زێدەڕۆیی لە بەختت دەکەیت.")
    
    # Exact match
    match = tm.find_fuzzy_match("You're pushing your luck.")
    assert match is not None
    assert match.target_text == "تۆ زێدەڕۆیی لە بەختت دەکەیت."

    # Fuzzy match
    fuzzy = tm.find_fuzzy_match("You are pushing your luck")
    assert fuzzy is not None
    assert fuzzy.similarity_score >= 0.85
