"""
Transcript extraction module.

Retrieves YouTube video transcripts with timestamps using youtube-transcript-api v1.2+.
Handles missing captions, language fallback, and long-video chunking.

Input type classification
-------------------------
detect_input_type(input_str) classifies a raw input string into one of three constants:

- INPUT_TYPE_YOUTUBE_URL  ('youtube_url')
  Any http:// or https:// URL whose host contains 'youtube.com' or 'youtu.be'.

- INPUT_TYPE_LOCAL_FILE   ('local_file')
  An absolute path that exists on disk as a regular file with a supported video
  extension (.mp4, .mov, .mkv, .webm, case-insensitive).

- INPUT_TYPE_NON_YOUTUBE_URL ('non_youtube_url')
  Any http:// or https:// URL that is NOT a YouTube URL.
"""

import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Input type constants
# ---------------------------------------------------------------------------
INPUT_TYPE_YOUTUBE_URL: str = "youtube_url"
INPUT_TYPE_LOCAL_FILE: str = "local_file"
INPUT_TYPE_NON_YOUTUBE_URL: str = "non_youtube_url"

_SUPPORTED_VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {".mp4", ".mov", ".mkv", ".webm"}
)

_AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".aac", ".opus"}
)

_FFMPEG_PATH: str = "/opt/homebrew/bin/ffmpeg"
_MAX_AUDIO_BYTES: int = 26_214_400  # 25 MB
# Characters that have special meaning in shells and must never appear in paths
# passed to subprocess (defence-in-depth on top of list-form invocation).
_SHELL_METACHARACTERS: str = ";|&$()<>`\x00"


def detect_input_type(input_str: str) -> str:
    """Classify *input_str* as a YouTube URL, local file path, or non-YouTube URL.

    Args:
        input_str: Raw input string from the caller.

    Returns:
        One of the module-level constants:
        - ``INPUT_TYPE_YOUTUBE_URL``    ('youtube_url')
        - ``INPUT_TYPE_LOCAL_FILE``     ('local_file')
        - ``INPUT_TYPE_NON_YOUTUBE_URL`` ('non_youtube_url')

    Raises:
        ValueError: For inputs that look like a local path but fail validation
            (relative path, file not found, unsupported extension, path is a
            directory), and for any input that matches no recognised pattern
            (bare strings, ``file://`` URLs, FTP URLs, etc.).
    """
    if not input_str:
        raise ValueError("Input string must not be empty.")

    # --- HTTP / HTTPS URL branch ---
    if input_str.startswith("http://") or input_str.startswith("https://"):
        if "youtube.com" in input_str or "youtu.be" in input_str:
            return INPUT_TYPE_YOUTUBE_URL
        return INPUT_TYPE_NON_YOUTUBE_URL

    # --- Local file path branch ---
    # Treat the input as a potential file path when it is not an HTTP(S) URL.
    p = Path(input_str)

    if not p.is_absolute():
        raise ValueError(
            f"Local file path must be an absolute path. Got: {input_str!r}"
        )

    if not p.exists():
        raise ValueError(
            f"Local file does not exist: {input_str!r}"
        )

    if not p.is_file():
        raise ValueError(
            f"Path exists but is not a regular file: {input_str!r}"
        )

    suffix = p.suffix.lower()
    if suffix not in _SUPPORTED_VIDEO_EXTENSIONS:
        raise ValueError(
            f"Unsupported file extension {p.suffix!r}. "
            f"Supported extensions: {sorted(_SUPPORTED_VIDEO_EXTENSIONS)}"
        )

    return INPUT_TYPE_LOCAL_FILE


def extract_video_id(url: str) -> str:
    """Extract the video ID from a YouTube URL.

    Supports standard, shortened, and embed URL formats.
    Raises ValueError if no valid ID is found.
    """
    patterns = [
        r"(?:v=|/v/)([a-zA-Z0-9_-]{11})",
        r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from URL: {url}")


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS or MM:SS format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def get_transcript(
    video_id: str,
    languages: list[str] | None = None,
    _fallback_source: str | None = None,
) -> dict:
    """Retrieve the transcript for a YouTube video.

    Uses youtube-transcript-api v1.2+ instance-based API.

    Args:
        video_id: The YouTube video ID.
        languages: Preferred languages in order. Defaults to ["en"].

    Returns:
        dict with keys:
            - "segments": list of dicts with "start", "duration", "text", "timestamp"
            - "full_text": concatenated plain text
            - "timestamped_text": text with inline timestamps at segment boundaries
            - "language": the language code of the transcript retrieved
            - "word_count": approximate word count of the full transcript

    Args:
        video_id: The YouTube video ID.
        languages: Preferred languages in order. Defaults to ["en"].
        _fallback_source: Optional absolute path to a local video file.  When
            provided and YouTube captions are unavailable, ``_whisper_fallback``
            is invoked on this path instead of raising
            ``TranscriptUnavailableError``.

    Raises:
        TranscriptUnavailableError: if no transcript can be retrieved and no
            *_fallback_source* was provided (or the fallback itself fails).
    """
    if languages is None:
        languages = ["en"]

    try:
        ytt_api = YouTubeTranscriptApi()

        # First, try listing transcripts to find the best match
        try:
            transcript_list = ytt_api.list(video_id)
        except Exception as e:
            raise TranscriptUnavailableError(
                f"Transcript unavailable for video {video_id}: {e}"
            ) from e

        # Try to find a manually created transcript first, then auto-generated
        fetched = None
        lang_used = None

        for lang in languages:
            try:
                transcript = transcript_list.find_manually_created_transcript([lang])
                fetched = transcript.fetch()
                lang_used = lang
                break
            except Exception:
                pass

        if fetched is None:
            for lang in languages:
                try:
                    transcript = transcript_list.find_generated_transcript([lang])
                    fetched = transcript.fetch()
                    lang_used = lang
                    break
                except Exception:
                    pass

        # Fallback: fetch directly without language preference
        if fetched is None:
            try:
                fetched = ytt_api.fetch(video_id, languages=languages)
                lang_used = languages[0]
            except Exception as e:
                raise TranscriptUnavailableError(
                    f"No transcript found for video {video_id} in languages: {languages}. Error: {e}"
                ) from e

        # Convert FetchedTranscript to raw data (list of dicts)
        if hasattr(fetched, "to_raw_data"):
            raw_segments = fetched.to_raw_data()
        elif isinstance(fetched, list):
            raw_segments = fetched
        else:
            # Iterate over the FetchedTranscript object directly
            raw_segments = list(fetched)

        # Process segments
        segments = []
        full_text_parts = []
        timestamped_parts = []

        for seg in raw_segments:
            # Handle both dict-style and attribute-style access
            if isinstance(seg, dict):
                start = seg.get("start", 0)
                duration = seg.get("duration", 0)
                text = seg.get("text", "").strip()
            else:
                start = getattr(seg, "start", 0)
                duration = getattr(seg, "duration", 0)
                text = getattr(seg, "text", "").strip()

            if not text:
                continue

            timestamp = format_timestamp(start)
            segments.append(
                {
                    "start": start,
                    "duration": duration,
                    "text": text,
                    "timestamp": timestamp,
                }
            )
            full_text_parts.append(text)
            timestamped_parts.append(f"[{timestamp}] {text}")

        full_text = " ".join(full_text_parts)
        word_count = len(full_text.split())

        return {
            "segments": segments,
            "full_text": full_text,
            "timestamped_text": "\n".join(timestamped_parts),
            "language": lang_used,
            "word_count": word_count,
        }

    except TranscriptUnavailableError:
        if _fallback_source is not None:
            logger.info(
                "YouTube captions unavailable for %r; routing to Whisper fallback.",
                video_id,
            )
            return _whisper_fallback(_fallback_source)
        raise


def chunk_transcript(
    segments: list[dict], max_words: int = 4000, overlap_words: int = 200
) -> list[dict]:
    """Split a transcript into overlapping chunks for long videos.

    Each chunk contains segments totalling approximately max_words,
    with overlap_words of overlap between consecutive chunks.

    Args:
        segments: list of transcript segments from get_transcript().
        max_words: target word count per chunk.
        overlap_words: word overlap between consecutive chunks.

    Returns:
        list of dicts, each with:
            - "segments": the segments in this chunk
            - "text": concatenated text
            - "timestamped_text": text with timestamps
            - "start_time": timestamp of first segment
            - "end_time": timestamp of last segment
            - "word_count": word count of the chunk
    """
    if not segments:
        return []

    total_words = sum(len(s["text"].split()) for s in segments)
    if total_words <= max_words:
        return [
            {
                "segments": segments,
                "text": " ".join(s["text"] for s in segments),
                "timestamped_text": "\n".join(
                    f"[{s['timestamp']}] {s['text']}" for s in segments
                ),
                "start_time": segments[0]["timestamp"],
                "end_time": segments[-1]["timestamp"],
                "word_count": total_words,
            }
        ]

    chunks = []
    current_start = 0

    while current_start < len(segments):
        current_words = 0
        current_end = current_start

        while current_end < len(segments) and current_words < max_words:
            current_words += len(segments[current_end]["text"].split())
            current_end += 1

        chunk_segments = segments[current_start:current_end]
        chunks.append(
            {
                "segments": chunk_segments,
                "text": " ".join(s["text"] for s in chunk_segments),
                "timestamped_text": "\n".join(
                    f"[{s['timestamp']}] {s['text']}" for s in chunk_segments
                ),
                "start_time": chunk_segments[0]["timestamp"],
                "end_time": chunk_segments[-1]["timestamp"],
                "word_count": sum(
                    len(s["text"].split()) for s in chunk_segments
                ),
            }
        )

        # Move start back by overlap amount for next chunk
        overlap_count = 0
        next_start = current_end
        while next_start > current_start and overlap_count < overlap_words:
            next_start -= 1
            overlap_count += len(segments[next_start]["text"].split())

        current_start = max(next_start, current_start + 1)

    return chunks


class TranscriptUnavailableError(Exception):
    """Raised when a transcript cannot be retrieved for a video."""

    pass


class AudioFileTooLargeError(Exception):
    """Raised when the extracted audio file exceeds the Groq upload limit (25 MB)."""

    pass


class GroqQuotaExhaustedError(Exception):
    """Raised when the Groq API returns a quota-exhausted / rate-limit error."""

    pass


class AudioExtractionError(Exception):
    """Raised when ffmpeg fails to extract audio from the input file."""

    pass


class MissingAPIKeyError(Exception):
    """Raised when GROQ_API_KEY is not set in the environment at invocation time."""

    pass


# ---------------------------------------------------------------------------
# Private helpers — audio extraction and Whisper fallback
# ---------------------------------------------------------------------------

def _validate_input_path(input_path: str) -> None:
    """Validate *input_path* before passing it to ffmpeg.

    Raises:
        ValueError: if the path contains ``../``, ``//``, shell metacharacters,
            null bytes, or an unsupported file extension.
    """
    if "../" in input_path:
        raise ValueError(
            f"Path traversal sequence '../' is not allowed in input path: {input_path!r}"
        )
    if "//" in input_path:
        raise ValueError(
            f"Double-slash '//' is not allowed in input path: {input_path!r}"
        )
    for char in _SHELL_METACHARACTERS:
        if char in input_path:
            raise ValueError(
                f"Invalid character {char!r} (shell metacharacter or null byte) "
                f"in input path: {input_path!r}"
            )
    suffix = Path(input_path).suffix.lower()
    if suffix not in _SUPPORTED_VIDEO_EXTENSIONS:
        raise ValueError(
            f"Unsupported file extension {Path(input_path).suffix!r}. "
            f"Supported extensions: {sorted(_SUPPORTED_VIDEO_EXTENSIONS)}"
        )


def _extract_audio(input_path: str) -> str:
    """Extract audio from *input_path* to a temporary MP3 file using ffmpeg.

    Args:
        input_path: Absolute path to a local video file with a supported
            extension (.mp4, .mov, .mkv, .webm).

    Returns:
        The absolute path to the temporary MP3 file.  The caller is
        responsible for deleting this file when done.

    Raises:
        ValueError: if *input_path* contains unsafe characters or an
            unsupported extension.
        FileNotFoundError: if the ffmpeg binary is not found at
            ``/opt/homebrew/bin/ffmpeg``.
        AudioExtractionError: if ffmpeg exits with a non-zero return code.
        AudioFileTooLargeError: if the extracted audio exceeds 25 MB.
    """
    _validate_input_path(input_path)
    input_path = os.path.realpath(input_path)

    if not os.path.isfile(_FFMPEG_PATH):
        raise FileNotFoundError(
            f"ffmpeg binary not found at {_FFMPEG_PATH!r}. "
            "Install Homebrew ffmpeg: brew install ffmpeg"
        )

    fd, temp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)  # Release the fd immediately; ffmpeg opens the path itself.

    try:
        try:
            subprocess.run(
                [
                    _FFMPEG_PATH,
                    "-y",
                    "-i", input_path,
                    "-ac", "1",
                    "-b:a", "64k",
                    "-f", "mp3",
                    temp_path,
                ],
                check=True,
                shell=False,
            )
        except subprocess.CalledProcessError as exc:
            raise AudioExtractionError(
                f"ffmpeg failed with exit code {exc.returncode} for input: {input_path!r}"
            ) from exc

        file_size = os.path.getsize(temp_path)
        if file_size > _MAX_AUDIO_BYTES:
            raise AudioFileTooLargeError(
                f"Extracted audio is {file_size:,} bytes, which exceeds the "
                f"25 MB Groq upload limit ({_MAX_AUDIO_BYTES:,} bytes)."
            )

        return temp_path

    except Exception:
        try:
            os.unlink(temp_path)
        except OSError as unlink_err:
            logger.warning(
                "Failed to delete temp audio file %r: %s", temp_path, unlink_err
            )
        raise


def _whisper_fallback(input_source: str) -> dict:
    """Transcribe *input_source* via Groq Whisper when YouTube captions are unavailable.

    Args:
        input_source: Absolute path to a local video file that ``_extract_audio``
            can process.

    Returns:
        dict with keys:
            - ``segments``: list of segment dicts (``start``, ``end``, ``text``,
              ``timestamp``)
            - ``full_text``: concatenated plain text of all segments
            - ``timestamped_text``: newline-joined ``[HH:MM:SS] text`` lines
            - ``language``: language code detected by Whisper
            - ``word_count``: integer word count of ``full_text``

    Raises:
        MissingAPIKeyError: if ``GROQ_API_KEY`` is not set in the environment.
        AudioFileTooLargeError: if the extracted audio exceeds 25 MB.
        AudioExtractionError: if ffmpeg fails.
    """
    if not os.environ.get("GROQ_API_KEY"):
        raise MissingAPIKeyError(
            "GROQ_API_KEY environment variable is not set. "
            "Set it before invoking the Whisper fallback."
        )

    # Lazy import — groq is an optional dependency; only load when needed.
    from groq import Groq  # noqa: PLC0415

    ext = os.path.splitext(input_source)[1].lower()
    if ext in _AUDIO_EXTENSIONS:
        # Already extracted audio — pass directly to Groq, skip ffmpeg.
        # The caller owns the file and is responsible for cleanup.
        temp_path = input_source
        _owns_temp = False
    else:
        # Video file — extract audio first; we own the resulting temp file.
        temp_path = _extract_audio(input_source)
        _owns_temp = True

    try:
        client = Groq()
        try:
            with open(temp_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3",
                    response_format="verbose_json",
                )
        except Exception as exc:
            exc_str = str(exc).lower()
            is_rate_limit = (
                "429" in str(exc)
                or "rate" in exc_str
                or "quota" in exc_str
                or "limit" in exc_str
            )
            if is_rate_limit:
                logger.error(
                    "[RETRY:SDK] Groq rate-limit/quota event after SDK retries: %s", exc
                )
                raise GroqQuotaExhaustedError(
                    f"Groq rate-limit/quota event after SDK retries: {exc}"
                ) from exc
            raise
    finally:
        if _owns_temp:
            try:
                os.unlink(temp_path)
            except OSError as unlink_err:
                logger.warning(
                    "Failed to delete temp audio file %r after Groq call: %s",
                    temp_path, unlink_err,
                )

    # Map verbose_json response to the canonical transcript dict shape.
    segments = []
    timestamped_parts = []

    for seg in transcription.segments:
        text = seg.text.strip() if hasattr(seg, "text") else str(seg)
        start = getattr(seg, "start", 0.0)
        end = getattr(seg, "end", 0.0)
        timestamp = format_timestamp(start)
        segments.append(
            {
                "start": start,
                "end": end,
                "text": text,
                "timestamp": timestamp,
            }
        )
        timestamped_parts.append(f"[{timestamp}] {text}")

    full_text = " ".join(s["text"] for s in segments)
    word_count = len(full_text.split())

    return {
        "segments": segments,
        "full_text": full_text,
        "timestamped_text": "\n".join(timestamped_parts),
        "language": getattr(transcription, "language", "unknown"),
        "word_count": word_count,
    }
