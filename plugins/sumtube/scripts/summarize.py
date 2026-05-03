#!/usr/bin/env python3
"""
YouTube Summarizer CLI (public plugin).

Usage:
    python summarize.py <youtube-url> [options]

Examples:
    python summarize.py "https://www.youtube.com/watch?v=jLuwLJBQkIs"
    python summarize.py "https://youtu.be/jLuwLJBQkIs" --output ./notes
    python summarize.py "https://www.youtube.com/watch?v=jLuwLJBQkIs" --compact
    python summarize.py "/path/to/local/video.mp4" --no-obsidian
"""

import argparse
import logging
import logging.handlers
import os
import shutil
import subprocess
import sys
import json
import tempfile
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).parent.parent / ".env")

from transcript import (
    detect_input_type,
    extract_video_id,
    get_transcript,
    TranscriptUnavailableError,
    GroqQuotaExhaustedError,
    INPUT_TYPE_YOUTUBE_URL,
    INPUT_TYPE_LOCAL_FILE,
    INPUT_TYPE_NON_YOUTUBE_URL,
    _whisper_fallback,
)
from summariser import summarise_transcript, _signal_scan
from output import render_note_plain

# History file tracks processed videos to avoid duplicates
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".history.json")


def _download_audio_yt_dlp(url: str) -> str:
    """Download audio from *url* to a temporary MP3 file using yt-dlp.

    Used as the first step of the YouTube Whisper fallback path when captions
    are unavailable.  The caller is responsible for deleting the returned temp
    file (a ``finally`` block in the caller should call ``os.unlink``).

    Args:
        url: A YouTube video URL.

    Returns:
        Absolute path to the temporary MP3 file.

    Raises:
        AudioExtractionError: if yt-dlp is not found or exits with a non-zero
            return code.
    """
    from transcript import AudioExtractionError

    # Locate yt-dlp without hardcoding the path.
    yt_dlp_path = shutil.which("yt-dlp") or (
        "/opt/homebrew/bin/yt-dlp"
        if os.path.isfile("/opt/homebrew/bin/yt-dlp")
        else None
    )
    if yt_dlp_path is None:
        raise AudioExtractionError(
            "yt-dlp not found. Install it with: brew install yt-dlp"
        )

    fd, temp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)

    cmd = [
        yt_dlp_path,
        "--format", "bestaudio",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "64K",
        "--no-playlist",
        "--output", temp_path,
        url,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        shell=False,
    )
    if result.returncode != 0:
        stderr_snippet = result.stderr.decode("utf-8", errors="replace")[:400]
        raise AudioExtractionError(
            f"yt-dlp exited with code {result.returncode} for URL {url!r}. "
            f"stderr: {stderr_snippet}"
        )

    return temp_path


def _download_video_yt_dlp(url: str, tmpdir: str) -> str:
    """Download a video from *url* to *tmpdir* using yt-dlp for frame extraction.

    Used by the --visual path to obtain a local video file before calling
    _extract_frames via summarise_transcript(visual_mode=True).

    Args:
        url: A YouTube video URL.
        tmpdir: Directory to write the downloaded video file.

    Returns:
        Absolute path to the downloaded video file.

    Raises:
        AudioExtractionError: if yt-dlp is not found or exits with a non-zero
            return code.
    """
    from transcript import AudioExtractionError

    yt_dlp_path = shutil.which("yt-dlp") or (
        "/opt/homebrew/bin/yt-dlp"
        if os.path.isfile("/opt/homebrew/bin/yt-dlp")
        else None
    )
    if yt_dlp_path is None:
        raise AudioExtractionError(
            "yt-dlp not found. Install it with: brew install yt-dlp"
        )

    cmd = [
        yt_dlp_path,
        "--format", "bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "--output", os.path.join(tmpdir, "%(title)s.%(ext)s"),
        "--restrict-filenames",
        "--no-playlist",
        "--print", "after_move:filepath",
        url,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        shell=False,
    )
    if result.returncode != 0:
        stderr_snippet = result.stderr.decode("utf-8", errors="replace")[:400]
        raise AudioExtractionError(
            f"yt-dlp video download exited with code {result.returncode} for URL {url!r}. "
            f"stderr: {stderr_snippet}"
        )

    local_path = result.stdout.decode("utf-8", errors="replace").strip()
    if not local_path or not os.path.isfile(local_path):
        # Fallback: find any .mp4 in tmpdir
        mp4_files = [
            os.path.join(tmpdir, f)
            for f in os.listdir(tmpdir)
            if f.endswith(".mp4") or f.endswith(".mkv")
        ]
        if not mp4_files:
            raise AudioExtractionError(
                f"yt-dlp did not produce a video file in {tmpdir!r}"
            )
        local_path = mp4_files[0]

    return local_path


def get_video_metadata(video_id: str, url: str) -> dict:
    """Retrieve basic video metadata.

    Uses the YouTube oEmbed endpoint (no API key required) to get the title
    and channel name. Falls back to video ID if the request fails.
    """
    import urllib.request

    oembed_url = (
        f"https://www.youtube.com/oembed?"
        f"url=https://www.youtube.com/watch?v={video_id}&format=json"
    )

    try:
        with urllib.request.urlopen(oembed_url, timeout=10) as response:
            data = json.loads(response.read().decode())
            return {
                "title": data.get("title", f"Video {video_id}"),
                "channel": data.get("author_name", "Unknown"),
                "url": url,
            }
    except Exception:
        return {
            "title": f"Video {video_id}",
            "channel": "Unknown",
            "url": url,
        }


def load_history() -> dict:
    """Load the processing history file."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {}


def save_history(history: dict):
    """Save the processing history file."""
    tmp_path = HISTORY_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(history, f, indent=2)
        os.fsync(f.fileno())
    os.replace(tmp_path, HISTORY_FILE)


def is_duplicate(video_id: str, mode: str, history: dict) -> bool:
    """Check if a video has already been processed in the given mode."""
    key = f"{video_id}:{mode}"
    return key in history


def record_processed(video_id: str, mode: str, title: str, output_path: str, history: dict):
    """Record a processed video in history."""
    from datetime import date
    key = f"{video_id}:{mode}"
    history[key] = {
        "video_id": video_id,
        "title": title,
        "mode": mode,
        "output": output_path,
        "date": date.today().isoformat(),
    }
    save_history(history)


def _groq_preflight_check() -> None:
    """Check Groq API availability before the first Whisper invocation.

    Calls the Groq models endpoint with a 3-second timeout as a lightweight
    availability probe.  On confirmed quota exhaustion (HTTP 429 with a
    quota-exceeded body), raises GroqQuotaExhaustedError.  All other failures
    (network errors, timeouts, unexpected responses) are caught and logged as
    warnings — they are non-blocking so that the caller can still attempt the
    Groq call directly.

    Raises:
        GroqQuotaExhaustedError: if the Groq API explicitly signals quota
            exhaustion.
    """
    import urllib.request
    import urllib.error

    groq_api_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_api_key:
        logger.warning("GROQ_API_KEY not set; skipping Groq preflight check.")
        return

    try:
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {groq_api_key}"},
        )
        with urllib.request.urlopen(req, timeout=3):
            pass
        logger.info("Groq preflight check passed.")
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        if exc.code == 429 and (
            "quota" in body.lower() or "exhausted" in body.lower() or "rate" in body.lower()
        ):
            logger.error("Groq preflight: quota exhausted (HTTP 429). body=%s", body[:200])
            raise GroqQuotaExhaustedError(
                f"Groq quota exhausted (HTTP 429): {body[:200]}"
            ) from exc
        logger.warning(
            "Groq preflight check returned HTTP %d (non-blocking): %s", exc.code, body[:200]
        )
    except Exception as exc:
        logger.warning("Groq preflight check failed (non-blocking): %s", exc)


def _maybe_offer_visual_rerun(
    transcript_text: str,
    input_source: str,
    url: str,
    input_type: str,
    transcript_data: dict,
    metadata: dict,
    api_key: str,
    args,
    output_dir: str,
) -> None:
    """Offer a visual re-run when visual signal keywords are detected in the transcript.

    Checks for 3+ visual signal keywords. If found, prompts the user interactively.
    If the user accepts, downloads the video (for YouTube URLs) and re-runs
    summarise_transcript with visual_mode=True, then writes the resulting note.

    Args:
        transcript_text: Full timestamped transcript text (used for signal scan).
        input_source: Local file path already available (may be empty string for YouTube URLs).
        url: Original URL or local path passed to process_single_url.
        input_type: One of INPUT_TYPE_YOUTUBE_URL, INPUT_TYPE_LOCAL_FILE, INPUT_TYPE_NON_YOUTUBE_URL.
        transcript_data: Full transcript dict from get_transcript / _whisper_fallback.
        metadata: Video metadata dict with title, channel, url keys.
        api_key: Anthropic API key.
        args: Parsed CLI args namespace.
        output_dir: Output directory for the generated note.
    """
    signal_count = _signal_scan(transcript_text)
    if signal_count < 3:
        return

    print(f"\nVisual signals detected in this video ({signal_count} keywords found).")
    print(
        "Would you like a visual summary using frame extraction? "
        "This uses claude-sonnet-4-6 and will increase token cost."
    )
    try:
        user_choice = input("Re-run with visual summary? [y/N]: ").strip()
    except EOFError:
        user_choice = ""
    if user_choice not in ("y", "Y"):
        return

    offer_local_path = input_source
    offer_visual_tmpdir: str | None = None
    if not offer_local_path and input_type == INPUT_TYPE_YOUTUBE_URL:
        print("Downloading video for visual re-summarisation...")
        offer_visual_tmpdir = tempfile.mkdtemp()
        try:
            offer_local_path = _download_video_yt_dlp(url, offer_visual_tmpdir)
            print(f"Video downloaded to: {offer_local_path}")
        except Exception as dl_err:
            print(f"Error downloading video for visual mode: {dl_err}", file=sys.stderr)
            if offer_visual_tmpdir is not None:
                shutil.rmtree(offer_visual_tmpdir, ignore_errors=True)
            return

    if not offer_local_path:
        return

    try:
        print("Summarising with claude-sonnet-4-6 (visual mode)...")
        visual_summary = summarise_transcript(
            transcript_data,
            metadata,
            api_key,
            model=args.model,
            max_chunk_words=args.max_chunk_words,
            compact=args.compact,
            visual_mode=True,
            input_source=offer_local_path,
        )
        print(f"Writing visual note to {output_dir}...")
        visual_filepath = render_note_plain(
            visual_summary, metadata, output_dir, compact=args.compact
        )
        print(f"Visual summary saved to: {visual_filepath}")
    except Exception as vis_err:
        print(f"Error during visual summarisation: {vis_err}", file=sys.stderr)
    finally:
        if offer_visual_tmpdir is not None:
            shutil.rmtree(offer_visual_tmpdir, ignore_errors=True)


def process_single_url(url: str, args, api_key: str, output_dir: str, history: dict) -> bool:
    """Process a single URL or local file path. Returns True on success, False on failure."""
    # Step 1: Classify input type before any other processing.
    try:
        input_type = detect_input_type(url)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return False

    # Non-YouTube URLs: direct yt-dlp invocation (no state file routing).
    if input_type == INPUT_TYPE_NON_YOUTUBE_URL:
        print("Non-YouTube URL detected — downloading audio via yt-dlp...")
        if os.environ.get("GROQ_API_KEY"):
            _groq_preflight_check()
        temp_audio_path: str | None = None
        try:
            temp_audio_path = _download_audio_yt_dlp(url)
            transcript_data = _whisper_fallback(temp_audio_path)
        except GroqQuotaExhaustedError as exc:
            print(f"Groq quota exhausted: {exc}", file=sys.stderr)
            return False
        except Exception as exc:
            print(f"Error during audio download/transcription: {exc}", file=sys.stderr)
            return False
        finally:
            if temp_audio_path is not None and os.path.exists(temp_audio_path):
                try:
                    os.unlink(temp_audio_path)
                except OSError as unlink_err:
                    logger.warning(
                        "Failed to delete yt-dlp temp audio %r: %s",
                        temp_audio_path, unlink_err,
                    )

        metadata = {
            "title": url.split("/")[-1] or "video",
            "channel": "Unknown",
            "url": url,
        }
        print(f"Transcript: {transcript_data['word_count']} words, language: {transcript_data['language']}")

        if args.transcript_only:
            print("\n--- Transcript (with timestamps) ---\n")
            print(transcript_data["timestamped_text"])
            return True

        mode_label = "compact" if args.compact else "full"
        try:
            if getattr(args, "visual", False):
                summary = summarise_transcript(
                    transcript_data, metadata, api_key,
                    model=args.model, max_chunk_words=args.max_chunk_words,
                    compact=args.compact, visual_mode=True, input_source="",
                )
            else:
                summary = summarise_transcript(
                    transcript_data, metadata, api_key,
                    model=args.model, max_chunk_words=args.max_chunk_words,
                    compact=args.compact,
                )
            note_path = render_note_plain(summary, metadata, output_dir, compact=args.compact)
            print(f"Done. Note saved to: {note_path}")
            if not getattr(args, "visual", False):
                _maybe_offer_visual_rerun(
                    transcript_text=transcript_data.get("timestamped_text", ""),
                    input_source="",
                    url=url,
                    input_type=input_type,
                    transcript_data=transcript_data,
                    metadata=metadata,
                    api_key=api_key,
                    args=args,
                    output_dir=output_dir,
                )
        except Exception as exc:
            print(f"Error summarising: {exc}", file=sys.stderr)
            return False
        return True

    mode_label = "compact" if args.compact else "full"

    # Step 1b: Local file path — bypass YouTube-specific steps entirely.
    if input_type == INPUT_TYPE_LOCAL_FILE:
        if os.environ.get("GROQ_API_KEY"):
            _groq_preflight_check()
        print("Extracting transcript via Whisper (local file)...")
        try:
            transcript_data = _whisper_fallback(url)
        except Exception as e:
            print(f"Error during Whisper transcription: {e}", file=sys.stderr)
            return False

        # Synthesise metadata from the filename.
        file_stem = Path(url).stem
        metadata = {
            "title": file_stem,
            "channel": "Local File",
            "url": url,
        }
        print(f"Title (from filename): {metadata['title']}")
        print(f"Transcript: {transcript_data['word_count']} words, language: {transcript_data['language']}")

        if args.transcript_only:
            print("\n--- Transcript (with timestamps) ---\n")
            print(transcript_data["timestamped_text"])
            return True

        # Fall through to shared summarise + render block below.
        video_id = file_stem

    else:
        # Step 1c: YouTube URL — existing flow.
        assert input_type == INPUT_TYPE_YOUTUBE_URL

        try:
            video_id = extract_video_id(url)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return False

        print(f"\nVideo ID: {video_id}")

        # Step 2: Duplicate check.
        if not args.force and is_duplicate(video_id, mode_label, history):
            existing = history[f"{video_id}:{mode_label}"]
            print(f"Skipped (already processed on {existing['date']}): {existing['title']}")
            print(f"  Output: {existing['output']}")
            print(f"  Use --force to re-process.")
            return True

        # Step 3: Get video metadata.
        print("Fetching video metadata...")
        metadata = get_video_metadata(video_id, url)
        print(f"Title: {metadata['title']}")
        print(f"Channel: {metadata['channel']}")

        # Step 4: Get transcript; attempt Whisper fallback if captions unavailable.
        if os.environ.get("GROQ_API_KEY"):
            _groq_preflight_check()
        print("Extracting transcript...")
        try:
            transcript_data = get_transcript(video_id)
        except TranscriptUnavailableError as e:
            # YouTube captions unavailable — attempt Whisper fallback via yt-dlp.
            print(
                "YouTube transcript unavailable — attempting Whisper fallback "
                "via yt-dlp audio download..."
            )
            temp_audio_path: str | None = None
            try:
                temp_audio_path = _download_audio_yt_dlp(url)
                transcript_data = _whisper_fallback(temp_audio_path)
            except Exception as fallback_exc:
                print(
                    f"Whisper fallback failed: {fallback_exc}",
                    file=sys.stderr,
                )
                return False
            finally:
                if temp_audio_path is not None and os.path.exists(temp_audio_path):
                    try:
                        os.unlink(temp_audio_path)
                    except OSError as unlink_err:
                        logger.warning(
                            "Failed to delete yt-dlp temp audio %r: %s",
                            temp_audio_path, unlink_err,
                        )

        print(f"Transcript: {transcript_data['word_count']} words, language: {transcript_data['language']}")

        if args.transcript_only:
            print("\n--- Transcript (with timestamps) ---\n")
            print(transcript_data["timestamped_text"])
            return True

    # -----------------------------------------------------------------------
    # Shared: summarise → render — runs for both youtube_url and local_file.
    # -----------------------------------------------------------------------

    # Determine local_path for visual mode.
    # For local file inputs, the path is already the local file.
    # For YouTube URLs with --visual, we need to download the video.
    local_path: str = ""
    visual_tmpdir: str | None = None

    if args.visual:
        if input_type == INPUT_TYPE_YOUTUBE_URL:
            print("Downloading video for frame extraction (--visual)...")
            visual_tmpdir = tempfile.mkdtemp()
            try:
                local_path = _download_video_yt_dlp(url, visual_tmpdir)
                print(f"Video downloaded to: {local_path}")
            except Exception as dl_err:
                print(f"Error downloading video for visual mode: {dl_err}", file=sys.stderr)
                if visual_tmpdir is not None:
                    shutil.rmtree(visual_tmpdir, ignore_errors=True)
                    visual_tmpdir = None
                # --visual was explicitly requested; do not silently degrade to text-only.
                return False
        elif input_type == INPUT_TYPE_LOCAL_FILE:
            local_path = url  # url holds the local path in this branch

    # Step 5: Summarise.
    try:
        if args.visual:
            print(f"Summarising with claude-sonnet-4-6 (visual mode)...")
            summary = summarise_transcript(
                transcript_data,
                metadata,
                api_key,
                model=args.model,
                max_chunk_words=args.max_chunk_words,
                compact=args.compact,
                visual_mode=True,
                input_source=local_path,
            )
        else:
            print(f"Summarising with {args.model} ({mode_label} mode)...")
            summary = summarise_transcript(
                transcript_data,
                metadata,
                api_key,
                model=args.model,
                max_chunk_words=args.max_chunk_words,
                compact=args.compact,
                visual_mode=False,
                input_source=local_path,
            )
    except ValueError as e:
        print(f"Error parsing LLM response: {e}", file=sys.stderr)
        if visual_tmpdir is not None:
            shutil.rmtree(visual_tmpdir, ignore_errors=True)
        return False
    except Exception as e:
        print(f"Error during summarisation: {e}", file=sys.stderr)
        if visual_tmpdir is not None:
            shutil.rmtree(visual_tmpdir, ignore_errors=True)
        return False

    # Step 6: Write output — always plain markdown in the public plugin.
    print(f"Writing note to {output_dir}...")
    filepath = render_note_plain(summary, metadata, output_dir, compact=args.compact)
    print(f"Done. Note saved to: {filepath}")

    # Step 7: Record in history.
    record_processed(video_id, mode_label, metadata["title"], filepath, history)

    # Step 8: Post-delivery visual offer (only when --visual was NOT already used).
    if not args.visual:
        full_transcript_text = transcript_data.get("timestamped_text", "")
        _maybe_offer_visual_rerun(
            transcript_text=full_transcript_text,
            input_source=local_path,
            url=url,
            input_type=input_type,
            transcript_data=transcript_data,
            metadata=metadata,
            api_key=api_key,
            args=args,
            output_dir=output_dir,
        )

    # Clean up visual download tmpdir if used in main path.
    if visual_tmpdir is not None:
        shutil.rmtree(visual_tmpdir, ignore_errors=True)

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Summarise YouTube videos into plain markdown notes."
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="YouTube video URL or local video file path.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=".",
        help=(
            "Output directory for the generated notes. "
            "Defaults to the current directory."
        ),
    )
    parser.add_argument(
        "--model",
        "-m",
        default="claude-haiku-4-5-20251001",
        help="Claude model to use (default: claude-haiku-4-5-20251001)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Anthropic API key. Lookup order: --api-key flag → SUMTUBE_API_KEY → ANTHROPIC_API_KEY (also loads from .env in plugin root).",
    )
    parser.add_argument(
        "--max-chunk-words",
        type=int,
        default=4000,
        help="Max words per chunk for long transcripts (default: 4000)",
    )
    parser.add_argument(
        "--compact",
        "-c",
        action="store_true",
        help="Produce a shorter note: max 5 key concepts, 2-paragraph summary, 3 takeaways.",
    )
    parser.add_argument(
        "--transcript-only",
        action="store_true",
        help="Extract and print the transcript without summarising. Useful for debugging.",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force re-processing even if the video was already summarised.",
    )
    parser.add_argument(
        "--no-obsidian",
        action="store_true",
        dest="no_obsidian",
        help=(
            "Output plain markdown (no YAML frontmatter, no [[wikilink]] syntax). "
            "This flag is accepted for compatibility but has no effect — "
            "the public plugin always outputs plain markdown."
        ),
    )
    parser.add_argument(
        "--visual",
        action="store_true",
        help=(
            "Enable visual summarisation via frame extraction. "
            "For YouTube URLs: auto-downloads the video via yt-dlp before extracting frames. "
            "Uses claude-sonnet-4-6 for the visual pass (higher token cost). "
            "A post-delivery offer also fires automatically when 3+ visual signal keywords "
            "are detected in the transcript, even without this flag."
        ),
    )

    args = parser.parse_args()

    # Validate input
    if not args.url:
        parser.error("Provide a YouTube URL or local video file path.")

    # Configure structured logging — RotatingFileHandler + stderr StreamHandler
    _log_fmt = "[%(asctime)s] [%(source_type)s] [%(api)s] [%(outcome)s] [%(detail)s]"
    _date_fmt = "%Y-%m-%dT%H:%M:%S"
    _log_default_factory = logging.getLogRecordFactory()

    def _log_record_factory(*fargs, **fkwargs):
        record = _log_default_factory(*fargs, **fkwargs)
        if not hasattr(record, "source_type"):
            record.source_type = "-"
        if not hasattr(record, "api"):
            record.api = "-"
        if not hasattr(record, "outcome"):
            record.outcome = "-"
        if not hasattr(record, "detail"):
            record.detail = record.getMessage() if record.args else record.msg
        return record

    logging.setLogRecordFactory(_log_record_factory)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(_log_fmt, datefmt=_date_fmt))
    root_logger.addHandler(stderr_handler)

    log_file_path = os.environ.get(
        "SUMTUBE_LOG_FILE",
        "./sumtube-run.log",
    )
    try:
        log_dir = os.path.dirname(os.path.abspath(log_file_path))
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path,
            maxBytes=1_048_576,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter(_log_fmt, datefmt=_date_fmt))
        root_logger.addHandler(file_handler)
    except OSError as log_err:
        logger.warning("Could not open log file %r (non-blocking): %s", log_file_path, log_err)

    # Resolve API key
    api_key = args.api_key or os.environ.get("SUMTUBE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key and not args.transcript_only:
        print("Error: No API key provided.", file=sys.stderr)
        print(
            "Set ANTHROPIC_API_KEY environment variable or pass --api-key.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Resolve output directory
    output_dir = args.output

    # Load history
    history = load_history()

    if process_single_url(args.url, args, api_key, output_dir, history):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
