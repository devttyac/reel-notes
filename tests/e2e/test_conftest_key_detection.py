"""Offline tests for the e2e key-detection helpers in conftest.py.

Since plugin 0.2.0 the plugin reads keys from the process environment AND from
~/.config/sumtube/.env. The e2e preconditions must detect keys the same way, or
paid and Whisper tests skip on a file-only setup. Only fake placeholder values
are used here; HOME is redirected to a temp folder so no real key file is read.
"""

from __future__ import annotations

import pytest

from conftest import _has_anthropic_key, _has_groq_key, _key_present

NAMES = ["SUMTUBE_API_KEY", "GROQ_API_KEY"]
HELPERS = {"SUMTUBE_API_KEY": _has_anthropic_key, "GROQ_API_KEY": _has_groq_key}


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def _write_env_file(home, text):
    cfg = home / ".config" / "sumtube"
    cfg.mkdir(parents=True)
    (cfg / ".env").write_text(text)


@pytest.mark.parametrize("name", NAMES)
def test_env_set_is_detected(home, monkeypatch, name):
    monkeypatch.setenv(name, "placeholder-not-a-real-key")
    assert _key_present(name) is True
    assert HELPERS[name]() is True


@pytest.mark.parametrize("name", NAMES)
def test_file_only_with_value_is_detected(home, name):
    _write_env_file(home, f"{name}=placeholder-not-a-real-key\n")
    assert _key_present(name) is True
    assert HELPERS[name]() is True


@pytest.mark.parametrize("name", NAMES)
def test_file_with_only_other_name_is_not_detected(home, name):
    other = "GROQ_API_KEY" if name == "SUMTUBE_API_KEY" else "SUMTUBE_API_KEY"
    _write_env_file(home, f"{other}=placeholder-not-a-real-key\n")
    assert _key_present(name) is False
    assert HELPERS[name]() is False


@pytest.mark.parametrize("name", NAMES)
def test_file_with_empty_value_is_not_detected(home, name):
    _write_env_file(home, f"{name}=\n")
    assert _key_present(name) is False
    assert HELPERS[name]() is False


@pytest.mark.parametrize("name", NAMES)
def test_empty_env_var_is_not_detected(home, monkeypatch, name):
    monkeypatch.setenv(name, "")
    assert _key_present(name) is False


@pytest.mark.parametrize("name", NAMES)
def test_neither_env_nor_file_is_not_detected(home, name):
    assert _key_present(name) is False
    assert HELPERS[name]() is False


@pytest.mark.parametrize("name", NAMES)
def test_name_prefix_does_not_match(home, name):
    _write_env_file(home, f"X{name}=placeholder-not-a-real-key\n")
    assert _key_present(name) is False


@pytest.mark.parametrize("name", NAMES)
def test_file_among_other_lines_is_detected(home, name):
    _write_env_file(home, f"# comment\nOTHER=1\n{name}=placeholder-not-a-real-key\n")
    assert _key_present(name) is True


def test_home_resolved_at_call_time(tmp_path, monkeypatch):
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    _write_env_file(first, "SUMTUBE_API_KEY=placeholder-not-a-real-key\n")
    monkeypatch.setenv("HOME", str(first))
    assert _key_present("SUMTUBE_API_KEY") is True
    monkeypatch.setenv("HOME", str(second))
    assert _key_present("SUMTUBE_API_KEY") is False
