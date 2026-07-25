import os
import pytest
from hawsub.core.ingest.parser import SubtitleParser, SubtitleCueModel, parse_timestamp_srt, format_timestamp_srt
from hawsub.core.source_resolver.resolver import SourceResolver, SubtitleTrackInfo

SAMPLE_SRT = """1
00:01:20,000 --> 00:01:23,500
JOHN: You're pushing your luck.

2
00:01:24,000 --> 00:01:26,000
I told you to stop.
"""

def test_srt_parsing():
    cues = SubtitleParser.parse_srt(SAMPLE_SRT)
    assert len(cues) == 2
    
    assert cues[0].id == 1
    assert cues[0].start_ms == 80000
    assert cues[0].end_ms == 83500
    assert cues[0].speaker == "JOHN"
    assert cues[0].clean_source_text == "You're pushing your luck."

    assert cues[1].id == 2
    assert cues[1].start_ms == 84000
    assert cues[1].end_ms == 86000
    assert cues[1].clean_source_text == "I told you to stop."


def test_srt_serialization():
    cues = SubtitleParser.parse_srt(SAMPLE_SRT)
    cues[0].target_text = "تۆ زێدەڕۆیی لە بەختت دەکەیت."
    cues[1].target_text = "پێم گوتیت بوەستە."
    
    srt_out = SubtitleParser.serialize_srt(cues, use_target=True)
    assert "00:01:20,000 --> 00:01:23,500" in srt_out
    assert "تۆ زێدەڕۆیی لە بەختت دەکەیت." in srt_out


def test_source_resolver_sidecar(tmp_path):
    media_file = tmp_path / "movie.mp4"
    media_file.write_text("fake media content")
    
    sidecar_srt = tmp_path / "movie.en.srt"
    sidecar_srt.write_text(SAMPLE_SRT)
    
    resolver = SourceResolver(str(media_file))
    master_track = resolver.resolve_master_track()
    
    assert master_track.origin == "sidecar"
    assert master_track.language == "en"
    assert master_track.source_path == str(sidecar_srt)
