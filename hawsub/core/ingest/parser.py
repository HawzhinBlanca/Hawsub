"""
Subtitle Parser and Serializer for SRT, ASS, and VTT formats.
"""

import re
from typing import List, Optional
from pydantic import BaseModel, Field


class SubtitleCueModel(BaseModel):
    id: int
    start_ms: int
    end_ms: int
    source_text: str
    target_text: Optional[str] = None
    speaker: Optional[str] = None
    scene_id: Optional[str] = None
    source_confidence: float = 1.0
    foreign_language: bool = False
    narrative_opacity: bool = False

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)

    @property
    def clean_source_text(self) -> str:
        """Strip formatting tags and speaker labels."""
        text = re.sub(r"<[^>]+>", "", self.source_text)
        text = re.sub(r"\{[^}]+\}", "", text)
        if self.speaker and text.startswith(f"{self.speaker}:"):
            text = text[len(self.speaker) + 1:].strip()
        return text.strip()


def parse_timestamp_srt(ts_str: str) -> int:
    """Parse SRT timestamp 'HH:MM:SS,mmm' to milliseconds."""
    ts_str = ts_str.replace(".", ",").strip()
    match = re.match(r"(\d+):(\d+):(\d+)[,:](\d+)", ts_str)
    if not match:
        raise ValueError(f"Invalid timestamp format: {ts_str}")
    hours, minutes, seconds, millis = map(int, match.groups())
    # Pad milliseconds if needed
    if len(match.group(4)) == 2:
        millis *= 10
    elif len(match.group(4)) == 1:
        millis *= 100
    return (hours * 3600 + minutes * 60 + seconds) * 1000 + millis


def format_timestamp_srt(ms: int) -> str:
    """Format milliseconds to SRT timestamp 'HH:MM:SS,mmm'."""
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    millis = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def parse_timestamp_vtt(ts_str: str) -> int:
    """Parse VTT timestamp 'HH:MM:SS.mmm' or 'MM:SS.mmm' to milliseconds."""
    ts_str = ts_str.strip()
    parts = ts_str.split(":")
    if len(parts) == 2:
        hours = 0
        minutes, sec_milli = parts
    elif len(parts) == 3:
        hours, minutes, sec_milli = parts
    else:
        raise ValueError(f"Invalid VTT timestamp: {ts_str}")

    sec_parts = sec_milli.split(".")
    seconds = int(sec_parts[0])
    millis = 0
    if len(sec_parts) > 1 and sec_parts[1]:
        frac = sec_parts[1]
        if len(frac) == 1:
            millis = int(frac) * 100
        elif len(frac) == 2:
            millis = int(frac) * 10
        else:
            millis = int(frac[:3])

    return (int(hours) * 3600 + int(minutes) * 60 + seconds) * 1000 + millis


class SubtitleParser:
    """Parser for SRT, VTT, and ASS files."""

    @staticmethod
    def parse_srt(content: str) -> List[SubtitleCueModel]:
        # Strip BOM if present
        if content.startswith("\ufeff"):
            content = content[1:]
        cues = []
        blocks = re.split(r"\n\s*\n", content.strip())
        
        cue_idx = 1
        for block in blocks:
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue

            # Skip numeric sequence header if present
            time_line_idx = 0
            if lines[0].isdigit():
                time_line_idx = 1
            
            if time_line_idx >= len(lines):
                continue

            time_line = lines[time_line_idx]
            if "-->" not in time_line:
                continue

            parts = time_line.split("-->")
            start_ms = parse_timestamp_srt(parts[0].strip())
            end_ms = parse_timestamp_srt(parts[1].split()[0].strip())

            text_lines = lines[time_line_idx + 1:]
            text = "\n".join(text_lines)

            # Check for speaker label like "JOHN: Hello"
            speaker = None
            speaker_match = re.match(r"^([A-Z0-9\s\_]+):\s*(.*)", text, re.DOTALL)
            if speaker_match:
                possible_speaker = speaker_match.group(1).strip()
                if len(possible_speaker) <= 30:
                    speaker = possible_speaker

            cues.append(
                SubtitleCueModel(
                    id=cue_idx,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    source_text=text,
                    speaker=speaker,
                )
            )
            cue_idx += 1

        return cues

    @staticmethod
    def parse_vtt(content: str) -> List[SubtitleCueModel]:
        # Strip BOM if present
        if content.startswith("\ufeff"):
            content = content[1:]
        lines = content.strip().split("\n")
        cues = []
        cue_idx = 1
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
                i += 1
                continue

            if "-->" in line:
                parts = line.split("-->")
                start_ms = parse_timestamp_vtt(parts[0].strip())
                end_ms = parse_timestamp_vtt(parts[1].split()[0].strip())

                i += 1
                text_lines = []
                while i < len(lines) and lines[i].strip():
                    text_lines.append(lines[i].strip())
                    i += 1
                
                text = "\n".join(text_lines)
                cues.append(
                    SubtitleCueModel(
                        id=cue_idx,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        source_text=text,
                    )
                )
                cue_idx += 1
            else:
                i += 1

        return cues

    @staticmethod
    def serialize_srt(cues: List[SubtitleCueModel], use_target: bool = True) -> str:
        blocks = []
        for idx, cue in enumerate(cues, 1):
            text = cue.target_text if (use_target and cue.target_text is not None) else cue.source_text
            start_str = format_timestamp_srt(cue.start_ms)
            end_str = format_timestamp_srt(cue.end_ms)
            blocks.append(f"{idx}\n{start_str} --> {end_str}\n{text}")
        return "\n\n".join(blocks) + "\n"

    @staticmethod
    def parse_ass(content: str) -> List[SubtitleCueModel]:
        """Parse ASS/SSA subtitle format."""
        # Strip BOM if present
        if content.startswith("\ufeff"):
            content = content[1:]
        cues = []
        cue_idx = 1
        in_events = False
        format_fields: List[str] = []

        for line in content.split("\n"):
            line = line.strip()
            if line.lower().startswith("[events]"):
                in_events = True
                continue
            if line.startswith("[") and in_events:
                break  # New section, stop

            if in_events and line.lower().startswith("format:"):
                fields_str = line.split(":", 1)[1]
                format_fields = [f.strip().lower() for f in fields_str.split(",")]
                continue

            if in_events and line.startswith("Dialogue:"):
                values_str = line.split(":", 1)[1].strip()
                # ASS dialogue: split only up to the number of format fields minus 1
                # The last field (Text) may contain commas
                parts = values_str.split(",", len(format_fields) - 1) if format_fields else values_str.split(",", 9)

                if not format_fields:
                    # Default ASS format
                    format_fields = ["layer", "start", "end", "style", "name",
                                     "marginl", "marginr", "marginv", "effect", "text"]

                field_map = {}
                for i, field in enumerate(format_fields):
                    if i < len(parts):
                        field_map[field] = parts[i].strip()

                start_str = field_map.get("start", "0:00:00.00")
                end_str = field_map.get("end", "0:00:00.00")
                text = field_map.get("text", "")

                # Convert ASS line breaks to newlines
                text = text.replace("\\N", "\n").replace("\\n", "\n")
                # Remove ASS formatting tags like {\b1}, {\i1}, {\pos(x,y)}, etc.
                text = re.sub(r"\{[^}]*\}", "", text)
                text = text.strip()

                if not text:
                    continue

                start_ms = _parse_ass_timestamp(start_str)
                end_ms = _parse_ass_timestamp(end_str)

                cues.append(
                    SubtitleCueModel(
                        id=cue_idx,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        source_text=text,
                    )
                )
                cue_idx += 1

        return cues

    @staticmethod
    def parse_auto(content: str, filename: str) -> List[SubtitleCueModel]:
        """Auto-detect format from filename extension and parse."""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext == "vtt":
            return SubtitleParser.parse_vtt(content)
        elif ext in ("ass", "ssa"):
            return SubtitleParser.parse_ass(content)
        else:
            return SubtitleParser.parse_srt(content)


def _parse_ass_timestamp(ts_str: str) -> int:
    """Parse ASS timestamp 'H:MM:SS.cs' (centiseconds) to milliseconds."""
    ts_str = ts_str.strip()
    match = re.match(r"(\d+):(\d+):(\d+)\.(\d+)", ts_str)
    if not match:
        return 0
    hours, minutes, seconds, centiseconds = map(int, match.groups())
    return (hours * 3600 + minutes * 60 + seconds) * 1000 + centiseconds * 10

