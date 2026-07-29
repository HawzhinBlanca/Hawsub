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

    # Kurmanji specific Arabic script vocabulary markers
    KURMANJI_ARABIC_MARKERS = {
        "دکەت", "دکەن", "دبێت", "دبن", "ئەز", "تە", "وە", "وان", "هاتیە", "چوویە"
    }

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
        self._cache: Dict[str, str] = {}

    def normalize(self, text: str) -> str:
        """Fully normalize Sorani Kurdish text with internal memoization for performance."""
        if not text:
            return ""

        if text in self._cache:
            return self._cache[text]

        result = text

        if self.normalize_characters:
            result = self.normalize_unicode_chars(result)

        if self.normalize_punctuation:
            result = self.normalize_punctuation_marks(result)

        if self.convert_arabic_digits:
            result = self.normalize_digits(result)

        if self.add_rtl_marks:
            result = self.apply_rtl_safety(result)

        # Cache up to 2000 entries
        if len(self._cache) < 2000:
            self._cache[text] = result

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

        # Check Arabic script Kurmanji markers
        words = re.findall(r"[\u0600-\u06FF]+", text)
        for w in words:
            if w in self.KURMANJI_ARABIC_MARKERS:
                found.append(w)

        return list(set(found))

    def detect_untranslated_english(self, text: str) -> List[str]:
        """Find English words embedded in target subtitle text."""
        # Allowlisted abbreviations and common subtitle markers
        ALLOWED_WORDS = {
            # HTML tags
            "i", "b", "u", "font", "color", "size", "br", "div", "span",
            # Common subtitle abbreviations
            "ok", "tv", "dvd", "dna", "fbi", "cia", "ngo", "usa",
            "sms", "gps", "atm", "vip", "dj", "cd", "pc", "wi", "fi",
            # Units and common proper nouns that should not be translated
            "km", "kg", "mg", "mm", "cm", "ml",
            # Common borrowed words used internationally
            "taxi", "internet", "video", "radio", "facebook", "google",
            "email", "telegram", "whatsapp", "youtube",
        }
        # Find words of 2+ characters
        words = re.findall(r"\b[A-Za-z]{2,}\b", text)
        return [w for w in words if w.lower() not in ALLOWED_WORDS]

    def detect_excessive_ezafe_chains(self, text: str) -> List[str]:
        """Detect suspiciously long chains of ezafe particle ی between words.
        
        In Sorani, ezafe (ی) connects nouns/adjectives. More than 3 consecutive
        ezafe-linked words often indicates malformed or machine-generated text.
        """
        issues = []
        # Find sequences of Arabic-script words connected by ی
        # Pattern: word + ی + word + ی + word + ی + word (4+ chain)
        # Match words (Arabic script clusters) separated by ی with optional space
        words = re.findall(r'[\u0600-\u06FF]+', text)
        
        chain_len = 0
        for i, word in enumerate(words):
            if word.endswith('ی') or word == 'ی':
                chain_len += 1
            else:
                if chain_len >= 4:
                    chain_start = max(0, i - chain_len - 1)
                    chain_words = words[chain_start:i+1]
                    issues.append(f"Excessive ezafe chain ({chain_len}+): {'‌'.join(chain_words)}")
                chain_len = 0
        
        # Check final chain
        if chain_len >= 4:
            issues.append(f"Excessive ezafe chain ({chain_len}+) at end of text")
        
        return issues

    def detect_common_llm_errors(self, text: str) -> List[str]:
        """Detect common patterns that LLMs produce incorrectly in Sorani.
        
        These are patterns observed from real LLM translation failures.
        """
        issues = []
        
        # 1. Mixed script detection (Arabic + Sorani characters in same word)
        # ك (Arabic kaf) mixed with ی (Kurdish yeh) in same word
        mixed_words = re.findall(r'[\u0600-\u06FF]+', text)
        for word in mixed_words:
            has_arabic_kaf = '\u0643' in word  # ك
            has_kurdish_yeh = '\u06CC' in word  # ی
            has_arabic_yeh = '\u064A' in word   # ي
            if has_arabic_kaf and has_kurdish_yeh:
                issues.append(f"Mixed script in word '{word}': Arabic kaf with Kurdish yeh")
            if has_arabic_yeh:
                issues.append(f"Arabic yeh (ي) found in word '{word}', should be Kurdish yeh (ی)")
        
        # 2. Repeated words (LLM stuttering)
        word_list = text.split()
        for i in range(len(word_list) - 2):
            if word_list[i] == word_list[i+1] == word_list[i+2] and len(word_list[i]) > 1:
                issues.append(f"Triple word repetition: '{word_list[i]}' × 3")
        
        # 3. Bracket/parenthesis pollution (LLM adding explanatory notes)
        if re.search(r'\([^)]*[A-Za-z]{3,}[^)]*\)', text):
            issues.append("English explanation in parentheses — LLM note pollution")
        
        # 4. Asterisk/markdown formatting leaked from LLM
        if '**' in text or '__' in text:
            issues.append("Markdown formatting leaked into subtitle text")
        
        # 5. Numbered list format (LLMs sometimes format as lists)
        if re.match(r'^\d+[\.\)]\s', text):
            issues.append("Numbered list format detected — not subtitle style")
        
        return issues

    def validate_sorani_text(self, text: str) -> Dict[str, List[str]]:
        """Run all Sorani linguistic validations and return categorized issues.
        
        Returns a dict with keys: 'kurmanji', 'untranslated', 'ezafe', 'llm_errors'
        """
        return {
            "kurmanji": self.detect_kurmanji_contamination(text),
            "untranslated": self.detect_untranslated_english(text),
            "ezafe": self.detect_excessive_ezafe_chains(text),
            "llm_errors": self.detect_common_llm_errors(text),
        }

