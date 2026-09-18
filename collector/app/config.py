"""Loads config.yaml, substituting ${ENV_VAR} references from the environment."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

_ENV_REF = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def _expand(value: Any) -> Any:
    """Recursively replace ${VAR} with the environment value, or "" if unset."""
    if isinstance(value, str):
        return _ENV_REF.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


def load(path: Path | None = None) -> dict[str, Any]:
    path = path or Path(os.environ.get("COLLECTOR_CONFIG", DEFAULT_PATH))
    with path.open() as fh:
        return _expand(yaml.safe_load(fh) or {})
