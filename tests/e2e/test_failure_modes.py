"""sumtube + media-downloader — explicit failure contracts.

Validates that documented error paths surface clean exit codes and
useful messages instead of stack traces. Offline-friendly except where
network is needed to reach a known-bad endpoint.
"""

from __future__ import annotations

import os
import subprocess

import pytest

from conftest import run_subprocess, REPO_ROOT


# ---------- 1. Missing GROQ_API_KEY on a caption-less local file ----------

def test_local_file_without_groq_key_fails_cleanly(
    python_executable, sumtube_script, zoo_fixture, tmp_path
):
    """Local file path always uses Whisper. Without GROQ_API_KEY anywhere
    (env nor .env), sumtube must exit non-zero with a clear message.

    Subtlety: the plugin loads `plugins/sumtube/.env` via python-dotenv,
    so `os.environ` manipulation alone is insufficient. We temporarily
    rename the .env file (if present) for the duration of the run so the
    subprocess has truly no Groq key available, then restore it.
    """
    anthropic_key = os.environ.get("SUMTUBE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        pytest.skip("needs Anthropic key to reach the Whisper path")

    env = {k: v for k, v in os.environ.items() if k != "GROQ_API_KEY"}
    env["SUMTUBE_API_KEY"] = anthropic_key

    dotenv_path = REPO_ROOT / "plugins" / "sumtube" / ".env"
    masked_path = dotenv_path.with_suffix(".env.masked-for-test")
    moved = False
    if dotenv_path.exists():
        dotenv_path.rename(masked_path)
        moved = True

    try:
        result = subprocess.run(
            [python_executable, str(sumtube_script), str(zoo_fixture),
             "--compact", "-o", str(tmp_path), "--force"],
            capture_output=True, text=True, timeout=60, env=env,
        )
    finally:
        if moved:
            masked_path.rename(dotenv_path)

    assert result.returncode != 0, (
        f"expected non-zero exit when GROQ_API_KEY absent. "
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = (result.stdout + result.stderr).lower()
    assert "groq" in combined or "api key" in combined or "missing" in combined, (
        f"error message should mention Groq / API key. got:\n{result.stdout}\n{result.stderr}"
    )


# ---------- 2. Audio file too large (>25MB) ----------

@pytest.mark.slow
def test_audio_file_too_large_rejected(
    python_executable, sumtube_script, has_ffmpeg, tmp_path
):
    """sumtube enforces the 25 MB Groq Whisper upload limit.

    Sizing math: sumtube's transcript pipeline re-encodes audio to mono
    mp3 at 64 kbps (8 KB/s) before uploading to Whisper, regardless of
    the source bitrate. So the size that matters for the 25 MB gate is
    `duration * 8 KB`, not the input file's on-disk size. To clear 25 MB
    after re-encode we need ~3200 s of audio; we use 3500 s to give the
    rejection clear headroom.
    """
    if not has_ffmpeg:
        pytest.skip("ffmpeg required to synthesise oversize fixture")
    if not os.environ.get("GROQ_API_KEY"):
        pytest.skip("Whisper limit only matters when Groq is configured")

    big = tmp_path / "big.mp4"
    # 3500 s × 64 kbps mono mp3 ≈ 28 MB after re-encode (>25 MB Whisper cap).
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=color=white:duration=3500",
         "-c:a", "aac", "-b:a", "64k", str(big)],
        check=True, capture_output=True, timeout=300,
    )

    result = run_subprocess(
        [python_executable, str(sumtube_script), str(big),
         "--compact", "-o", str(tmp_path), "--force"],
        timeout=300,
    )
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "25" in combined or "too large" in combined or "limit" in combined, (
        f"error should mention 25MB / too large. got:\n{result.stdout}\n{result.stderr}"
    )


# ---------- 3. Bad Anthropic key surfaces a clean error ----------

@pytest.mark.live
def test_bad_anthropic_key_surfaces_clean_error(
    python_executable, sumtube_script, zoo_fixture, tmp_path, monkeypatch
):
    """A clearly-invalid Anthropic key must produce a non-zero exit and
    a message the user can act on — not a Python traceback.
    """
    if not os.environ.get("GROQ_API_KEY"):
        pytest.skip("needs Groq for Whisper to reach the Anthropic call")

    monkeypatch.setenv("SUMTUBE_API_KEY", "sk-ant-invalid-key-for-testing")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-invalid-key-for-testing")

    result = run_subprocess(
        [python_executable, str(sumtube_script), str(zoo_fixture),
         "--compact", "-o", str(tmp_path), "--force"],
        timeout=120,
    )
    assert result.returncode != 0
    # The CLI should surface the auth failure, not raise an unhandled exception.
    combined = (result.stdout + result.stderr).lower()
    assert "401" in combined or "auth" in combined or "api key" in combined or "invalid" in combined, (
        f"Anthropic auth error should be surfaced clearly. got:\n{result.stdout}\n{result.stderr}"
    )
    # Negative assertion: no raw Python traceback leaking through.
    assert "Traceback (most recent call last)" not in (result.stdout + result.stderr), (
        "raw traceback leaked to user — wrap the API call in proper error handling"
    )


# ---------- 4. Nonexistent input path is rejected before any work ----------

def test_nonexistent_input_path_rejected(python_executable, sumtube_script, tmp_path):
    """Running sumtube on /does/not/exist must exit non-zero immediately
    without contacting any API.
    """
    result = run_subprocess(
        [python_executable, str(sumtube_script), "/does/not/exist.mp4",
         "--compact", "-o", str(tmp_path)],
        timeout=10,
    )
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "exist" in combined or "not found" in combined or "no such" in combined, (
        f"error should mention file does not exist. got:\n{result.stdout}\n{result.stderr}"
    )


# ---------- 5. media-downloader on a non-existent URL surfaces a clean error ----------

@pytest.mark.live
def test_media_downloader_bad_url_surfaces_clean_error(
    python_executable, media_downloader_script, has_yt_dlp, tmp_path
):
    """yt-dlp's failure must propagate as a non-zero exit with a useful
    message, not a silent success.
    """
    if not has_yt_dlp:
        pytest.skip("yt-dlp required")

    # A URL that yt-dlp can resolve as YouTube-shaped but with a non-existent ID.
    bad_url = "https://www.youtube.com/watch?v=AAAAAAAAAAA"

    result = run_subprocess(
        [python_executable, str(media_downloader_script), bad_url,
         "--output", str(tmp_path), "--no-compress"],
        timeout=60,
    )
    assert result.returncode != 0, "bad URL must not exit 0"
    combined = (result.stdout + result.stderr).lower()
    assert "error" in combined or "unavailable" in combined or "video" in combined, (
        f"error should mention the failed download. got:\n{result.stdout}\n{result.stderr}"
    )
