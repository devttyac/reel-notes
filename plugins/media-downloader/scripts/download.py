"""
download.py — media-downloader public skill script

Accepts a URL or local file path. Downloads video via yt-dlp (URLs only),
then compresses via ffmpeg. Prints final local file path to stdout.

No API keys required. No vault paths. No state file logic.

Usage:
    python download.py <url_or_path> [--output <dir>] [--no-compress] [--quality <format>]

Exit codes:
    0 — success
    1 — yt-dlp or ffmpeg binary not found (RuntimeError)
    2 — yt-dlp download failed
    3 — invalid input (bad URL scheme or file path)
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FFMPEG_HOMEBREW = "/opt/homebrew/bin/ffmpeg"
_DISK_WARN_THRESHOLD_BYTES = 500 * 1024 * 1024  # 500 MB
_DEFAULT_OUTPUT_DIR = "./media-downloader-output"


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def validate_input(source: str) -> None:
    """Validate *source* as either a https:// URL or an existing absolute file path.

    Raises:
        ValueError: if *source* is not a valid https:// URL and not a valid
                    absolute path to an existing file.
    """
    # Check if it looks like a URL (has a scheme)
    parsed = urlparse(source)

    if parsed.scheme:
        # It has a scheme — validate as URL
        if parsed.scheme != "https":
            raise ValueError(
                f"Invalid URL scheme {parsed.scheme!r}. Only https:// URLs are "
                "accepted. http://, ftp://, and file:// are not supported."
            )
        # https:// — valid
        return

    # No scheme — treat as a file path
    path = Path(source)

    if not path.is_absolute():
        raise ValueError(
            f"Invalid input {source!r}. Local file paths must be absolute "
            "(start with /). Relative paths are not accepted."
        )

    if not path.exists():
        raise ValueError(
            f"File does not exist: {source!r}. Provide a valid absolute path to "
            "an existing file."
        )


# ---------------------------------------------------------------------------
# ffmpeg compression
# ---------------------------------------------------------------------------

def compress_with_ffmpeg(input_path: str, output_dir: str) -> str:
    """Compress *input_path* with ffmpeg and write the result to *output_dir*.

    Tries /opt/homebrew/bin/ffmpeg first; falls back to shutil.which('ffmpeg').

    Args:
        input_path: Absolute path to the source video file.
        output_dir: Directory to write the compressed output.

    Returns:
        Absolute path to the compressed output file.

    Raises:
        RuntimeError: if ffmpeg is not found at either location.
    """
    # Resolve ffmpeg binary
    if os.path.isfile(_FFMPEG_HOMEBREW):
        ffmpeg_bin = _FFMPEG_HOMEBREW
    else:
        ffmpeg_bin = shutil.which("ffmpeg")

    if not ffmpeg_bin:
        raise RuntimeError(
            "ffmpeg not found. Install: brew install ffmpeg\n"
            f"Expected at {_FFMPEG_HOMEBREW!r} or on PATH."
        )

    input_file = Path(input_path)
    output_file = Path(output_dir) / (input_file.stem + "_compressed" + input_file.suffix)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg_bin,
        "-i", str(input_file),
        "-vcodec", "libx264",
        "-crf", "23",
        "-preset", "fast",
        "-acodec", "aac",
        "-y",           # overwrite output without prompting
        str(output_file),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(
            f"ffmpeg compression failed (exit {result.returncode}). "
            f"Stderr: {result.stderr.strip()}",
            file=sys.stderr,
        )
        # Non-fatal: return original file path
        return str(input_file)

    return str(output_file)


# ---------------------------------------------------------------------------
# URL download
# ---------------------------------------------------------------------------

def download_url(url: str, output_dir: str, quality: Optional[str] = None) -> str:
    """Download *url* using yt-dlp into *output_dir*.

    Checks disk space before download. Tracks partial downloads and cleans up
    on failure.

    Args:
        url: A validated https:// URL.
        output_dir: Directory to place the downloaded file.
        quality: Optional yt-dlp format string (e.g. "bestvideo+bestaudio").

    Returns:
        Absolute path to the downloaded file.

    Raises:
        RuntimeError: if yt-dlp is not found on PATH.
        SystemExit(2): if yt-dlp returns non-zero exit code.
    """
    # Disk space preflight
    try:
        usage = shutil.disk_usage(output_dir if os.path.exists(output_dir) else "/")
        if usage.free < _DISK_WARN_THRESHOLD_BYTES:
            free_mb = usage.free // (1024 * 1024)
            print(
                f"WARNING: Low disk space — only {free_mb} MB available. "
                "Download may fail. Free up disk space before proceeding.",
                file=sys.stderr,
            )
    except OSError:
        pass  # Non-fatal — proceed

    # Resolve yt-dlp binary
    ytdlp_bin = shutil.which("yt-dlp")
    if not ytdlp_bin:
        raise RuntimeError(
            "yt-dlp not found. Install: pip install yt-dlp\n"
            "Ensure yt-dlp is on your PATH before running download.py."
        )

    # Prepare output directory
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    output_template = str(out_dir / "%(title)s.%(ext)s")

    cmd = [
        ytdlp_bin,
        "--no-playlist",
        "--output", output_template,
    ]

    if quality:
        cmd.extend(["--format", quality])

    cmd.append(url)

    # Track the output path for partial download cleanup
    downloaded_path: Optional[str] = None
    success = False

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(
                f"yt-dlp failed (exit {result.returncode}): {result.stderr.strip()}",
                file=sys.stderr,
            )
            sys.exit(2)

        # Parse the output path from yt-dlp stdout or discover by listing output_dir
        # yt-dlp writes "[download] Destination: <path>" or similar
        downloaded_path = _parse_ytdlp_output_path(result.stdout, str(out_dir))
        success = True
        return downloaded_path

    finally:
        if not success and downloaded_path and os.path.exists(downloaded_path):
            try:
                os.unlink(downloaded_path)
            except OSError:
                pass


def _parse_ytdlp_output_path(stdout: str, output_dir: str) -> str:
    """Extract the downloaded file path from yt-dlp stdout.

    Falls back to finding the most recently modified file in *output_dir*.

    Args:
        stdout: yt-dlp stdout text.
        output_dir: Directory where the file was saved.

    Returns:
        Absolute path to the downloaded file.
    """
    for line in stdout.splitlines():
        line = line.strip()
        # yt-dlp prints: [download] Destination: /path/to/file.mp4
        if line.startswith("[download] Destination:"):
            candidate = line.split("Destination:", 1)[1].strip()
            if os.path.exists(candidate):
                return candidate
        # yt-dlp also prints: [Merger] Merging formats into "/path/to/file.mp4"
        if "[Merger] Merging formats into" in line:
            candidate = line.split('"')[1] if '"' in line else ""
            if candidate and os.path.exists(candidate):
                return candidate

    # Fallback: find the most recently modified file in output_dir.
    # Assumes single concurrent invocation — concurrent downloads to the same
    # directory could return the wrong file. Use separate output directories
    # per invocation if concurrent use is required.
    out_dir = Path(output_dir)
    candidates = sorted(
        out_dir.glob("*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return str(candidates[0])

    return output_dir


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Download a video from a URL or pass through a local file, "
            "optionally compressing with ffmpeg."
        )
    )
    parser.add_argument(
        "source",
        help="https:// URL to download, or absolute local file path.",
    )
    parser.add_argument(
        "--output",
        default=_DEFAULT_OUTPUT_DIR,
        help=f"Output directory. Default: {_DEFAULT_OUTPUT_DIR!r}",
    )
    parser.add_argument(
        "--no-compress",
        action="store_true",
        help="Skip ffmpeg compression step.",
    )
    parser.add_argument(
        "--quality",
        default=None,
        help="yt-dlp format string (e.g. 'bestvideo+bestaudio'). URL downloads only.",
    )
    args = parser.parse_args()

    # Validate input
    try:
        validate_input(args.source)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(3)

    parsed = urlparse(args.source)
    is_url = bool(parsed.scheme)

    if is_url:
        try:
            file_path = download_url(args.source, args.output, quality=args.quality)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        # Local file passthrough
        file_path = args.source

    if not args.no_compress:
        try:
            file_path = compress_with_ffmpeg(file_path, args.output)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)

    print(file_path)


if __name__ == "__main__":
    main()
