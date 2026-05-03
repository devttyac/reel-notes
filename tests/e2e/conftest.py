"""Shared fixtures for the reel-notes e2e test kit.

Default `pytest tests/e2e` runs only offline tests. Live and paid tests are
opted into via `-m "live"` or `-m "live and paid"`. Tests are auto-skipped
when their preconditions (network, API keys) are not met — never failed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SUMTUBE_SCRIPT = REPO_ROOT / "plugins" / "sumtube" / "scripts" / "summarize.py"
SUMTUBE_SETUP = REPO_ROOT / "plugins" / "sumtube" / "scripts" / "setup.py"
MEDIA_DOWNLOADER_SCRIPT = REPO_ROOT / "plugins" / "media-downloader" / "scripts" / "download.py"
MEDIA_DOWNLOADER_SETUP = REPO_ROOT / "plugins" / "media-downloader" / "scripts" / "setup.py"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _has_anthropic_key() -> bool:
    return bool(os.environ.get("SUMTUBE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))


def _has_groq_key() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))


def _has_network() -> bool:
    """Cheap probe: try resolving a stable host. Skip live tests if it fails."""
    import socket
    try:
        socket.gethostbyname("api.anthropic.com")
        return True
    except OSError:
        return False


def _has_binary(name: str) -> bool:
    return shutil.which(name) is not None or os.path.isfile(f"/opt/homebrew/bin/{name}")


def pytest_collection_modifyitems(config, items):
    """Auto-skip tests whose preconditions are not met.

    - `live` marker: skipped if no network.
    - `paid` marker: skipped if Anthropic key missing. Whisper-using paid tests
      additionally need GROQ_API_KEY; that's checked per-test where relevant.
    - `youtube` marker: skipped under GitHub Actions because YouTube blocks
      runner IPs as bot traffic ("Sign in to confirm you're not a bot").
      Run these locally instead.
    """
    network_ok = _has_network()
    anthropic_ok = _has_anthropic_key()
    in_github_actions = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"

    skip_no_network = pytest.mark.skip(reason="no network — skipping live test")
    skip_no_key = pytest.mark.skip(
        reason="no SUMTUBE_API_KEY / ANTHROPIC_API_KEY — skipping paid test"
    )
    skip_youtube_in_ci = pytest.mark.skip(
        reason="YouTube blocks GitHub Actions IPs as bot traffic — run locally"
    )

    for item in items:
        if "live" in item.keywords and not network_ok:
            item.add_marker(skip_no_network)
        if "paid" in item.keywords and not anthropic_ok:
            item.add_marker(skip_no_key)
        if "youtube" in item.keywords and in_github_actions:
            item.add_marker(skip_youtube_in_ci)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def sumtube_script() -> Path:
    assert SUMTUBE_SCRIPT.is_file(), f"sumtube script missing: {SUMTUBE_SCRIPT}"
    return SUMTUBE_SCRIPT


@pytest.fixture(scope="session")
def sumtube_setup() -> Path:
    return SUMTUBE_SETUP


@pytest.fixture(scope="session")
def media_downloader_script() -> Path:
    assert MEDIA_DOWNLOADER_SCRIPT.is_file(), f"media-downloader script missing: {MEDIA_DOWNLOADER_SCRIPT}"
    return MEDIA_DOWNLOADER_SCRIPT


@pytest.fixture(scope="session")
def media_downloader_setup() -> Path:
    return MEDIA_DOWNLOADER_SETUP


@pytest.fixture(scope="session")
def zoo_fixture() -> Path:
    """Local mp4 used to exercise the Whisper transcription path.

    Source: YouTube `jNQXAC9IVRw` ("Me at the zoo"), ~19s, ~600KB. Copied from
    the test clone after the v0.1.6 verification run.
    """
    fixture = FIXTURES_DIR / "zoo.mp4"
    if not fixture.is_file():
        pytest.skip(f"missing fixture: {fixture}")
    return fixture


@pytest.fixture(scope="session")
def zoo_webm_fixture() -> Path:
    """Local webm used to exercise the v0.1.4 compression regression in CI.

    Re-encoded from `zoo.mp4` using libvpx-vp9 + libopus. Used by tests that
    must run on GitHub Actions (where YouTube downloads are blocked by bot
    detection) to validate that download.py's compression path produces a
    valid mp4 from a webm source.

    To regenerate:
        ffmpeg -y -i zoo.mp4 -c:v libvpx-vp9 -b:v 200k -c:a libopus -b:a 64k zoo.webm
    """
    fixture = FIXTURES_DIR / "zoo.webm"
    if not fixture.is_file():
        pytest.skip(f"missing fixture: {fixture}")
    return fixture


@pytest.fixture
def python_executable() -> str:
    """Python interpreter used to run plugin subprocess invocations.

    Defaults to `sys.executable` (the python running pytest, assumed to have
    the plugin runtime deps installed). Override via SUMTUBE_TEST_PYTHON env
    var if the test runner's python lacks deps but a separate venv has them.
    """
    return os.environ.get("SUMTUBE_TEST_PYTHON", sys.executable)


@pytest.fixture
def has_groq_key() -> bool:
    return _has_groq_key()


@pytest.fixture
def has_yt_dlp() -> bool:
    return _has_binary("yt-dlp")


@pytest.fixture
def has_ffmpeg() -> bool:
    return _has_binary("ffmpeg")


@pytest.fixture
def has_ffprobe() -> bool:
    return _has_binary("ffprobe")


def run_subprocess(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    """Run a subprocess capturing output. Used by tests for plugin invocations."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
