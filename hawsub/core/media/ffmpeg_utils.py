"""
FFmpeg & Media Processing Utilities for Hawsub.
"""

import os
import subprocess
import json
from typing import Dict, Any, Optional, List


class MediaInspector:
    """Wrapper around FFmpeg and FFprobe for media analysis and audio clip extraction."""

    @staticmethod
    def probe_media(media_path: str) -> Dict[str, Any]:
        if not os.path.exists(media_path):
            return {"duration_ms": 0, "has_video": False, "has_audio": False}

        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            media_path,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(res.stdout)
            fmt = data.get("format", {})
            duration_sec = float(fmt.get("duration", 0.0))
            streams = data.get("streams", [])
            has_video = any(s.get("codec_type") == "video" for s in streams)
            has_audio = any(s.get("codec_type") == "audio" for s in streams)

            return {
                "duration_ms": int(duration_sec * 1000),
                "container": fmt.get("format_name", ""),
                "has_video": has_video,
                "has_audio": has_audio,
                "streams": streams,
            }
        except Exception:
            return {"duration_ms": 0, "has_video": False, "has_audio": False}

    @staticmethod
    def extract_audio_clip(
        media_path: str, start_ms: int, end_ms: int, output_wav_path: str
    ) -> bool:
        """Extract a short WAV audio segment using FFmpeg."""
        if not os.path.exists(media_path):
            return False

        start_sec = start_ms / 1000.0
        duration_sec = max(0.5, (end_ms - start_ms) / 1000.0)

        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start_sec),
            "-i", media_path,
            "-t", str(duration_sec),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            output_wav_path,
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return os.path.exists(output_wav_path)
        except Exception:
            return False
