"""Smoke tests — both plugins' setup.py --check exit 0.

Offline by default but auto-skipped if no Anthropic key (sumtube preflight
requires SUMTUBE_API_KEY or ANTHROPIC_API_KEY to exit 0). media-downloader
preflight has no key requirement.
"""

from __future__ import annotations

import pytest

from conftest import run_subprocess


def test_media_downloader_setup_check_exits_zero(python_executable, media_downloader_setup):
    result = run_subprocess([python_executable, str(media_downloader_setup), "--check"])
    assert result.returncode == 0, (
        f"media-downloader setup --check exited {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


@pytest.mark.paid  # requires SUMTUBE_API_KEY or ANTHROPIC_API_KEY (auto-skip if absent)
def test_sumtube_setup_check_exits_zero(python_executable, sumtube_setup):
    result = run_subprocess([python_executable, str(sumtube_setup), "--check"])
    assert result.returncode == 0, (
        f"sumtube setup --check exited {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
