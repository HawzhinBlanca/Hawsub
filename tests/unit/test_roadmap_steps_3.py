"""
Tests for Steps 7-9 of the production hardening roadmap:
  Step 7: Feedback Loop (FeedbackStore)
  Step 8: Cost Controls (TokenBudget)
  Step 9: Error Recovery improvements
"""

import os
import json
import pytest
from hawsub.core.review.feedback import FeedbackStore, HumanCorrection
from hawsub.core.cost.budget import TokenBudget, CostEstimate


# ──────────────────────────────────────────────────────────────────────────────
# Step 7: Feedback Loop Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestFeedbackStore:

    def test_store_and_retrieve_correction(self, tmp_path):
        """Store a correction and retrieve it."""
        store = FeedbackStore(db_path=str(tmp_path / "test_feedback.db"))
        
        correction = HumanCorrection(
            cue_id=1,
            source_text="Hello my friend",
            original_translation="سڵاو هاوڕێم",
            corrected_translation="سڵاو برام",
            correction_type="edit",
            project_id="test_proj",
            scene_id="scene_001",
        )
        store.record_correction(correction)

        results = store.get_corrections(project_id="test_proj")
        assert len(results) == 1
        assert results[0].corrected_translation == "سڵاو برام"

    def test_empty_correction_not_stored(self, tmp_path):
        """Empty corrections are silently ignored."""
        store = FeedbackStore(db_path=str(tmp_path / "test_feedback.db"))
        
        correction = HumanCorrection(
            cue_id=1,
            source_text="",
            original_translation="",
            corrected_translation="",
        )
        store.record_correction(correction)

        results = store.get_corrections()
        assert len(results) == 0

    def test_multiple_corrections(self, tmp_path):
        """Store multiple corrections and retrieve all."""
        store = FeedbackStore(db_path=str(tmp_path / "test_feedback.db"))
        
        for i in range(5):
            store.record_correction(HumanCorrection(
                cue_id=i,
                source_text=f"Source text {i}",
                original_translation=f"Original {i}",
                corrected_translation=f"Corrected {i}",
                project_id="bulk_proj",
            ))

        results = store.get_corrections(project_id="bulk_proj")
        assert len(results) == 5

    def test_frequent_corrections(self, tmp_path):
        """Identify frequently corrected phrases."""
        store = FeedbackStore(db_path=str(tmp_path / "test_feedback.db"))
        
        # Insert the same correction pattern 4 times
        for i in range(4):
            store.record_correction(HumanCorrection(
                cue_id=i,
                source_text="Break a leg",
                original_translation="قاچت بشکێنە",
                corrected_translation="بەختی باشت هەبێت",
                correction_type="edit",
            ))

        frequent = store.get_frequent_corrections(min_count=3)
        assert len(frequent) >= 1
        assert frequent[0]["frequency"] >= 3
        assert frequent[0]["source_text"] == "Break a leg"

    def test_export_training_data(self, tmp_path):
        """Export corrections as JSONL for fine-tuning."""
        store = FeedbackStore(db_path=str(tmp_path / "test_feedback.db"))
        
        store.record_correction(HumanCorrection(
            cue_id=1,
            source_text="Break a leg",
            original_translation="قاچت بشکێنە",
            corrected_translation="بەختی باشت هەبێت",
            correction_type="edit",
        ))
        store.record_correction(HumanCorrection(
            cue_id=2,
            source_text="Accepted as is",
            original_translation="وەک خۆیەتی",
            corrected_translation="وەک خۆیەتی",
            correction_type="accept",  # Should not be exported (not an edit)
        ))

        export_path = str(tmp_path / "training.jsonl")
        count = store.export_training_data(export_path)

        assert count == 1  # Only the actual edit, not the accept

        with open(export_path, "r", encoding="utf-8") as f:
            line = f.readline()
            record = json.loads(line)
        assert record["source"] == "Break a leg"
        assert record["corrected"] == "بەختی باشت هەبێت"


# ──────────────────────────────────────────────────────────────────────────────
# Step 8: Cost Controls Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestTokenBudget:

    def test_initial_state(self):
        """Budget starts at zero cost and full remaining."""
        budget = TokenBudget(max_cost_usd=5.0, model_name="gemini-2.5-flash")
        assert budget.total_cost_usd == 0.0
        assert budget.remaining_budget_usd == 5.0
        assert budget.api_calls == 0

    def test_record_usage(self):
        """Recording usage updates total cost and call count."""
        budget = TokenBudget(max_cost_usd=10.0, model_name="gemini-2.5-flash")
        budget.record_usage(input_tokens=1000, output_tokens=500)
        
        assert budget.api_calls == 1
        assert budget.total_cost_usd > 0.0
        assert budget.remaining_budget_usd < 10.0

    def test_check_budget_within_limits(self):
        """Budget check returns True when within limits."""
        budget = TokenBudget(max_cost_usd=10.0)
        assert budget.check_budget(estimated_cost=1.0) is True

    def test_check_budget_over_limit(self):
        """Budget check returns False when over limit."""
        budget = TokenBudget(max_cost_usd=0.01)
        assert budget.check_budget(estimated_cost=1.0) is False

    def test_estimate_scene_cost(self):
        """Scene cost estimation returns a positive number."""
        budget = TokenBudget(model_name="gpt-4o")
        cues_data = [{"source_text": f"Dialogue line {i}" * 3} for i in range(10)]
        cost = budget.estimate_scene_cost(cues_data, system_prompt_len=3000)
        assert cost > 0.0
        assert cost < 1.0  # 10 cues should be cents, not dollars

    def test_estimate_full_file(self):
        """Full file cost estimation returns valid estimate."""
        budget = TokenBudget(model_name="gemini-2.5-flash")
        estimate = budget.estimate_full_file(total_cues=500, avg_source_length=45)
        
        assert isinstance(estimate, CostEstimate)
        assert estimate.total_cues == 500
        assert estimate.estimated_cost_usd > 0.0
        assert estimate.estimated_input_tokens > 0
        assert estimate.estimated_output_tokens > 0

    def test_get_summary(self):
        """Usage summary contains all expected fields."""
        budget = TokenBudget(max_cost_usd=5.0, model_name="gemini-2.5-flash")
        budget.record_usage(input_tokens=500, output_tokens=200)
        
        summary = budget.get_summary()
        assert "model" in summary
        assert "api_calls" in summary
        assert "total_cost_usd" in summary
        assert "remaining_usd" in summary
        assert summary["api_calls"] == 1

    def test_multiple_models_have_different_costs(self):
        """Different models produce different cost estimates."""
        budget_cheap = TokenBudget(model_name="gemini-2.5-flash")
        budget_expensive = TokenBudget(model_name="gpt-4o")

        cues = [{"source_text": "Hello there my friend"}] * 20
        cost_cheap = budget_cheap.estimate_scene_cost(cues)
        cost_expensive = budget_expensive.estimate_scene_cost(cues)

        assert cost_expensive > cost_cheap  # GPT-4o is more expensive
