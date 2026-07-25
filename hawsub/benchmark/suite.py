"""
Hawsub Cinematic Benchmark Suite & Evaluation Framework.
Evaluates LLM translation models against hand-curated gold standard English -> Sorani pairs.
"""

import json
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from hawsub.providers.base import SemanticModel
from hawsub.core.normalization.sorani import SoraniNormalizer


class GoldBenchmarkItem(BaseModel):
    id: int
    source: str
    context: str
    intended_meaning: str
    gold_sorani: str
    acceptable_alternatives: List[str] = Field(default_factory=list)
    unacceptable_literal_examples: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class BenchmarkItemResult(BaseModel):
    item_id: int
    source: str
    gold_sorani: str
    model_translation: str
    exact_gold_match: bool
    acceptable_match: bool
    unacceptable_literal_flag: bool
    item_score: float  # 0.0 to 1.0


class BenchmarkRunReport(BaseModel):
    provider_name: str
    model_name: str
    total_items: int
    passed_items: int
    literal_error_count: int
    overall_benchmark_score: float
    results: List[BenchmarkItemResult]


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

            exact_match = (tr_clean == gold_clean)
            
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

            results.append(
                BenchmarkItemResult(
                    item_id=item.id,
                    source=item.source,
                    gold_sorani=item.gold_sorani,
                    model_translation=tr_clean,
                    exact_gold_match=exact_match,
                    acceptable_match=acc_match,
                    unacceptable_literal_flag=literal_flag,
                    item_score=score,
                )
            )

        total = len(self.items)
        overall_score = round(total_score_sum / total, 3) if total > 0 else 0.0

        return BenchmarkRunReport(
            provider_name=model.provider_name,
            model_name=model.model_name,
            total_items=total,
            passed_items=passed_count,
            literal_error_count=literal_errors,
            overall_benchmark_score=overall_score,
            results=results,
        )
