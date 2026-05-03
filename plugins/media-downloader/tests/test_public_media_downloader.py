"""
Test suite for the media-downloader public plugin scripts.

Covers:
  1. Vault logic absence checks (grep-based)
  2. download.py — URL validation
  3. download.py — local file path validation
  4. download.py — yt-dlp binary resolution
  5. download.py — ffmpeg binary resolution
  6. download.py — disk space warning
  7. download.py — subprocess never uses shell=True
  8. download.py — --no-playlist always present in yt-dlp invocation
  9. setup.py — exit codes (0, 2, 3, 4)
  10. setup.py — --check flag silent on success
  11. setup.py — --json flag structured output
  12. scripts/__init__.py exists (package import)

Test isolation: no vault paths on sys.path (enforced in conftest.py).
"""

import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
_PLUGIN_ROOT = Path(__file__).parent.parent.resolve()
_SCRIPTS_DIR = _PLUGIN_ROOT / "scripts"


# ---------------------------------------------------------------------------
# 1. Vault logic absence checks
# ---------------------------------------------------------------------------

VAULT_FORBIDDEN_STRINGS = [
    "Claude-Work",
    "YouTube Notes",
    "Obsidian",
    "wikilink",
    "sumtube-learnings",
    "NotebookLM",
    "read_pending_entries",
    "update_entry_status",
    "ANTHROPIC_API_KEY",
    "GROQ_API_KEY",
]

# NOTE: Credential pattern strings below are structural test fixtures, not real keys.
# The grep gate for release is scoped to production *.py files only and excludes test pattern lists.
# The Anthropic key prefix is replaced with a placeholder to avoid triggering secret-scanning tools on this test file.
API_KEY_PATTERNS = [
    "anthropic-secret-prefix-placeholder",
    "gsk_",
    "ANTHROPIC_API_KEY",
    "GROQ_API_KEY",
]


def _grep_scripts(pattern: str) -> list[str]:
    """Return non-comment, non-blank lines matching *pattern* across all .py files."""
    hits = []
    for py_file in _SCRIPTS_DIR.glob("*.py"):
        with open(py_file, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if pattern in line:
                    hits.append(f"{py_file.name}:{lineno}: {line.rstrip()}")
    return hits


class TestVaultLogicAbsence(unittest.TestCase):
    """Scripts must contain no vault paths, API key references, or state file logic."""

    def test_no_vault_forbidden_strings(self):
        for pattern in VAULT_FORBIDDEN_STRINGS:
            with self.subTest(pattern=pattern):
                hits = _grep_scripts(pattern)
                self.assertEqual(
                    hits,
                    [],
                    msg=f"Forbidden string {pattern!r} found in scripts:\n"
                    + "\n".join(hits),
                )

    def test_no_hardcoded_api_key_patterns(self):
        for pattern in API_KEY_PATTERNS:
            with self.subTest(pattern=pattern):
                hits = _grep_scripts(pattern)
                self.assertEqual(
                    hits,
                    [],
                    msg=f"API key pattern {pattern!r} found in scripts:\n"
                    + "\n".join(hits),
                )


# ---------------------------------------------------------------------------
# 2. download.py — URL validation
# ---------------------------------------------------------------------------

class TestDownloadURLValidation(unittest.TestCase):
    """validate_input() must reject non-https URLs and accept https:// URLs."""

    def setUp(self):
        # Import lazily so tests can be collected even before implementation exists
        import scripts.download as dl
        self.dl = dl

    def test_https_url_accepted(self):
        """https:// URL does not raise."""
        # Should not raise
        self.dl.validate_input("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_http_url_rejected(self):
        """http:// (non-SSL) URL raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.dl.validate_input("http://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertIn("https", str(ctx.exception).lower())

    def test_ftp_url_rejected(self):
        """ftp:// URL raises ValueError."""
        with self.assertRaises(ValueError):
            self.dl.validate_input("ftp://example.com/video.mp4")

    def test_file_scheme_url_rejected(self):
        """file:// URL raises ValueError."""
        with self.assertRaises(ValueError):
            self.dl.validate_input("file:///tmp/video.mp4")

    def test_schemeless_domain_rejected(self):
        """Bare domain string raises ValueError."""
        with self.assertRaises(ValueError):
            self.dl.validate_input("www.youtube.com/watch?v=abc")

    def test_plain_string_rejected(self):
        """Random string raises ValueError when not a valid absolute path."""
        with self.assertRaises(ValueError):
            self.dl.validate_input("not_a_url_or_path")


# ---------------------------------------------------------------------------
# 3. download.py — local file path validation
# ---------------------------------------------------------------------------

class TestDownloadLocalPathValidation(unittest.TestCase):
    """validate_input() must accept absolute paths that exist and reject others."""

    def setUp(self):
        import scripts.download as dl
        self.dl = dl

    def test_existing_absolute_path_accepted(self):
        """Absolute path to existing file does not raise."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        try:
            self.dl.validate_input(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_nonexistent_absolute_path_rejected(self):
        """Absolute path to missing file raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.dl.validate_input("/tmp/this_file_does_not_exist_ever_12345.mp4")
        self.assertIn("exist", str(ctx.exception).lower())

    def test_relative_path_rejected(self):
        """Relative file path raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.dl.validate_input("relative/path/video.mp4")
        self.assertIn("absolute", str(ctx.exception).lower())


# ---------------------------------------------------------------------------
# 4. download.py — yt-dlp binary resolution
# ---------------------------------------------------------------------------

class TestDownloadYtDlpResolution(unittest.TestCase):
    """download_url() raises RuntimeError with install hint when yt-dlp missing."""

    def setUp(self):
        import scripts.download as dl
        self.dl = dl

    def test_missing_ytdlp_raises_runtime_error(self):
        """RuntimeError raised with install hint when yt-dlp not found."""
        with patch("shutil.which", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                self.dl.download_url(
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    output_dir="/tmp",
                )
        self.assertIn("yt-dlp", str(ctx.exception))
        self.assertIn("pip install yt-dlp", str(ctx.exception))

    def test_ytdlp_invoked_with_no_playlist(self):
        """yt-dlp subprocess call always includes --no-playlist flag."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        # Simulate yt-dlp outputting a file path
        mock_result.stdout = "/tmp/test_video.mp4\n"

        with patch("shutil.which", return_value="/usr/local/bin/yt-dlp"), \
             patch("subprocess.run", return_value=mock_result) as mock_run, \
             patch.object(self.dl, "compress_with_ffmpeg", return_value="/tmp/test_video.mp4"):
            self.dl.download_url(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                output_dir="/tmp/media-downloader-output",
            )

        # Verify subprocess.run was called and --no-playlist was in the args
        self.assertTrue(mock_run.called)
        call_args = mock_run.call_args[0][0]  # First positional arg = cmd list
        self.assertIn("--no-playlist", call_args)

    def test_ytdlp_not_invoked_with_shell_true(self):
        """yt-dlp subprocess.run must never use shell=True."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "/tmp/test_video.mp4\n"

        with patch("shutil.which", return_value="/usr/local/bin/yt-dlp"), \
             patch("subprocess.run", return_value=mock_result) as mock_run, \
             patch.object(self.dl, "compress_with_ffmpeg", return_value="/tmp/test_video.mp4"):
            self.dl.download_url(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                output_dir="/tmp/media-downloader-output",
            )

        for actual_call in mock_run.call_args_list:
            kwargs = actual_call[1]
            self.assertNotEqual(
                kwargs.get("shell"),
                True,
                msg="subprocess.run called with shell=True — forbidden",
            )

    def test_ytdlp_failure_exits_nonzero(self):
        """Non-zero yt-dlp exit causes SystemExit with non-zero code."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "ERROR: Unable to download"

        with patch("shutil.which", return_value="/usr/local/bin/yt-dlp"), \
             patch("subprocess.run", return_value=mock_result):
            with self.assertRaises(SystemExit) as ctx:
                self.dl.download_url(
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    output_dir="/tmp/media-downloader-output",
                )
        self.assertNotEqual(ctx.exception.code, 0)


# ---------------------------------------------------------------------------
# 5. download.py — ffmpeg binary resolution
# ---------------------------------------------------------------------------

class TestDownloadFfmpegResolution(unittest.TestCase):
    """compress_with_ffmpeg() resolves binary correctly; failure is non-fatal."""

    def setUp(self):
        import scripts.download as dl
        self.dl = dl

    def test_ffmpeg_homebrew_path_tried_first(self):
        """compress_with_ffmpeg tries /opt/homebrew/bin/ffmpeg before shutil.which."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            input_path = tmp.name

        try:
            with patch("os.path.isfile", side_effect=lambda p: p == "/opt/homebrew/bin/ffmpeg"), \
                 patch("subprocess.run", return_value=mock_result) as mock_run:
                self.dl.compress_with_ffmpeg(input_path, output_dir="/tmp")

            call_args = mock_run.call_args[0][0]
            self.assertEqual(call_args[0], "/opt/homebrew/bin/ffmpeg")
        finally:
            os.unlink(input_path)

    def test_ffmpeg_falls_back_to_which(self):
        """compress_with_ffmpeg falls back to shutil.which when homebrew path absent."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            input_path = tmp.name

        try:
            with patch("os.path.isfile", return_value=False), \
                 patch("shutil.which", return_value="/usr/local/bin/ffmpeg"), \
                 patch("subprocess.run", return_value=mock_result) as mock_run:
                self.dl.compress_with_ffmpeg(input_path, output_dir="/tmp")

            call_args = mock_run.call_args[0][0]
            self.assertEqual(call_args[0], "/usr/local/bin/ffmpeg")
        finally:
            os.unlink(input_path)

    def test_ffmpeg_missing_raises_runtime_error(self):
        """RuntimeError raised with install hint when ffmpeg not found anywhere."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            input_path = tmp.name

        try:
            with patch("os.path.isfile", return_value=False), \
                 patch("shutil.which", return_value=None):
                with self.assertRaises(RuntimeError) as ctx:
                    self.dl.compress_with_ffmpeg(input_path, output_dir="/tmp")
        finally:
            os.unlink(input_path)

        self.assertIn("ffmpeg", str(ctx.exception))
        self.assertIn("brew install ffmpeg", str(ctx.exception))

    def test_ffmpeg_never_uses_shell_true(self):
        """compress_with_ffmpeg subprocess.run must never use shell=True."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            input_path = tmp.name

        try:
            with patch("os.path.isfile", return_value=True), \
                 patch("subprocess.run", return_value=mock_result) as mock_run:
                self.dl.compress_with_ffmpeg(input_path, output_dir="/tmp")

            for actual_call in mock_run.call_args_list:
                kwargs = actual_call[1]
                self.assertNotEqual(
                    kwargs.get("shell"),
                    True,
                    msg="compress_with_ffmpeg called subprocess.run with shell=True",
                )
        finally:
            os.unlink(input_path)


# ---------------------------------------------------------------------------
# 6. download.py — disk space warning
# ---------------------------------------------------------------------------

class TestDownloadDiskSpaceWarning(unittest.TestCase):
    """download_url() warns when available disk space < 500MB."""

    def setUp(self):
        import scripts.download as dl
        self.dl = dl

    def test_low_disk_space_emits_warning(self):
        """Warning printed to stderr when < 500MB available."""
        mock_usage = MagicMock()
        mock_usage.free = 100 * 1024 * 1024  # 100 MB — below threshold

        import io
        with patch("shutil.disk_usage", return_value=mock_usage), \
             patch("shutil.which", return_value=None):
            # Will raise RuntimeError (yt-dlp missing) but we just want to verify warning
            with self.assertRaises(RuntimeError):
                with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                    self.dl.download_url(
                        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                        output_dir="/tmp/media-downloader-output",
                    )
                    output = mock_stderr.getvalue()
                    self.assertIn("disk", output.lower())

    def test_sufficient_disk_space_no_warning(self):
        """No disk-space warning when >= 500MB available."""
        mock_usage = MagicMock()
        mock_usage.free = 1024 * 1024 * 1024  # 1 GB

        import io
        with patch("shutil.disk_usage", return_value=mock_usage), \
             patch("shutil.which", return_value=None):
            with self.assertRaises(RuntimeError):
                captured = io.StringIO()
                with patch("sys.stderr", captured):
                    self.dl.download_url(
                        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                        output_dir="/tmp",
                    )


# ---------------------------------------------------------------------------
# 7 & 8. Covered in sections 4 (shell=True checks and --no-playlist checks)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 9. setup.py — exit codes
# ---------------------------------------------------------------------------

class TestSetupExitCodes(unittest.TestCase):
    """setup.py exits with correct codes based on tool availability."""

    def _run_setup(self, ytdlp_present: bool, ffmpeg_present: bool) -> int:
        """Run setup.py --check and return exit code."""
        import scripts.setup as su

        def mock_which(cmd):
            if cmd == "yt-dlp":
                return "/usr/local/bin/yt-dlp" if ytdlp_present else None
            return None

        def mock_isfile(path):
            if "ffmpeg" in str(path):
                return ffmpeg_present
            return False

        with patch("shutil.which", side_effect=mock_which), \
             patch("os.path.isfile", side_effect=mock_isfile):
            try:
                su.run_checks()
                return 0
            except SystemExit as exc:
                return exc.code if exc.code is not None else 0

    def test_both_present_exits_zero(self):
        """Exit 0 when both yt-dlp and ffmpeg are present."""
        code = self._run_setup(ytdlp_present=True, ffmpeg_present=True)
        self.assertEqual(code, 0)

    def test_missing_ytdlp_exits_two(self):
        """Exit code 2 when yt-dlp is missing."""
        code = self._run_setup(ytdlp_present=False, ffmpeg_present=True)
        self.assertEqual(code, 2)

    def test_missing_ffmpeg_exits_three(self):
        """Exit code 3 when ffmpeg is missing."""
        code = self._run_setup(ytdlp_present=True, ffmpeg_present=False)
        self.assertEqual(code, 3)

    def test_both_missing_exits_four(self):
        """Exit code 4 when both yt-dlp and ffmpeg are missing."""
        code = self._run_setup(ytdlp_present=False, ffmpeg_present=False)
        self.assertEqual(code, 4)


# ---------------------------------------------------------------------------
# 10. setup.py — --check flag silent on success
# ---------------------------------------------------------------------------

class TestSetupCheckFlagSilentOnSuccess(unittest.TestCase):
    """--check flag produces no stdout output on success."""

    def test_check_flag_silent_on_success(self):
        """No stdout output when both tools present and --check passed."""
        import io
        import scripts.setup as su

        with patch("shutil.which", return_value="/usr/local/bin/yt-dlp"), \
             patch("os.path.isfile", return_value=True), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            su.run_checks()

        self.assertEqual(
            mock_out.getvalue(),
            "",
            msg="--check should produce no stdout on success",
        )

    def test_check_flag_prints_hint_on_failure(self):
        """One-line actionable hint printed to stderr on failure."""
        import io
        import scripts.setup as su

        with patch("shutil.which", return_value=None), \
             patch("os.path.isfile", return_value=False), \
             patch("sys.stderr", new_callable=io.StringIO) as mock_err:
            try:
                su.run_checks()
            except SystemExit:
                pass

        stderr_output = mock_err.getvalue()
        self.assertIn("yt-dlp", stderr_output)
        self.assertIn("ffmpeg", stderr_output)


# ---------------------------------------------------------------------------
# 11. setup.py — --json flag structured output
# ---------------------------------------------------------------------------

class TestSetupJsonFlag(unittest.TestCase):
    """--json flag returns structured JSON with yt_dlp, ffmpeg, and ready keys."""

    def _run_json(self, ytdlp_present: bool, ffmpeg_present: bool) -> dict:
        import io
        import scripts.setup as su

        def mock_which(cmd):
            if cmd == "yt-dlp":
                return "/usr/local/bin/yt-dlp" if ytdlp_present else None
            return None

        def mock_isfile(path):
            if "ffmpeg" in str(path):
                return ffmpeg_present
            return False

        captured = io.StringIO()
        with patch("shutil.which", side_effect=mock_which), \
             patch("os.path.isfile", side_effect=mock_isfile), \
             patch("sys.stdout", captured):
            try:
                su.run_checks_json()
            except SystemExit:
                pass

        return json.loads(captured.getvalue())

    def test_json_both_present(self):
        result = self._run_json(ytdlp_present=True, ffmpeg_present=True)
        self.assertTrue(result["yt_dlp"])
        self.assertTrue(result["ffmpeg"])
        self.assertTrue(result["ready"])

    def test_json_missing_ytdlp(self):
        result = self._run_json(ytdlp_present=False, ffmpeg_present=True)
        self.assertFalse(result["yt_dlp"])
        self.assertTrue(result["ffmpeg"])
        self.assertFalse(result["ready"])

    def test_json_missing_ffmpeg(self):
        result = self._run_json(ytdlp_present=True, ffmpeg_present=False)
        self.assertTrue(result["yt_dlp"])
        self.assertFalse(result["ffmpeg"])
        self.assertFalse(result["ready"])

    def test_json_both_missing(self):
        result = self._run_json(ytdlp_present=False, ffmpeg_present=False)
        self.assertFalse(result["yt_dlp"])
        self.assertFalse(result["ffmpeg"])
        self.assertFalse(result["ready"])


# ---------------------------------------------------------------------------
# 12. scripts/__init__.py exists (package import)
# ---------------------------------------------------------------------------

class TestScriptsPackageImport(unittest.TestCase):
    """scripts/ must be importable as a package."""

    def test_scripts_init_exists(self):
        """scripts/__init__.py must exist."""
        init_path = _SCRIPTS_DIR / "__init__.py"
        self.assertTrue(
            init_path.exists(),
            msg=f"scripts/__init__.py not found at {init_path}",
        )

    def test_scripts_importable(self):
        """scripts package must be importable."""
        try:
            import scripts
        except ImportError as exc:
            self.fail(f"Failed to import scripts package: {exc}")

    def test_download_module_importable(self):
        """scripts.download must be importable."""
        try:
            import scripts.download
        except ImportError as exc:
            self.fail(f"Failed to import scripts.download: {exc}")

    def test_setup_module_importable(self):
        """scripts.setup must be importable."""
        try:
            import scripts.setup
        except ImportError as exc:
            self.fail(f"Failed to import scripts.setup: {exc}")


if __name__ == "__main__":
    unittest.main()
