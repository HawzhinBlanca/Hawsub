"""
Source Track Resolver for Hawsub.
Discovers, enumerates, ranks, and validates subtitle sources (embedded & sidecar).
"""

import os
import subprocess
import json
from pathlib import Path
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class SubtitleTrackInfo(BaseModel):
    id: str
    origin: str  # embedded | sidecar | transcript | asr
    language: str = "en"
    format: str = "srt"
    track_type: str = "full"  # full | forced | sdh | unknown
    quality_score: float = 1.0
    selected_as_master: bool = False
    source_path: str
    provenance_notes: str = ""


class SourceResolver:
    """Discovers and ranks subtitle track sources for media files."""

    def __init__(self, media_path: str):
        self.media_path = media_path

    def scan_sidecar_subtitles(self) -> List[SubtitleTrackInfo]:
        """Scan directory of media file for sidecar subtitle files."""
        sidecars = []
        base_dir = os.path.dirname(self.media_path) or "."
        base_name = os.path.splitext(os.path.basename(self.media_path))[0]

        valid_exts = {".srt", ".ass", ".vtt"}
        if not os.path.exists(base_dir):
            return sidecars

        for file in os.listdir(base_dir):
            ext = os.path.splitext(file)[1].lower()
            if ext in valid_exts:
                full_path = os.path.join(base_dir, file)
                
                # Determine language and track type from filename
                lower_file = file.lower()
                lang = "en" if ("en" in lower_file or "eng" in lower_file) else "unknown"
                
                track_type = "full"
                if "forced" in lower_file:
                    track_type = "forced"
                elif "sdh" in lower_file or "cc" in lower_file:
                    track_type = "sdh"

                # Score quality
                score = 0.9
                if lower_file.startswith(base_name.lower()):
                    score += 0.05
                if lang == "en":
                    score += 0.05

                sidecars.append(
                    SubtitleTrackInfo(
                        id=f"sidecar_{file}",
                        origin="sidecar",
                        language=lang,
                        format=ext.lstrip("."),
                        track_type=track_type,
                        quality_score=score,
                        source_path=full_path,
                        provenance_notes=f"Sidecar file discovered at {full_path}",
                    )
                )

        return sidecars

    def scan_embedded_subtitles(self) -> List[SubtitleTrackInfo]:
        """Use ffprobe to discover embedded subtitle streams in media file."""
        embedded = []
        if not os.path.exists(self.media_path):
            return embedded

        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            self.media_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            streams = data.get("streams", [])
            for idx, stream in enumerate(streams):
                if stream.get("codec_type") == "subtitle":
                    tags = stream.get("tags", {})
                    lang = tags.get("language", "unknown")
                    title = tags.get("title", "").lower()

                    track_type = "full"
                    if "forced" in title:
                        track_type = "forced"
                    elif "sdh" in title or "cc" in title:
                        track_type = "sdh"

                    score = 0.95 if lang == "eng" else 0.5
                    embedded.append(
                        SubtitleTrackInfo(
                            id=f"embedded_stream_{idx}",
                            origin="embedded",
                            language="en" if lang in ["eng", "en"] else lang,
                            format=stream.get("codec_name", "srt"),
                            track_type=track_type,
                            quality_score=score,
                            source_path=self.media_path,
                            provenance_notes=f"FFprobe stream #{idx} ({stream.get('codec_name')})",
                        )
                    )
        except Exception:
            # If ffprobe is not installed or file is not media, pass silently
            pass

        return embedded

    def resolve_master_track(self, manual_override_path: Optional[str] = None) -> SubtitleTrackInfo:
        """Rank and return the best master subtitle source track."""
        if manual_override_path and os.path.exists(manual_override_path):
            return SubtitleTrackInfo(
                id="manual_override",
                origin="manual",
                language="en",
                format=os.path.splitext(manual_override_path)[1].lstrip("."),
                track_type="full",
                quality_score=1.0,
                selected_as_master=True,
                source_path=manual_override_path,
                provenance_notes=f"Manual user override: {manual_override_path}",
            )

        all_tracks = self.scan_sidecar_subtitles() + self.scan_embedded_subtitles()

        # Sort by quality score descending
        all_tracks.sort(key=lambda x: x.quality_score, reverse=True)

        if all_tracks:
            all_tracks[0].selected_as_master = True
            return all_tracks[0]

        # Fallback to ASR trigger indicator
        return SubtitleTrackInfo(
            id="asr_fallback",
            origin="asr",
            language="en",
            format="srt",
            track_type="full",
            quality_score=0.7,
            selected_as_master=True,
            source_path=self.media_path,
            provenance_notes="No existing subtitle track found. Triggering English ASR fallback.",
        )
