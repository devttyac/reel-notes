"""sumtube — audio-file input and Whisper language pinning.

Regression guards for two defects found 2026-09-16 while transcribing a
26-minute voice recording:

1. Audio files were rejected at the CLI gate. ``_AUDIO_EXTENSIONS`` and the
   "already extracted audio, skip ffmpeg" branch in ``_whisper_fallback``
   both existed, but ``detect_input_type`` only admitted video extensions,
   so that branch was unreachable from the command line. Callers had to
   remux audio into an .mp4 container to get it accepted, which also forced
   a pointless transcode.

2. The Groq Whisper call passed no ``language``, leaving it to auto-detect.
   On Singapore-accented English in a 32 kbps mono recording, auto-detect
   chose Malay and returned a full transcript in the wrong language.

These tests run offline: no network, no API key, no ffmpeg.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins" / "sumtube" / "scripts"


def _load_transcript_module(name: str = "transcript_under_test"):
    """Import transcript.py with third-party deps stubbed."""
    for mod_name in ("youtube_transcript_api", "youtube_transcript_api._errors"):
        sys.modules.setdefault(mod_name, types.ModuleType(mod_name))
    sys.modules["youtube_transcript_api"].YouTubeTranscriptApi = object
    for exc in (
        "TranscriptsDisabled",
        "NoTranscriptFound",
        "VideoUnavailable",
        "CouldNotRetrieveTranscript",
    ):
        for mod_name in ("youtube_transcript_api", "youtube_transcript_api._errors"):
            setattr(sys.modules[mod_name], exc, type(exc, (Exception,), {}))

    spec = importlib.util.spec_from_file_location(name, SCRIPTS / "transcript.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def transcript_mod():
    return _load_transcript_module()


@pytest.fixture
def fake_groq(monkeypatch):
    """Stub the groq SDK and capture the kwargs sent to the transcription API."""
    captured: dict = {}

    class _Transcriptions:
        def create(self, **kwargs):
            captured.update(kwargs)
            captured["file_name"] = getattr(kwargs["file"], "name", None)
            return types.SimpleNamespace(
                text="stub", language="english", duration=1.0, segments=[]
            )

    class _Audio:
        transcriptions = _Transcriptions()

    class _FakeGroq:
        def __init__(self, *args, **kwargs):
            pass

        audio = _Audio()

    groq_module = types.ModuleType("groq")
    groq_module.Groq = _FakeGroq
    monkeypatch.setitem(sys.modules, "groq", groq_module)
    monkeypatch.setenv("GROQ_API_KEY", "stub-key-not-real")
    return captured


# ---------- 1. Audio accepted at the input gate ----------

@pytest.mark.parametrize("ext", [".m4a", ".mp3", ".wav", ".flac", ".ogg", ".aac", ".opus"])
def test_audio_extensions_accepted_as_local_file(transcript_mod, tmp_path, ext):
    """Audio files must be admitted by detect_input_type.

    Before the fix these raised ValueError("Unsupported file extension"),
    which made the audio branch of _whisper_fallback unreachable.
    """
    probe = tmp_path / f"probe{ext}"
    probe.write_bytes(b"x")
    assert transcript_mod.detect_input_type(str(probe)) == transcript_mod.INPUT_TYPE_LOCAL_FILE


@pytest.mark.parametrize("ext", [".mp4", ".mov", ".mkv", ".webm"])
def test_video_extensions_still_accepted(transcript_mod, tmp_path, ext):
    """Widening the gate must not disturb the existing video path."""
    probe = tmp_path / f"probe{ext}"
    probe.write_bytes(b"x")
    assert transcript_mod.detect_input_type(str(probe)) == transcript_mod.INPUT_TYPE_LOCAL_FILE


def test_unsupported_extension_still_rejected(transcript_mod, tmp_path):
    """The gate must stay closed to genuinely unsupported types."""
    probe = tmp_path / "probe.txt"
    probe.write_bytes(b"x")
    with pytest.raises(ValueError, match="Unsupported file extension"):
        transcript_mod.detect_input_type(str(probe))


def test_extract_audio_remains_video_only(transcript_mod):
    """_validate_input_path guards the ffmpeg path and must stay video-only.

    Audio bypasses _extract_audio entirely; if this validator were widened,
    audio would be sent through a transcode it does not need.
    """
    import inspect

    assert "_SUPPORTED_VIDEO_EXTENSIONS" in inspect.getsource(
        transcript_mod._validate_input_path
    )


# ---------- 2. Audio bypasses ffmpeg ----------

def test_audio_input_skips_ffmpeg(transcript_mod, fake_groq, tmp_path, monkeypatch):
    """An audio input must go straight to Groq without a transcode."""
    calls = {"n": 0}
    monkeypatch.setattr(
        transcript_mod,
        "_extract_audio",
        lambda path: calls.__setitem__("n", calls["n"] + 1) or path,
    )
    audio = tmp_path / "clip.m4a"
    audio.write_bytes(b"x")

    transcript_mod._whisper_fallback(str(audio))

    assert calls["n"] == 0, "audio input must not be routed through ffmpeg"
    assert fake_groq["file_name"] == str(audio)


def test_oversize_audio_rejected_before_upload(transcript_mod, fake_groq, tmp_path):
    """The 25 MB Groq gate must apply to audio inputs too.

    The size check lives in _extract_audio, which the audio branch skips.
    Without an equivalent check here, an oversize audio file would reach the
    API and fail with a raw provider error instead of AudioFileTooLargeError.
    """
    big = tmp_path / "big.m4a"
    big.write_bytes(b"0" * (transcript_mod._MAX_AUDIO_BYTES + 1))
    with pytest.raises(transcript_mod.AudioFileTooLargeError, match="25 MB"):
        transcript_mod._whisper_fallback(str(big))
    assert "file" not in fake_groq, "oversize audio must not be uploaded"


# ---------- 3. Language pinning ----------

def test_explicit_language_forwarded_to_whisper(transcript_mod, fake_groq, tmp_path):
    """--language must reach the Groq transcription call."""
    audio = tmp_path / "clip.m4a"
    audio.write_bytes(b"x")
    transcript_mod._whisper_fallback(str(audio), language="en")
    assert fake_groq.get("language") == "en"


def test_language_omitted_when_unset(transcript_mod, fake_groq, tmp_path, monkeypatch):
    """With no argument and no env var, Whisper keeps auto-detecting.

    Guards backwards compatibility: pinning must stay opt-in. This test
    originally failed because the env var was captured into a module-level
    constant at import time, so clearing it afterwards had no effect — and
    any shell that happened to export SUMTUBE_WHISPER_LANGUAGE leaked into
    the run. The value is now read inside _whisper_fallback.
    """
    monkeypatch.delenv("SUMTUBE_WHISPER_LANGUAGE", raising=False)
    audio = tmp_path / "clip.m4a"
    audio.write_bytes(b"x")
    transcript_mod._whisper_fallback(str(audio))
    assert "language" not in fake_groq


def test_env_var_used_as_fallback(transcript_mod, fake_groq, tmp_path, monkeypatch):
    """SUMTUBE_WHISPER_LANGUAGE applies when no explicit argument is given.

    Also guards the read-at-call-time contract: the variable is set *after*
    the module was imported, and must still take effect.
    """
    monkeypatch.setenv("SUMTUBE_WHISPER_LANGUAGE", "ms")
    audio = tmp_path / "clip.m4a"
    audio.write_bytes(b"x")
    transcript_mod._whisper_fallback(str(audio))
    assert fake_groq.get("language") == "ms"


def test_explicit_language_beats_env_var(transcript_mod, fake_groq, tmp_path, monkeypatch):
    """Explicit argument must win over the environment variable."""
    monkeypatch.setenv("SUMTUBE_WHISPER_LANGUAGE", "ms")
    audio = tmp_path / "clip.m4a"
    audio.write_bytes(b"x")
    transcript_mod._whisper_fallback(str(audio), language="en")
    assert fake_groq.get("language") == "en"


# ---------- 4. CLI surface ----------

def test_language_flag_exposed_in_cli_help(python_executable, sumtube_script):
    """--language must be discoverable, not env-var-only."""
    from conftest import run_subprocess

    result = run_subprocess([python_executable, str(sumtube_script), "--help"], timeout=30)
    assert "--language" in result.stdout, (
        f"--language missing from --help output:\n{result.stdout}"
    )
