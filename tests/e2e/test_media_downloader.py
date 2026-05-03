"""media-downloader — download + compression paths.

regression: v0.1.4 webm-source compression bug. download.py inherited the
input file's container suffix (.webm) but ffmpeg was forced to encode
libx264+aac, producing a 264-byte broken file. v0.1.4 hardcodes .mp4.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import run_subprocess, REPO_ROOT

YOUTUBE_SHORT = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # downloads as .webm by default


def _import_download_module():
    """Import plugins/media-downloader/scripts/download.py as a module.

    Avoids requiring the test runner to add the script's parent dir to PYTHONPATH.
    """
    script_path = REPO_ROOT / "plugins" / "media-downloader" / "scripts" / "download.py"
    spec = importlib.util.spec_from_file_location("media_downloader_download", script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["media_downloader_download"] = module
    spec.loader.exec_module(module)
    return module


def _ffprobe_codecs(path: str) -> dict:
    """Return {'video': codec_name, 'audio': codec_name} for the given file.

    Uses ffprobe's JSON output to avoid the line-ordering pitfall in
    `default=nw=1` mode, where `codec_name` appears before `codec_type`
    per stream and naive line-by-line parsing files each codec under the
    previous stream's type.
    """
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_streams", "-of", "json",
            path,
        ],
        capture_output=True, text=True, timeout=30,
    )
    streams = json.loads(result.stdout or "{}").get("streams", [])
    return {
        s["codec_type"]: s["codec_name"]
        for s in streams
        if "codec_type" in s and "codec_name" in s
    }


def test_compression_webm_local_fixture_produces_valid_mp4(
    zoo_webm_fixture, has_ffmpeg, has_ffprobe, tmp_path
):
    """Direct compression test using a local webm fixture — no network.

    regression: v0.1.4. Calls compress_with_ffmpeg directly so the test runs
    in CI (no YouTube download, no bot-detection block). The earlier
    YouTube-sourced compression test is retained for local manual runs but is
    @pytest.mark.youtube-marked and skipped in CI.
    """
    if not has_ffmpeg:
        pytest.skip("ffmpeg required")
    if not has_ffprobe:
        pytest.skip("ffprobe required for codec assertion")

    download = _import_download_module()
    output_path = download.compress_with_ffmpeg(str(zoo_webm_fixture), str(tmp_path))

    out_file = Path(output_path)
    assert out_file.exists(), f"compress_with_ffmpeg returned non-existent path: {output_path}"
    assert out_file.suffix == ".mp4", (
        f"v0.1.4 regression: compressed output should be .mp4, got {out_file.suffix}"
    )
    assert out_file.stat().st_size > 100_000, (
        f"v0.1.4 regression: compressed file suspiciously small ({out_file.stat().st_size} bytes)"
    )

    codecs = _ffprobe_codecs(str(out_file))
    assert codecs.get("video") == "h264", f"expected h264 video codec, got {codecs}"
    assert codecs.get("audio") == "aac", f"expected aac audio codec, got {codecs}"


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.youtube
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
@pytest.mark.youtube
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
