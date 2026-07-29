"""
Hawsub Cinematic Benchmark Suite & Evaluation Framework.
Evaluates LLM translation models against hand-curated gold standard English -> Sorani pairs.
Supports chrF scoring, per-category breakdowns, and severity-weighted scoring.
"""

import json
import os
import math
from typing import List, Dict, Any, Optional
from collections import defaultdict
from pydantic import BaseModel, Field
from hawsub.providers.base import SemanticModel
from hawsub.core.normalization.sorani import SoraniNormalizer


class GoldBenchmarkItem(BaseModel):
    id: int
    category: str = "general"
    source: str
    context: str
    intended_meaning: str
    gold_sorani: str
    acceptable_alternatives: List[str] = Field(default_factory=list)
    unacceptable_literal_examples: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class BenchmarkItemResult(BaseModel):
    item_id: int
    category: str = "general"
    source: str
    gold_sorani: str
    model_translation: str
    exact_gold_match: bool
    acceptable_match: bool
    unacceptable_literal_flag: bool
    chrf_score: float = 0.0
    item_score: float  # 0.0 to 1.0


class CategoryResult(BaseModel):
    category: str
    total_items: int
    passed_items: int
    literal_errors: int
    avg_score: float
    avg_chrf: float


class BenchmarkRunReport(BaseModel):
    provider_name: str
    model_name: str
    total_items: int
    passed_items: int
    literal_error_count: int
    overall_benchmark_score: float
    overall_chrf_score: float = 0.0
    category_results: List[CategoryResult] = Field(default_factory=list)
    results: List[BenchmarkItemResult]


# === chrF Implementation ===
# Character n-gram F-score (Popović, 2015) — better than BLEU for morphologically rich languages.

def _char_ngrams(text: str, n: int) -> Dict[str, int]:
    """Extract character n-grams with counts."""
    ngrams: Dict[str, int] = defaultdict(int)
    # Operate on whitespace-separated words to get within-word character n-grams
    for word in text.split():
        padded = f" {word} "
        for i in range(len(padded) - n + 1):
            ngrams[padded[i:i + n]] += 1
    return dict(ngrams)


def _word_ngrams(text: str, n: int) -> Dict[str, int]:
    """Extract word n-grams with counts."""
    words = text.split()
    ngrams: Dict[str, int] = defaultdict(int)
    for i in range(len(words) - n + 1):
        ngrams[" ".join(words[i:i + n])] += 1
    return dict(ngrams)


def compute_chrf(
    reference: str,
    hypothesis: str,
    max_char_order: int = 6,
    max_word_order: int = 0,
    beta: float = 2.0,
) -> float:
    """
    Compute chrF score between reference and hypothesis.
    
    Args:
        reference: Gold standard translation.
        hypothesis: Model translation.
        max_char_order: Maximum character n-gram order (default 6 for chrF).
        max_word_order: Maximum word n-gram order (0 = pure chrF, 2 = chrF++).
        beta: Recall weight (2.0 standard = recall twice as important as precision).
    
    Returns:
        chrF score between 0.0 and 1.0.
    """
    if not reference.strip() or not hypothesis.strip():
        return 0.0 if reference.strip() != hypothesis.strip() else 1.0

    total_precision = 0.0
    total_recall = 0.0
    count = 0

    # Character n-grams
    for n in range(1, max_char_order + 1):
        ref_ngrams = _char_ngrams(reference, n)
        hyp_ngrams = _char_ngrams(hypothesis, n)

        if not ref_ngrams or not hyp_ngrams:
            continue

        # Count matches
        matches = 0
        for ng, cnt in hyp_ngrams.items():
            matches += min(cnt, ref_ngrams.get(ng, 0))

        hyp_total = sum(hyp_ngrams.values())
        ref_total = sum(ref_ngrams.values())

        precision = matches / hyp_total if hyp_total > 0 else 0.0
        recall = matches / ref_total if ref_total > 0 else 0.0

        total_precision += precision
        total_recall += recall
        count += 1

    # Word n-grams (for chrF++)
    for n in range(1, max_word_order + 1):
        ref_ngrams = _word_ngrams(reference, n)
        hyp_ngrams = _word_ngrams(hypothesis, n)

        if not ref_ngrams or not hyp_ngrams:
            continue

        matches = 0
        for ng, cnt in hyp_ngrams.items():
            matches += min(cnt, ref_ngrams.get(ng, 0))

        hyp_total = sum(hyp_ngrams.values())
        ref_total = sum(ref_ngrams.values())

        precision = matches / hyp_total if hyp_total > 0 else 0.0
        recall = matches / ref_total if ref_total > 0 else 0.0

        total_precision += precision
        total_recall += recall
        count += 1

    if count == 0:
        return 0.0

    avg_precision = total_precision / count
    avg_recall = total_recall / count

    if avg_precision + avg_recall == 0:
        return 0.0

    # F-beta score
    beta_sq = beta ** 2
    chrf = (1 + beta_sq) * avg_precision * avg_recall / (beta_sq * avg_precision + avg_recall)
    return round(chrf, 4)


class BenchmarkSuite:
    """Runs evaluation benchmark against gold datasets."""

    def __init__(self, dataset_path: str = "tests/gold/gold_dataset.json"):
        self.dataset_path = dataset_path
        self.normalizer = SoraniNormalizer()
        self.items: List[GoldBenchmarkItem] = self._load_dataset()

    def _load_dataset(self) -> List[GoldBenchmarkItem]:
        if not os.path.exists(self.dataset_path):
            return []
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [GoldBenchmarkItem(**d) for d in data]

    def evaluate_model(self, model: SemanticModel) -> BenchmarkRunReport:
        results: List[BenchmarkItemResult] = []
        passed_count = 0
        literal_errors = 0
        total_score_sum = 0.0
        total_chrf_sum = 0.0

        # Category tracking
        cat_data: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"total": 0, "passed": 0, "literal": 0, "score_sum": 0.0, "chrf_sum": 0.0}
        )

        for item in self.items:
            # Simulate cue translation
            cues_data = [{"id": item.id, "source_text": item.source}]
            ctx_data = {"scene_summary": item.context}

            resp = model.translate_scene(
                scene_id=f"BM_{item.id:03d}",
                cues_data=cues_data,
                interpretations=None,
                context_data=ctx_data,
            )

            tr_text = resp.translations[0].translation if resp.translations else ""

            def clean_str(s: str) -> str:
                return self.normalizer.normalize(s).strip(".,!؟? ")

            tr_clean = clean_str(tr_text)
            gold_clean = clean_str(item.gold_sorani)

            exact_match = tr_clean == gold_clean

            acc_match = False
            for alt in item.acceptable_alternatives:
                if tr_clean == clean_str(alt):
                    acc_match = True
                    break

            literal_flag = False
            for bad_lit in item.unacceptable_literal_examples:
                if self.normalizer.normalize(bad_lit) in tr_clean:
                    literal_flag = True
                    break

            # Compute chrF score against gold
            chrf = compute_chrf(gold_clean, tr_clean)

            # Also check chrF against alternatives and take best
            for alt in item.acceptable_alternatives:
                alt_chrf = compute_chrf(clean_str(alt), tr_clean)
                if alt_chrf > chrf:
                    chrf = alt_chrf

            if literal_flag:
                literal_errors += 1
                score = 0.0
            elif exact_match:
                score = 1.0
                passed_count += 1
            elif acc_match:
                score = 0.90
                passed_count += 1
            else:
                # Partial match heuristic
                score = 0.50 if len(tr_clean) > 2 else 0.0

            total_score_sum += score
            total_chrf_sum += chrf

            # Update category tracking
            cat = item.category
            cat_data[cat]["total"] += 1
            cat_data[cat]["score_sum"] += score
            cat_data[cat]["chrf_sum"] += chrf
            if score >= 0.9:
                cat_data[cat]["passed"] += 1
            if literal_flag:
                cat_data[cat]["literal"] += 1

            results.append(
                BenchmarkItemResult(
                    item_id=item.id,
                    category=item.category,
                    source=item.source,
                    gold_sorani=item.gold_sorani,
                    model_translation=tr_clean,
                    exact_gold_match=exact_match,
                    acceptable_match=acc_match,
                    unacceptable_literal_flag=literal_flag,
                    chrf_score=chrf,
                    item_score=score,
                )
            )

        total = len(self.items)
        overall_score = round(total_score_sum / total, 3) if total > 0 else 0.0
        overall_chrf = round(total_chrf_sum / total, 3) if total > 0 else 0.0

        # Build category results
        category_results = []
        for cat_name, cd in sorted(cat_data.items()):
            t = cd["total"]
            category_results.append(
                CategoryResult(
                    category=cat_name,
                    total_items=t,
                    passed_items=cd["passed"],
                    literal_errors=cd["literal"],
                    avg_score=round(cd["score_sum"] / t, 3) if t > 0 else 0.0,
                    avg_chrf=round(cd["chrf_sum"] / t, 3) if t > 0 else 0.0,
                )
            )

        return BenchmarkRunReport(
            provider_name=model.provider_name,
            model_name=model.model_name,
            total_items=total,
            passed_items=passed_count,
            literal_error_count=literal_errors,
            overall_benchmark_score=overall_score,
            overall_chrf_score=overall_chrf,
            category_results=category_results,
            results=results,
        )
