"""sumtube — flag-specific paths.

Covers --transcript-only (free, captions-only), --visual (paid, frames),
--max-chunk-words (paid, chunking), and parens-in-filename regression.
"""

from __future__ import annotations

import shutil

import pytest

from conftest import run_subprocess

YOUTUBE_SHORT = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo", 19s
YOUTUBE_LONG = "https://www.youtube.com/watch?v=8jPQjjsBbIc"  # TED, ~5min, ~2200-word transcript


@pytest.mark.live
def test_transcript_only_no_anthropic_call(python_executable, sumtube_script, tmp_path):
    """--transcript-only must not POST to api.anthropic.com.

    Free flag — does not require any API key.
    """
    result = run_subprocess(
        [
            python_executable, str(sumtube_script),
            YOUTUBE_SHORT,
            "--transcript-only",
            "--output", str(tmp_path),
            "--force",
        ],
        timeout=120,
    )
    assert result.returncode == 0, (
        f"sumtube exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # Negative assertion: no Anthropic call should appear in the structured log
    combined = result.stdout + result.stderr
    assert "api.anthropic.com/v1/messages" not in combined, (
        "--transcript-only emitted an Anthropic API call (should be free)"
    )


@pytest.mark.live
@pytest.mark.paid
@pytest.mark.slow
def test_visual_flag_runs_vision_pass(python_executable, sumtube_script, has_yt_dlp, has_ffmpeg, tmp_path):
    """--visual downloads video, extracts frames, runs claude-sonnet vision pass."""
    if not has_yt_dlp:
        pytest.skip("yt-dlp required for video download")
    if not has_ffmpeg:
        pytest.skip("ffmpeg required for frame extraction")

    result = run_subprocess(
        [
            python_executable, str(sumtube_script),
            YOUTUBE_SHORT,
            "--compact",
            "--visual",
            "--output", str(tmp_path),
            "--force",
        ],
        timeout=420,
    )
    assert result.returncode == 0, (
        f"sumtube --visual exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    notes = list(tmp_path.rglob("*.md"))
    assert notes, f"no markdown note produced in {tmp_path}"


@pytest.mark.live
@pytest.mark.paid
@pytest.mark.slow
def test_max_chunk_words_chunking(python_executable, sumtube_script, tmp_path):
    """Long transcript with a small chunk cap exercises the chunked summarisation path."""
    result = run_subprocess(
        [
            python_executable, str(sumtube_script),
            YOUTUBE_LONG,
            "--compact",
            "--max-chunk-words", "500",
            "--output", str(tmp_path),
            "--force",
        ],
        timeout=420,
    )
    assert result.returncode == 0, (
        f"sumtube chunking exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    notes = list(tmp_path.rglob("*.md"))
    assert notes, f"no markdown note produced in {tmp_path}"


@pytest.mark.live
@pytest.mark.paid
def test_parens_in_filename_accepted(
    python_executable, sumtube_script, zoo_fixture, has_groq_key, has_ffmpeg, tmp_path
):
    """Local file with ( ) in the path must be accepted by the validator.

    regression: v0.1.5 (B2). Validator previously rejected `()` as shell
    metacharacters despite every subprocess call using shell=False, breaking
    the media-downloader → sumtube handoff (yt-dlp produces filenames with
    parens by default).
    """
    if not has_groq_key:
        pytest.skip("GROQ_API_KEY required for Whisper path")
    if not has_ffmpeg:
        pytest.skip("ffmpeg required for audio extraction")

    parens_path = tmp_path / "Title (Year) Stuff.mp4"
    shutil.copy(zoo_fixture, parens_path)

    result = run_subprocess(
        [
            python_executable, str(sumtube_script),
            str(parens_path),
            "--compact",
            "--output", str(tmp_path),
            "--force",
        ],
        timeout=240,
    )

    # Negative regression assertion
    assert "shell metacharacter" not in result.stderr, (
        "v0.1.5 regression: paren in filename rejected by validator\n"
        f"stderr: {result.stderr}"
    )
    assert result.returncode == 0, (
        f"sumtube exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
