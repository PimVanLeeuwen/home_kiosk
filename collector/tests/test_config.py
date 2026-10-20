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


def test_the_local_config_wins_over_the_shipped_example(tmp_path, monkeypatch):
    monkeypatch.delenv("COLLECTOR_CONFIG", raising=False)
    monkeypatch.setattr(config, "DEFAULT_PATH", tmp_path / "config.yaml")
    monkeypatch.setattr(config, "LOCAL_PATH", tmp_path / "config.local.yaml")
    config.DEFAULT_PATH.write_text("source: example\n")

    assert config.load() == {"source": "example"}

    config.LOCAL_PATH.write_text("source: local\n")
    assert config.load() == {"source": "local"}


def test_a_folder_in_place_of_the_local_config_is_ignored(tmp_path, monkeypatch):
    # Docker creates a folder when the file to mount is missing on the host.
    monkeypatch.delenv("COLLECTOR_CONFIG", raising=False)
    monkeypatch.setattr(config, "DEFAULT_PATH", tmp_path / "config.yaml")
    monkeypatch.setattr(config, "LOCAL_PATH", tmp_path / "config.local.yaml")
    config.LOCAL_PATH.mkdir()

    assert config.resolve() == config.DEFAULT_PATH


def test_collector_config_names_another_file(tmp_path, monkeypatch):
    named = tmp_path / "elsewhere.yaml"
    named.write_text("source: named\n")
    monkeypatch.setattr(config, "LOCAL_PATH", tmp_path / "config.local.yaml")
    config.LOCAL_PATH.write_text("source: local\n")
    monkeypatch.setenv("COLLECTOR_CONFIG", str(named))

    assert config.load() == {"source": "named"}
