"""
Export Module: SRT, ASS, VTT, Bilingual Debug HTML, and QC Audit Reports.
"""

import json
import os
import html as html_mod
from typing import List, Optional, Dict, Any
from hawsub.core.ingest.parser import SubtitleCueModel, SubtitleParser, format_timestamp_srt
from hawsub.core.qc.engine import QCEvaluationResult


def format_timestamp_ass(ms: int) -> str:
    """Format milliseconds to ASS timestamp 'H:MM:SS.cs' (centiseconds)."""
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    cs = (ms % 1000) // 10
    return f"{hours}:{minutes:02d}:{seconds:02d}.{cs:02d}"


def format_timestamp_vtt(ms: int) -> str:
    """Format milliseconds to VTT timestamp 'HH:MM:SS.mmm'."""
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    millis = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


class SubtitleExporter:
    """Handles multi-format exports for Hawsub projects."""

    @staticmethod
    def export_srt(cues: List[SubtitleCueModel], output_path: str) -> str:
        content = SubtitleParser.serialize_srt(cues, use_target=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return output_path

    @staticmethod
    def export_vtt(cues: List[SubtitleCueModel], output_path: str) -> str:
        lines = ["WEBVTT", ""]
        for idx, cue in enumerate(cues, 1):
            text = cue.target_text if cue.target_text is not None else cue.source_text
            start_str = format_timestamp_vtt(cue.start_ms)
            end_str = format_timestamp_vtt(cue.end_ms)
            lines.append(f"{idx}\n{start_str} --> {end_str}\n{text}\n")
        content = "\n".join(lines)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return output_path

    @staticmethod
    def export_ass(cues: List[SubtitleCueModel], output_path: str, title: str = "Hawsub Sorani Subtitle") -> str:
        header = f"""[Script Info]
Title: {title}
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Naskh Arabic,28,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        event_lines = []
        for cue in cues:
            text = cue.target_text if cue.target_text is not None else cue.source_text
            # Format newlines for ASS
            ass_text = text.replace("\n", "\\N")
            start_str = format_timestamp_ass(cue.start_ms)
            end_str = format_timestamp_ass(cue.end_ms)
            event_lines.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{ass_text}")

        content = header + "\n".join(event_lines) + "\n"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return output_path

    @staticmethod
    def export_bilingual_debug_html(
        cues: List[SubtitleCueModel], qc_results: List[QCEvaluationResult], output_path: str
    ) -> str:
        qc_map = {r.cue_id: r for r in qc_results}
        
        rows = []
        for cue in cues:
            qc = qc_map.get(cue.id)
            conf = f"{qc.overall_confidence:.2f}" if qc else "N/A"
            status_color = "#28a745" if (qc and qc.passed) else "#dc3545"
            issues_str = html_mod.escape(", ".join([i.message for i in qc.issues])) if qc else ""
            source_escaped = html_mod.escape(cue.clean_source_text)
            target_escaped = html_mod.escape(cue.target_text or '')

            rows.append(f"""
            <tr>
                <td>{cue.id}</td>
                <td>{format_timestamp_srt(cue.start_ms)} --&gt; {format_timestamp_srt(cue.end_ms)}</td>
                <td>{source_escaped}</td>
                <td dir="rtl">{target_escaped}</td>
                <td style="color: {status_color}; font-weight: bold;">{conf}</td>
                <td style="font-size: 0.85em; color: #555;">{issues_str}</td>
            </tr>
            """)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Hawsub Bilingual Debug Inspection</title>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; margin: 20px; background: #f8f9fa; }}
        h1 {{ color: #212529; }}
        table {{ width: 100%; border-collapse: collapse; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        th, td {{ padding: 10px 12px; border: 1px solid #dee2e6; text-align: left; }}
        th {{ background: #e9ecef; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
    </style>
</head>
<body>
    <h1>Hawsub — English to Sorani Subtitle Debug Inspection</h1>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>Timecode</th>
                <th>English Source</th>
                <th>Central Kurdish (Sorani)</th>
                <th>Confidence</th>
                <th>QC Issues</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows)}
        </tbody>
    </table>
</body>
</html>
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        return output_path

    @staticmethod
    def export_qc_report(
        project_id: str, qc_results: List[QCEvaluationResult], output_path: str
    ) -> str:
        total_cues = len(qc_results)
        passed_cues = sum(1 for r in qc_results if r.passed)
        review_required = sum(1 for r in qc_results if r.requires_review)
        avg_confidence = (
            sum(r.overall_confidence for r in qc_results) / total_cues if total_cues > 0 else 0.0
        )

        report_data = {
            "project_id": project_id,
            "total_cues": total_cues,
            "passed_cues": passed_cues,
            "review_required_cues": review_required,
            "average_confidence": round(avg_confidence, 3),
            "evaluations": [r.model_dump() for r in qc_results],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        return output_path
