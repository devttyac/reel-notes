"""sumtube — YouTube captions path.

Validates the cheapest end-to-end path: a YouTube video with auto-captions
goes caption-only → Anthropic → markdown note. Does not exercise Whisper.
"""

from __future__ import annotations

import pytest

from conftest import run_subprocess

YOUTUBE_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo", 19s, captions present


@pytest.mark.live
@pytest.mark.paid
def test_youtube_captions_path_produces_note(python_executable, sumtube_script, tmp_path):
    """End-to-end: YouTube URL → captions → Anthropic → note file written."""
    result = run_subprocess(
        [
            python_executable, str(sumtube_script),
            YOUTUBE_URL,
            "--compact",
            "--output", str(tmp_path),
            "--force",  # do not respect history file
        ],
        timeout=180,
    )
    assert result.returncode == 0, (
        f"sumtube exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    notes = list(tmp_path.rglob("*.md"))
    assert notes, f"no markdown note produced in {tmp_path}"

    # Note has non-trivial body
    body = notes[0].read_text()
    assert len(body) > 200, f"note body suspiciously short ({len(body)} chars): {notes[0]}"
