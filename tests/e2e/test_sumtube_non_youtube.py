"""sumtube — non-YouTube URL path (yt-dlp + Whisper).

regression: v0.1.6 mkstemp-stub conflict. tempfile.mkstemp(suffix=".mp3")
pre-created an empty file; yt-dlp saw the path existed, skipped download,
then postprocessed the stub — ffprobe failed to obtain audio codec.
v0.1.6 unlinks the stub before yt-dlp runs.
"""

from __future__ import annotations

import pytest

from conftest import run_subprocess

VIMEO_URL = "https://vimeo.com/76979871"  # "The New Vimeo Player", ~1m


@pytest.mark.live
@pytest.mark.paid
@pytest.mark.slow
def test_vimeo_direct_via_yt_dlp_and_whisper(
    python_executable, sumtube_script, has_groq_key, has_yt_dlp, has_ffmpeg, tmp_path
):
    if not has_groq_key:
        pytest.skip("GROQ_API_KEY required for non-YouTube URL Whisper path")
    if not has_yt_dlp:
        pytest.skip("yt-dlp required for non-YouTube URL download")
    if not has_ffmpeg:
        pytest.skip("ffmpeg required for audio postprocess")

    result = run_subprocess(
        [
            python_executable, str(sumtube_script),
            VIMEO_URL,
            "--compact",
            "--output", str(tmp_path),
            "--force",
        ],
        timeout=300,
    )

    # Regression assertion: this was the v0.1.6 bug. Match against the
    # specific stderr signature so a future regression is identifiable.
    assert "unable to obtain file audio codec with ffprobe" not in result.stderr, (
        "v0.1.6 regression: yt-dlp postprocess failed on empty mkstemp stub\n"
        f"stderr: {result.stderr}"
    )
    assert result.returncode == 0, (
        f"sumtube exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    notes = list(tmp_path.rglob("*.md"))
    assert notes, f"no markdown note produced in {tmp_path}"
