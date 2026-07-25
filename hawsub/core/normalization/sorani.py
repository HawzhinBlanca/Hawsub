"""
Sorani (Central Kurdish, ckb) Orthographic Normalization Engine & Style Guide Enforcement.
"""

import re
from typing import Dict, List, Tuple, Optional


class SoraniNormalizer:
    # Character Mappings
    KAF_ARABIC = "\u0643"      # ك
    KAF_KURDISH = "\u06A9"     # ک
    
    YA_ARABIC = "\u064A"       # ي
    YA_ALEF_MAQSURA = "\u0649" # ى
    YA_KURDISH = "\u06CC"      # ی
    
    AE_KURDISH = "\u06D5"      # ە
    HA_ARABIC = "\u0647"       # ه
    
    TATWEEL = "\u0640"         # ـ

    # Punctuation
    COMMA_ARABIC = "\u060C"    # ،
    SEMICOLON_ARABIC = "\u061B" # ؛
    QUESTION_ARABIC = "\u061F"  # ؟

    # Kurmanji Latin / Specific Character Set
    KURMANJI_SPECIFIC_CHARS = set("êîûşçÊÎÛŞÇ")

    def __init__(
        self,
        normalize_characters: bool = True,
        normalize_punctuation: bool = True,
        convert_arabic_digits: bool = False,
        add_rtl_marks: bool = False,
    ):
        self.normalize_characters = normalize_characters
        self.normalize_punctuation = normalize_punctuation
        self.convert_arabic_digits = convert_arabic_digits
        self.add_rtl_marks = add_rtl_marks

    def normalize(self, text: str) -> str:
        """Fully normalize Sorani Kurdish text."""
        if not text:
            return ""

        result = text

        if self.normalize_characters:
            result = self.normalize_unicode_chars(result)

        if self.normalize_punctuation:
            result = self.normalize_punctuation_marks(result)

        if self.convert_arabic_digits:
            result = self.normalize_digits(result)

        if self.add_rtl_marks:
            result = self.apply_rtl_safety(result)

        return result

    def normalize_unicode_chars(self, text: str) -> str:
        """Replace non-Kurdish Arabic letter variants with standard Central Kurdish code points."""
        text = text.replace(self.KAF_ARABIC, self.KAF_KURDISH)
        text = text.replace(self.YA_ARABIC, self.YA_KURDISH)
        text = text.replace(self.YA_ALEF_MAQSURA, self.YA_KURDISH)
        # Remove tatweel
        text = text.replace(self.TATWEEL, "")
        
        # Normalize double spaces
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    def normalize_punctuation_marks(self, text: str) -> str:
        """Ensure Sorani punctuation marks are correctly formatted."""
        # Replace Western comma/semicolon/question mark if adjacent to Kurdish text
        # Convert English ? to Sorani ؟ if text contains Arabic/Kurdish script
        if re.search(r"[\u0600-\u06FF]", text):
            text = text.replace("?", self.QUESTION_ARABIC)
            text = text.replace(",", self.COMMA_ARABIC)
            text = text.replace(";", self.SEMICOLON_ARABIC)

        # Normalize multiple question marks / exclamation marks
        text = re.sub(r"؟{2,}", "؟", text)
        text = re.sub(r"\!{2,}", "!", text)

        # Normalize ellipses
        text = re.sub(r"…", "...", text)
        text = re.sub(r"\.{4,}", "...", text)

        # Spacing around Kurdish punctuation: no space before ، ؟ ؛ , space after
        text = re.sub(r"\s+([،؛؟])", r"\1", text)
        text = re.sub(r"([،؛؟])(?=[^\s،؛؟\)])", r"\1 ", text)

        return text

    def normalize_digits(self, text: str) -> str:
        """Convert Eastern Arabic digits to standard ASCII or vice-versa."""
        arabic_digits = "٠١٢٣٤٥٦٧٨٩"
        persian_digits = "۰۱۲۳۴۵۶۷۸۹"
        ascii_digits = "0123456789"
        
        tr_map = str.maketrans(arabic_digits + persian_digits, ascii_digits * 2)
        return text.translate(tr_map)

    def apply_rtl_safety(self, text: str) -> str:
        """
        Wrap text or append Right-To-Left Mark (RLM \\u200f) to prevent line-end punctuation
        flipping in LTR sub rendering engines.
        """
        rlm = "\u200F"
        if text and not text.startswith(rlm):
            text = rlm + text
        if text and not text.endswith(rlm):
            text = text + rlm
        return text

    def detect_kurmanji_contamination(self, text: str) -> List[str]:
        """Detect Kurmanji Latin script characters or forbidden dialect markers."""
        found = []
        for char in text:
            if char in self.KURMANJI_SPECIFIC_CHARS:
                found.append(char)
        return list(set(found))

    def detect_untranslated_english(self, text: str) -> List[str]:
        """Find English words embedded in target subtitle text."""
        # Exclude common tags or special codes
        words = re.findall(r"\b[A-Za-z]{2,}\b", text)
        # Filter out HTML tags like <i>, <b>, <u>, font, etc.
        html_tags = {"i", "b", "u", "font", "color", "size"}
        return [w for w in words if w.lower() not in html_tags]
