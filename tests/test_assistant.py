"""Tests for the optional LLM assistant.

These run fully offline: no test here contacts a network backend.
"""

import json

import pytest

from statinvest.assistant import (
    AssistantConfig,
    AssistantError,
    build_facts,
    describe_payload,
    explain,
)


def test_disabled_without_key(monkeypatch):
    monkeypatch.delenv("STATINVEST_LLM_API_KEY", raising=False)
    cfg = AssistantConfig()
    assert cfg.enabled is False
    assert cfg.api_key is None


def test_enabled_with_key(monkeypatch):
    monkeypatch.setenv("STATINVEST_LLM_API_KEY", "sk-test-value")
    assert AssistantConfig().enabled is True


def test_local_backend_needs_no_key(monkeypatch):
    monkeypatch.delenv("STATINVEST_LLM_API_KEY", raising=False)
    cfg = AssistantConfig(base_url="http://localhost:11434/v1", model="llama3.1")
    assert cfg.enabled is True
    assert cfg.status()["local"] is True


def test_status_never_reveals_the_key(monkeypatch):
    monkeypatch.setenv("STATINVEST_LLM_API_KEY", "sk-super-secret-value")
    status = AssistantConfig().status()
    blob = json.dumps(status)
    assert "sk-super-secret-value" not in blob
    assert status["key_present"] is True


def test_explain_without_key_raises_and_leaks_nothing(monkeypatch):
    monkeypatch.delenv("STATINVEST_LLM_API_KEY", raising=False)
    with pytest.raises(AssistantError) as exc:
        explain({"result": {"n": 10}})
    assert "STATINVEST_LLM_API_KEY" in str(exc.value)
    assert "sk-" not in str(exc.value)


def test_build_facts_is_an_allow_list():
    spec = {"family": "ols", "target": "y", "features": ["x"],
            "secret_local_path": "/home/user/private.db",
            "api_key": "sk-should-never-appear"}
    result = {"family": "ols", "n": 100, "r_squared": 0.5,
              "internal_db_handle": "postgres://user:pw@host",
              "coefficients": [{"term": "x", "coef": 1.0, "p_value": 0.01,
                                "private_note": "leak me"}]}
    facts = build_facts(spec, result)
    blob = json.dumps(facts)
    assert "secret_local_path" not in blob
    assert "sk-should-never-appear" not in blob
    assert "internal_db_handle" not in blob
    assert "private_note" not in blob
    assert facts["result"]["r_squared"] == 0.5
    assert facts["coefficients"][0]["coef"] == 1.0


def test_build_facts_keeps_warnings():
    facts = build_facts({"family": "logistic"},
                        {"family": "logistic", "warnings": ["did not converge"]})
    assert facts["result"]["warnings"] == ["did not converge"]


def test_describe_payload_is_readable_json():
    facts = build_facts({"family": "ols"}, {"n": 5, "r_squared": 0.9})
    text = describe_payload(facts)
    assert json.loads(text)["result"]["n"] == 5


def test_no_network_call_when_disabled(monkeypatch):
    """Guard: a disabled assistant must not open a connection at all."""
    monkeypatch.delenv("STATINVEST_LLM_API_KEY", raising=False)
    called = []
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: called.append(1))
    with pytest.raises(AssistantError):
        explain({"result": {}})
    assert called == []


# -- source hygiene -----------------------------------------------------------
def test_source_has_no_non_latin_text():
    """All source is English.

    Guards against non-Latin text creeping back into comments or UI strings.
    Ranges are given as codepoints so this file stays pure ASCII itself.
    """
    import pathlib

    # Hebrew U+0590-U+05FF, Arabic U+0600-U+06FF, Cyrillic U+0400-U+04FF
    blocks = ((0x0590, 0x05FF), (0x0600, 0x06FF), (0x0400, 0x04FF))
    exts = {".py", ".bat", ".sh", ".ps1", ".spec", ".toml", ".ini"}
    skip = {".git", "grandma_results", ".venv", "__pycache__", "node_modules"}

    offenders = []
    root = pathlib.Path(__file__).resolve().parents[1]
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in exts:
            continue
        if any(part in skip for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if any(lo <= ord(ch) <= hi for ch in line for lo, hi in blocks):
                offenders.append(f"{path.relative_to(root)}:{lineno}")

    assert not offenders, "Non-English text in source: " + ", ".join(offenders)
