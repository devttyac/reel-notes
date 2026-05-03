"""media-downloader — download + compression paths.

regression: v0.1.4 webm-source compression bug. download.py inherited the
input file's container suffix (.webm) but ffmpeg was forced to encode
libx264+aac, producing a 264-byte broken file. v0.1.4 hardcodes .mp4.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from conftest import run_subprocess

YOUTUBE_SHORT = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # downloads as .webm by default


def _ffprobe_codecs(path: str) -> dict:
    """Return {'video': codec_name, 'audio': codec_name} for the given file."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_name,codec_type",
            "-of", "default=nw=1",
            path,
        ],
        capture_output=True, text=True, timeout=30,
    )
    codecs = {}
    current_type = None
    for line in result.stdout.splitlines():
        if line.startswith("codec_name="):
            name = line.split("=", 1)[1]
            if current_type:
                codecs[current_type] = name
        elif line.startswith("codec_type="):
            current_type = line.split("=", 1)[1]
    return codecs


@pytest.mark.live
@pytest.mark.slow
def test_compression_webm_source_produces_valid_mp4(
    python_executable, media_downloader_script, has_yt_dlp, has_ffmpeg, has_ffprobe, tmp_path
):
    """Webm source → compressed.mp4 with h264+aac. Regression for v0.1.4."""
    if not has_yt_dlp:
        pytest.skip("yt-dlp required")
    if not has_ffmpeg:
        pytest.skip("ffmpeg required")
    if not has_ffprobe:
        pytest.skip("ffprobe required for codec assertion")

    result = run_subprocess(
        [
            python_executable, str(media_downloader_script),
            YOUTUBE_SHORT,
            "--output", str(tmp_path),
        ],
        timeout=180,
    )
    assert result.returncode == 0, (
        f"download.py exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    compressed = list(tmp_path.glob("*_compressed.mp4"))
    assert compressed, f"no _compressed.mp4 found in {tmp_path}; contents: {list(tmp_path.iterdir())}"

    out_file = compressed[0]
    # Regression assertion: v0.1.4 produced a 264-byte broken file.
    assert out_file.stat().st_size > 100_000, (
        f"v0.1.4 regression: compressed file suspiciously small ({out_file.stat().st_size} bytes)"
    )

    codecs = _ffprobe_codecs(str(out_file))
    assert codecs.get("video") == "h264", f"expected h264 video codec, got {codecs}"
    assert codecs.get("audio") == "aac", f"expected aac audio codec, got {codecs}"


@pytest.mark.live
@pytest.mark.slow
def test_no_compress_flag_skips_compression(
    python_executable, media_downloader_script, has_yt_dlp, tmp_path
):
    """--no-compress retains only the raw download; no _compressed.* file produced."""
    if not has_yt_dlp:
        pytest.skip("yt-dlp required")

    result = run_subprocess(
        [
            python_executable, str(media_downloader_script),
            YOUTUBE_SHORT,
            "--output", str(tmp_path),
            "--no-compress",
        ],
        timeout=180,
    )
    assert result.returncode == 0, (
        f"download.py --no-compress exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    compressed = list(tmp_path.glob("*_compressed*"))
    assert not compressed, f"--no-compress should not produce compressed file: {compressed}"

    raw = [p for p in tmp_path.iterdir() if p.is_file() and p.stat().st_size > 0]
    assert raw, f"no raw download file produced in {tmp_path}"
