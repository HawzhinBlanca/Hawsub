from typing import Dict, Optional, Any
from pydantic import BaseModel, Field


class ProjectConfig(BaseModel):
    target_language: str = Field(default="ckb", description="Target language code")
    mode: str = Field(default="professional", description="fast | professional | master")
    qc_profile: str = Field(default="house_standard")
    style_guide: str = Field(default="sorani-default-v1")


class SourceConfig(BaseModel):
    prefer_existing_subtitles: bool = True
    allow_asr_fallback: bool = True
    preserve_source_timing: bool = True


class ASRConfig(BaseModel):
    local_provider: str = "faster-whisper"
    model: str = "large-v3"
    use_for_full_transcription_only_if_needed: bool = True
    use_for_verification: bool = True


class SemanticConfig(BaseModel):
    provider: str = "google"
    model: str = "gemini-2.5-pro"
    temperature: float = 0.2


class TranslationConfig(BaseModel):
    provider: str = "google"
    model: str = "gemini-2.5-pro"
    structured_output: bool = True
    scene_batch_min_cues: int = 10
    scene_batch_max_cues: int = 30


class VerificationConfig(BaseModel):
    enabled: bool = True
    provider: str = "google"
    model: str = "gemini-2.5-pro"
    trigger_threshold: float = 0.88
    verify_critical_flags: bool = True


class ContextConfig(BaseModel):
    use_movie_bible: bool = True
    use_series_bible: bool = True
    use_character_profiles: bool = True
    use_glossary: bool = True
    previous_scene_summary: bool = True
    next_scene_hint: bool = True


class SoraniConfig(BaseModel):
    force_ckb: bool = True
    forbid_kurmanji: bool = True
    unicode_normalization: bool = True
    rtl_normalization: bool = True


class QCProfile(BaseModel):
    max_lines: int = 2
    preferred_cps: float = 17.0
    hard_max_cps: float = 20.0
    preferred_cpl: int = 40
    hard_max_cpl: int = 42
    min_duration_ms: int = 800
    min_gap_ms: int = 80


class QCConfig(BaseModel):
    profile: str = "house_standard"
    semantic: bool = True
    linguistic: bool = True
    technical: bool = True


class PrivacyConfig(BaseModel):
    upload_entire_media: bool = False
    upload_only_required_clips: bool = True
    redact_logs: bool = True


class CacheConfig(BaseModel):
    enabled: bool = True


class JobsConfig(BaseModel):
    resumable: bool = True
    checkpoint_per_scene: bool = True


class HawsubConfig(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    source: SourceConfig = Field(default_factory=SourceConfig)
    asr: ASRConfig = Field(default_factory=ASRConfig)
    semantic: SemanticConfig = Field(default_factory=SemanticConfig)
    translation: TranslationConfig = Field(default_factory=TranslationConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    sorani: SoraniConfig = Field(default_factory=SoraniConfig)
    qc: QCConfig = Field(default_factory=QCConfig)
    profiles: Dict[str, QCProfile] = Field(
        default_factory=lambda: {"house_standard": QCProfile()}
    )
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    jobs: JobsConfig = Field(default_factory=JobsConfig)
