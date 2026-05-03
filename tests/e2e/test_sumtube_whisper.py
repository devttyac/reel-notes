"""sumtube — Groq Whisper path on a local file.

regression: v0.1.3 ffmpeg `-y` flag (mkstemp-pre-created mp3 stub caused
ffmpeg to refuse overwrite, leaving Groq with a 0-byte file).
"""

from __future__ import annotations

import pytest

from conftest import run_subprocess


@pytest.mark.live
@pytest.mark.paid
def test_local_file_whisper_path_produces_note(
    python_executable, sumtube_script, zoo_fixture, has_groq_key, has_ffmpeg, tmp_path
):
    if not has_groq_key:
        pytest.skip("GROQ_API_KEY required for Whisper path")
    if not has_ffmpeg:
        pytest.skip("ffmpeg required for audio extraction")

    result = run_subprocess(
        [
            python_executable, str(sumtube_script),
            str(zoo_fixture),
            "--compact",
            "--output", str(tmp_path),
            "--force",
        ],
        timeout=240,
    )
    assert result.returncode == 0, (
        f"sumtube exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    notes = list(tmp_path.rglob("*.md"))
    assert notes, f"no markdown note produced in {tmp_path}"
    assert len(notes[0].read_text()) > 200
