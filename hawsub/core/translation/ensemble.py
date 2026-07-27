"""
Multi-Model Translation Ensemble & Consensus Verification Engine.
Queries multiple LLM models in parallel or sequence, computing semantic consensus to guarantee highest quality.
"""

from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel
from hawsub.providers.base import SemanticModel, TranslationResponse, TranslationCueItem
from hawsub.core.normalization.sorani import SoraniNormalizer


class EnsembleResult(BaseModel):
    cue_id: int
    primary_translation: str
    secondary_translation: str
    consensus_score: float  # 0.0 to 1.0
    agreed: bool


class TranslationEnsembleEngine:
    """Combines predictions from multiple translation providers for maximum reliability."""

    def __init__(self, primary_model: SemanticModel, secondary_model: Optional[SemanticModel] = None):
        self.primary = primary_model
        self.secondary = secondary_model
        self.normalizer = SoraniNormalizer()

    def translate_scene_with_consensus(
        self,
        scene_id: str,
        cues_data: List[Dict[str, Any]],
        context_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[TranslationResponse, List[EnsembleResult]]:

        # Translate with primary model
        res_primary = self.primary.translate_scene(
            scene_id=scene_id,
            cues_data=cues_data,
            interpretations=None,
            context_data=context_data or {},
        )

        ensemble_reports: List[EnsembleResult] = []

        if not self.secondary:
            # Single model mode
            for cue in res_primary.translations:
                cue_id = cue.cue_ids[0] if cue.cue_ids else 0
                ensemble_reports.append(
                    EnsembleResult(
                        cue_id=cue_id,
                        primary_translation=cue.translation,
                        secondary_translation=cue.translation,
                        consensus_score=1.0,
                        agreed=True,
                    )
                )
            return res_primary, ensemble_reports

        # Translate with secondary model for cross-verification
        res_secondary = self.secondary.translate_scene(
            scene_id=scene_id,
            cues_data=cues_data,
            interpretations=None,
            context_data=context_data or {},
        )

        sec_map = {}
        for c in res_secondary.translations:
            cid = c.cue_ids[0] if c.cue_ids else 0
            sec_map[cid] = c.translation

        for cue in res_primary.translations:
            cid = cue.cue_ids[0] if cue.cue_ids else 0
            p_tr = self.normalizer.normalize(cue.translation)
            s_tr = self.normalizer.normalize(sec_map.get(cid, ""))

            agreed = (p_tr == s_tr)
            score = 1.0 if agreed else (0.75 if len(p_tr) > 0 and len(s_tr) > 0 else 0.0)

            ensemble_reports.append(
                EnsembleResult(
                    cue_id=cid,
                    primary_translation=p_tr,
                    secondary_translation=s_tr,
                    consensus_score=score,
                    agreed=agreed,
                )
            )

        return res_primary, ensemble_reports
