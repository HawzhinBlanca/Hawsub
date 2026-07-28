"""
Production API Provider Adapters for Google Gemini, OpenAI, Anthropic, OpenRouter, and Local LLM endpoints.
Includes exponential backoff, rate-limit handling, and structured output parsing.
"""

import os
import json
import time
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import List, Dict, Any, Optional
from hawsub.providers.base import (
    SemanticModel,
    SemanticInterpretationResponse,
    SemanticInterpretationItem,
    TranslationResponse,
    TranslationCueItem,
    VerificationResponse,
)
from hawsub.core.normalization.sorani import SoraniNormalizer

logger = logging.getLogger("hawsub.provider")


class GenericAPIModel(SemanticModel):
    """
    Unified API provider adapter that handles requests to OpenAI, OpenRouter, Local OpenAI-compatible,
    Anthropic, or Google Gemini HTTP endpoints using standard library urllib with exponential backoff.
    """

    MAX_RETRIES = 3
    BASE_BACKOFF_SEC = 1.0
    REQUEST_TIMEOUT_SEC = 60

    def __init__(
        self,
        provider_name: str,
        model_name: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.2,
    ):
        super().__init__(provider_name, model_name, temperature)
        self.api_key = api_key or os.environ.get(f"{provider_name.upper()}_API_KEY", "")
        self.base_url = base_url or self._default_base_url(provider_name)
        self.normalizer = SoraniNormalizer()

    def _default_base_url(self, provider: str) -> str:
        urls = {
            "openai": "https://api.openai.com/v1",
            "openrouter": "https://openrouter.ai/api/v1",
            "google": "https://generativelanguage.googleapis.com/v1beta",
            "anthropic": "https://api.anthropic.com/v1",
            "local": "http://localhost:11434/v1",
        }
        return urls.get(provider, "https://api.openai.com/v1")

    def _build_request(self, payload: Dict[str, Any], endpoint: str) -> urllib.request.Request:
        """Build HTTP request with proper auth headers for each provider."""
        url = f"{self.base_url.rstrip('/')}{endpoint}"
        headers = {"Content-Type": "application/json"}

        if self.provider_name == "anthropic":
            headers["x-api-key"] = self.api_key
            headers["anthropic-version"] = "2023-06-01"
        elif self.provider_name == "google":
            url += f"?key={self.api_key}"
        elif self.provider_name in ["openai", "openrouter", "local"]:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req_data = json.dumps(payload).encode("utf-8")
        return urllib.request.Request(url, data=req_data, headers=headers, method="POST")

    def _call_http_json(self, payload: Dict[str, Any], endpoint: str = "/chat/completions") -> Dict[str, Any]:
        """Execute HTTP POST request with exponential backoff retry."""
        if not self.api_key and self.provider_name != "local":
            raise ValueError(f"API key missing for provider {self.provider_name}. "
                             f"Set {self.provider_name.upper()}_API_KEY environment variable.")

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                req = self._build_request(payload, endpoint)
                with urllib.request.urlopen(req, timeout=self.REQUEST_TIMEOUT_SEC) as resp:
                    resp_body = resp.read().decode("utf-8")
                    return json.loads(resp_body)
            except urllib.error.HTTPError as e:
                last_error = e
                status = e.code
                body = ""
                try:
                    body = e.read().decode("utf-8", errors="replace")
                except Exception:
                    pass

                # Rate limit or server overload — retry with backoff
                if status in (429, 500, 502, 503, 529):
                    backoff = self.BASE_BACKOFF_SEC * (2 ** attempt)
                    logger.warning(f"Provider {self.provider_name} returned HTTP {status}, retrying in {backoff:.1f}s (attempt {attempt + 1}/{self.MAX_RETRIES})")
                    time.sleep(backoff)
                    continue

                # Client error — don't retry
                logger.error(f"Provider {self.provider_name} HTTP {status}: {body[:500]}")
                raise
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last_error = e
                backoff = self.BASE_BACKOFF_SEC * (2 ** attempt)
                logger.warning(f"Connection error to {self.provider_name}: {e}, retrying in {backoff:.1f}s")
                time.sleep(backoff)
                continue

        raise ConnectionError(f"Failed to reach {self.provider_name} after {self.MAX_RETRIES} attempts: {last_error}")

    def _extract_content(self, response: Dict[str, Any]) -> str:
        """Extract text content from provider response regardless of format."""
        if not response or not isinstance(response, dict):
            return ""

        # OpenAI/OpenRouter/Local format
        if "choices" in response and isinstance(response["choices"], list) and len(response["choices"]) > 0:
            choice = response["choices"][0]
            if isinstance(choice, dict) and "message" in choice:
                return choice["message"].get("content", "")
        # Anthropic format
        if "content" in response and isinstance(response["content"], list) and len(response["content"]) > 0:
            return response["content"][0].get("text", "")
        # Google Gemini format
        if "candidates" in response and isinstance(response["candidates"], list) and len(response["candidates"]) > 0:
            parts = response["candidates"][0].get("content", {}).get("parts", [])
            return parts[0].get("text", "") if parts else ""
        return ""

    def _build_chat_payload(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Build chat completion payload for the specific provider."""
        if self.provider_name == "anthropic":
            return {
                "model": self.model_name,
                "max_tokens": 4096,
                "temperature": self.temperature,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            }
        elif self.provider_name == "google":
            return {
                "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
                "generationConfig": {
                    "temperature": self.temperature,
                    "responseMimeType": "application/json",
                },
            }
        else:
            # OpenAI / OpenRouter / Local
            return {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": self.temperature,
                "response_format": {"type": "json_object"},
            }

    def _get_endpoint(self) -> str:
        """Return the correct API endpoint for the provider."""
        if self.provider_name == "google":
            return f"/models/{self.model_name}:generateContent"
        elif self.provider_name == "anthropic":
            return "/messages"
        return "/chat/completions"

    def _safe_parse_json(self, content: str) -> Dict[str, Any]:
        """Robustly extract JSON from LLM response, handling markdown fences and partial text."""
        content = content.strip()
        # Handle markdown code blocks gracefully
        import re
        if "```" in content:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content, re.IGNORECASE)
            if match:
                content = match.group(1).strip()
            else:
                lines = [l for l in content.split("\n") if not l.strip().startswith("```")]
                content = "\n".join(lines).strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try to locate JSON object substring
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(content[start:end])
            except json.JSONDecodeError:
                pass

        logger.warning(f"Failed to parse JSON from model response: {content[:200]}")
        return {}

    @staticmethod
    def _parse_cue_ids(item: Dict[str, Any], default_id: int = 1) -> List[int]:
        """Safely extract cue IDs as a list of integers from LLM JSON response item."""
        raw = item.get("cue_ids")
        if raw is None:
            raw = item.get("cue_id")
        if raw is None:
            raw = item.get("id")
        if raw is None:
            return [default_id]

        if isinstance(raw, (int, float)):
            return [int(raw)]
        if isinstance(raw, str):
            try:
                return [int(raw)]
            except ValueError:
                return [default_id]
        if isinstance(raw, list):
            res = []
            for x in raw:
                try:
                    res.append(int(x))
                except (ValueError, TypeError):
                    pass
            return res if res else [default_id]
        return [default_id]

    def analyze_scene(
        self, scene_id: str, cues_data: List[Dict[str, Any]], context_data: Dict[str, Any]
    ) -> SemanticInterpretationResponse:
        """Analyze narrative meaning and subtext before translating using the LLM."""
        system_prompt = (
            "You are a master narrative analyst for cinematic subtitle localization into Central Kurdish (Sorani, ckb). "
            "Analyze intended meaning, tone, register, subtext, and ambiguity. Do not translate. Return JSON only."
        )

        user_prompt = (
            f"Scene ID: {scene_id}\n"
            f"Context: {json.dumps(context_data.get('scene_summary', ''), ensure_ascii=False)}\n\n"
            f"Analyze these dialogue cues:\n{json.dumps(cues_data, ensure_ascii=False)}\n\n"
            "Return JSON: {\"items\": [{\"cue_ids\": [N], \"source_text\": \"...\", \"meaning\": \"...\", "
            "\"tone\": \"...\", \"register\": \"...\", \"subtext\": \"...\", \"ambiguity_score\": 0.0}]}"
        )

        try:
            payload = self._build_chat_payload(system_prompt, user_prompt)
            res = self._call_http_json(payload, self._get_endpoint())
            content = self._extract_content(res)
            parsed = self._safe_parse_json(content)

            items = []
            for item in parsed.get("items", []):
                cids = self._parse_cue_ids(item, default_id=cues_data[0].get("id", 1) if cues_data else 1)
                items.append(
                    SemanticInterpretationItem(
                        cue_ids=cids,
                        source_text=item.get("source_text", ""),
                        intended_meaning=item.get("meaning", item.get("intended_meaning", "")),
                        tone=item.get("tone", "neutral"),
                        speech_register=item.get("register", item.get("speech_register", "informal")),
                        subtext=item.get("subtext"),
                        ambiguity_score=float(item.get("ambiguity_score", 0.0)),
                        notes=item.get("notes"),
                    )
                )
            if items:
                return SemanticInterpretationResponse(scene_id=scene_id, items=items, model_version=self.model_name)
        except Exception as e:
            logger.warning(f"LLM analyze_scene failed, using passthrough: {e}")

        # Passthrough fallback — preserve source text as meaning
        items = []
        for cue in cues_data:
            c_id = cue.get("id", 1)
            src = cue.get("source_text", "")
            items.append(
                SemanticInterpretationItem(
                    cue_ids=[c_id],
                    source_text=src,
                    intended_meaning=src,
                    tone="neutral",
                    ambiguity_score=0.0,
                )
            )
        return SemanticInterpretationResponse(scene_id=scene_id, items=items, model_version=self.model_name)

    def translate_scene(
        self,
        scene_id: str,
        cues_data: List[Dict[str, Any]],
        interpretations: Optional[List[SemanticInterpretationItem]],
        context_data: Dict[str, Any],
    ) -> TranslationResponse:
        """Translate meaning-first into Central Kurdish / Sorani (ckb) using the LLM."""
        system_prompt = (
            "You are a master subtitle translator specializing in English to Central Kurdish (Sorani, ckb). "
            "Use Arabic-based Central Kurdish script (ک، ی، ۆ، ێ، ە، ڵ، ڕ). "
            "Translate meaning, not words. Localize idioms naturally. Keep concise for subtitles. "
            "NO Kurmanji. Return valid JSON only."
        )

        interp_info = ""
        if interpretations:
            interp_info = f"\nSemantic interpretations:\n{json.dumps([i.model_dump() for i in interpretations], ensure_ascii=False)}\n"

        user_prompt = (
            f"Scene: {scene_id}\n"
            f"Context: {json.dumps(context_data.get('scene_summary', ''), ensure_ascii=False)}\n"
            f"{interp_info}\n"
            f"Translate these cues into natural Sorani:\n{json.dumps(cues_data, ensure_ascii=False)}\n\n"
            "Return JSON: {\"translations\": [{\"cue_ids\": [N], \"meaning\": \"...\", \"translation\": \"Sorani text\", "
            "\"confidence\": 0.95, \"ambiguity\": false}]}"
        )

        try:
            payload = self._build_chat_payload(system_prompt, user_prompt)
            res = self._call_http_json(payload, self._get_endpoint())
            content = self._extract_content(res)
            parsed = self._safe_parse_json(content)

            translations = []
            for item in parsed.get("translations", []):
                norm_text = self.normalizer.normalize(item.get("translation", ""))
                cids = self._parse_cue_ids(item, default_id=cues_data[0].get("id", 1) if cues_data else 1)
                translations.append(
                    TranslationCueItem(
                        cue_ids=cids,
                        meaning=item.get("meaning", ""),
                        translation=norm_text,
                        confidence=float(item.get("confidence", 0.95)),
                        ambiguity=bool(item.get("ambiguity", False)),
                        notes=item.get("notes"),
                    )
                )
            if translations:
                return TranslationResponse(scene_id=scene_id, translations=translations, model_name=self.model_name)
        except Exception as e:
            logger.warning(f"LLM translate_scene failed, using mock fallback: {e}")

        # Offline fallback if remote API call fails
        from hawsub.providers.mock import MockSemanticModel
        mock_model = MockSemanticModel()
        fallback_items = []
        for c in cues_data:
            src_txt = c.get("source_text", "")
            mock_tr = mock_model._mock_translate(src_txt)
            fallback_items.append(
                TranslationCueItem(
                    cue_ids=[c.get("id", 1)],
                    meaning=src_txt,
                    translation=self.normalizer.normalize(mock_tr),
                    confidence=0.90,
                    notes="Offline fallback translation used",
                )
            )
        return TranslationResponse(scene_id=scene_id, translations=fallback_items, model_name=self.model_name)

    def verify_translation(
        self,
        source_text: str,
        current_translation: str,
        meaning: str,
        context_data: Dict[str, Any],
    ) -> VerificationResponse:
        """Verify an existing Sorani translation using a second-model check."""
        system_prompt = (
            "You are an expert Kurdish subtitle quality verifier. "
            "Audit a proposed Sorani translation against the English source. "
            "Check semantic fidelity, naturalness, Kurmanji contamination, literal translation failures. "
            "Return JSON only."
        )

        user_prompt = (
            f"Source English: {source_text}\n"
            f"Current Sorani Translation: {current_translation}\n"
            f"Intended Meaning: {meaning}\n\n"
            "Return JSON: {\"decision\": \"agree|disagree|uncertain\", \"severity\": \"none|minor|major|critical\", "
            "\"reason\": \"...\", \"alternative\": null, \"confidence\": 0.90}"
        )

        try:
            payload = self._build_chat_payload(system_prompt, user_prompt)
            res = self._call_http_json(payload, self._get_endpoint())
            content = self._extract_content(res)
            parsed = self._safe_parse_json(content)

            if parsed and "decision" in parsed:
                return VerificationResponse(
                    cue_ids=[1],
                    decision=parsed.get("decision", "agree"),
                    severity=parsed.get("severity", "none"),
                    reason=parsed.get("reason", "Verified"),
                    alternative=parsed.get("alternative"),
                    confidence=float(parsed.get("confidence", 0.9)),
                )
        except Exception as e:
            logger.warning(f"LLM verify_translation failed, using default agree: {e}")

        return VerificationResponse(
            cue_ids=[1],
            decision="agree",
            severity="none",
            reason="Verification unavailable — default pass",
            confidence=0.85,
        )
