"""Turn what a NAS sender posts into the hub's own template.

backup.sh sends its figures in `data`; Watchtower only sends its report text,
whose lines come from the template in nas-docker's watchtower compose file and
are read back here. Anything that does not match goes out as it came, so a
changed sender never loses a message.
"""

from __future__ import annotations

import re
from typing import Any

from ..store import Store
from . import core, templates

_WATCHTOWER_HEAD = re.compile(
    r"Watchtower: (\d+) scanned, (\d+) updated, (\d+) failed$")
_WATCHTOWER_UPDATED = re.compile(r"^✅ (\S+) \((.+)\)$")
_WATCHTOWER_FAILED = re.compile(r"^❌ ([^:]+): (.*)$")


def backup(store: Store, data: dict[str, Any]) -> templates.Rendered | None:
    try:
        ok = bool(data["ok"])
        volumes = [
            {"status": "OK" if v.get("ok") else "FAILED", "name": str(v["name"]),
             "label": str(v.get("label") or v["name"])}
            for v in data["volumes"]
        ]
        values = {"minutes": int(data["minutes"]), "volumes": volumes}
    except (KeyError, TypeError, ValueError):
        return None
    return templates.message(store, "backup_ok" if ok else "backup_failed", values,
                             "ok" if ok else "error")


def watchtower_values(title: str, body: str) -> dict[str, Any] | None:
    """The report's figures and lines, or None when it does not read as one."""
    head = _WATCHTOWER_HEAD.search(title)
    if not head:
        return None
    updated, failed = [], []
    for line in (ln.strip() for ln in body.splitlines()):
        if not line:
            continue
        if m := _WATCHTOWER_UPDATED.match(line):
            updated.append({"name": m.group(1), "image": m.group(2)})
        elif m := _WATCHTOWER_FAILED.match(line):
            failed.append({"name": m.group(1).strip(), "error": m.group(2)})
        else:
            return None
    scanned, updated_count, failed_count = head.groups()
    return {"scanned": scanned, "updated_count": updated_count, "failed_count": failed_count,
            "updated": updated, "failed": failed}


def watchtower(store: Store, severity: core.Severity, title: str, body: str,
               extras: dict[str, dict[str, Any]] | None = None) -> templates.Rendered | None:
    """`extras` adds per container name its versions line and update note (M26)."""
    values = watchtower_values(title, body)
    if values is None:
        return None
    for item in values["updated"]:
        item.update((extras or {}).get(item["name"]) or {})
    return templates.message(store, "watchtower", values, severity)


def from_sender(store: Store, source: str, severity: core.Severity, title: str, body: str,
                data: dict[str, Any] | None) -> templates.Rendered | None:
    """The templated message for a known sender, or None to send it as it came."""
    if source == "backup" and data:
        return backup(store, data)
    if source == "watchtower":
        return watchtower(store, severity, title, body)
    return None
