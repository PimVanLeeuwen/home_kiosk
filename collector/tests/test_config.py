from __future__ import annotations

from app import config


def test_expands_env_references_recursively(tmp_path, monkeypatch):
    monkeypatch.setenv("READECK_TOKEN", "secret")
    path = tmp_path / "config.yaml"
    path.write_text("readeck:\n  api_token: ${READECK_TOKEN}\nlist:\n  - ${READECK_TOKEN}\n")

    cfg = config.load(path)

    assert cfg["readeck"]["api_token"] == "secret"
    assert cfg["list"] == ["secret"]


def test_default_used_when_variable_unset_or_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("NAS_HOST", raising=False)
    monkeypatch.setenv("EMPTY", "")
    path = tmp_path / "config.yaml"
    path.write_text("a: http://${NAS_HOST:-localhost}:9100\nb: ${EMPTY:-fallback}\n")

    cfg = config.load(path)

    assert cfg == {"a": "http://localhost:9100", "b": "fallback"}


def test_unset_variable_without_default_expands_to_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("MISSING_VAR", raising=False)
    path = tmp_path / "config.yaml"
    path.write_text("token: ${MISSING_VAR}\n")

    assert config.load(path) == {"token": ""}
