import pytest
from hawsub.core.normalization.sorani import SoraniNormalizer


def test_sorani_character_normalization():
    normalizer = SoraniNormalizer()
    
    # Arabic kaf -> Kurdish kaf
    arabic_text = "كوردستان" # Arabic kaf
    normalized = normalizer.normalize(arabic_text)
    assert "ک" in normalized
    assert "ك" not in normalized

    # Arabic ya -> Kurdish ya
    arabic_ya = "مۆسیقايی" # Arabic ya
    normalized = normalizer.normalize(arabic_ya)
    assert "ی" in normalized
    assert "ي" not in normalized


def test_punctuation_normalization():
    normalizer = SoraniNormalizer()
    
    # English question mark convert to Sorani ؟
    text = "تۆ بەرەو کوێ دەچیت?"
    normalized = normalizer.normalize(text)
    assert normalized.endswith("؟")
    
    # Space before question mark should be stripped
    text_with_space = "سڵاو   ؟"
    normalized = normalizer.normalize(text_with_space)
    assert normalized == "سڵاو؟"


def test_kurmanji_contamination_detection():
    normalizer = SoraniNormalizer()
    
    clean_sorani = "سڵاو هاوڕێیان، چۆنن؟"
    assert len(normalizer.detect_kurmanji_contamination(clean_sorani)) == 0
    
    kurmanji_mixed = "Slav êdî çi dibêjî"
    contamination = normalizer.detect_kurmanji_contamination(kurmanji_mixed)
    assert "ê" in contamination or "î" in contamination


def test_untranslated_english_detection():
    normalizer = SoraniNormalizer()
    
    mixed_text = "ئەمە <i>movie</i> زۆر باشە Hello"
    english_words = normalizer.detect_untranslated_english(mixed_text)
    assert "Hello" in english_words
    assert "movie" in english_words
    assert "i" not in english_words # html tag filtered out
