"""Loads the config, substituting ${ENV_VAR} references from the environment.

The repo's config.yaml is a neutral example. The household's own config lives in
config.local.yaml beside it (never in git; on the NAS mounted into the container),
which wins when present. COLLECTOR_CONFIG names another file instead.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

_ENV_REF = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(?::-([^}]*))?\}")

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
LOCAL_PATH = DEFAULT_PATH.with_name("config.local.yaml")


def _sub(match: re.Match[str]) -> str:
    name, default = match.group(1), match.group(2)
    return os.environ.get(name) or (default or "")


def _expand(value: Any) -> Any:
    """Recursively replace ${VAR} and ${VAR:-default} with environment values.

    The default form lets one config file serve both local development (pointing
    at the NAS over Tailscale) and the deployed container (pointing at localhost).
    """
    if isinstance(value, str):
        return _ENV_REF.sub(_sub, value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


def resolve() -> Path:
    """COLLECTOR_CONFIG, else config.local.yaml when it is a file, else config.yaml."""
    if named := os.environ.get("COLLECTOR_CONFIG"):
        return Path(named)
    return LOCAL_PATH if LOCAL_PATH.is_file() else DEFAULT_PATH


def load(path: Path | None = None) -> dict[str, Any]:
    path = path or resolve()
    with path.open() as fh:
        return _expand(yaml.safe_load(fh) or {})
