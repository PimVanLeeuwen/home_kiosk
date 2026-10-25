"""Editable message templates: the wording of every message the hub sends.

A template is Telegram text with `{placeholders}` and a few HTML tags (<b>,
<i>, <u>, <s>, <code>, <pre>). Placeholder values are escaped; everything else in the
template is escaped too, except those tags. A block placeholder (holdings,
volumes, ...) repeats a line template of its own, joined by a separator.

Only your changes are stored (setting "templates", {id: text}); without one
the built-in text applies, which gives exactly the messages from before this
existed. A line that holds a placeholder and renders empty is left out, so an
empty body or block leaves no blank line behind.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any

from ..store import Store
from . import core

SETTING = "templates"
MAX_TEXT = 2000
MAX_MESSAGE = 4096  # Telegram's limit
TAGS = ("b", "i", "u", "s", "code", "pre")

PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
_ESCAPED_TAG = re.compile(r"&lt;(/?)(" + "|".join(TAGS) + r")&gt;")
_TAG = re.compile(r"<(/?)([a-z]+)>")
# Telegram refuses a message with formatting inside a <pre> block.
_TAG_IN_PRE = re.compile(r"<pre>(?:(?!</pre>).)*<(?!/pre>)", re.S)
# Blank lines left at the edges of a <pre> block by an empty block placeholder.
_PRE_EDGES = re.compile(r"<pre>\s+|\s+</pre>")
# Placeholders that were renamed or dropped, for texts saved before.
_RENAMED = (("{icon} ", "<b>{level}</b> · "), ("{icon}", "<b>{level}</b>"),
            ("{dot} ", ""), ("{dot}", ""))


@dataclass(frozen=True)
class Block:
    template: str  # the line template repeated per item
    joiner: str = "\n"


@dataclass(frozen=True)
class Template:
    group: str
    label: str
    description: str
    default: str
    # name -> (what it is, sample value); blocks take a list of item values.
    placeholders: dict[str, tuple[str, Any]]
    blocks: dict[str, Block] = field(default_factory=dict)
    # Messages only: where a test goes, and the severity of the sample.
    category: str = ""
    severity: core.Severity = "info"
    # Line templates: the message they are part of.
    parent: str = ""

    @property
    def is_line(self) -> bool:
        return bool(self.parent)


LEVEL = ("level", ("The severity: ERROR, WARNING, OK or INFO", None))


def _msg(group: str, label: str, description: str, default: str, category: str,
         severity: core.Severity, placeholders: dict[str, tuple[str, Any]],
         blocks: dict[str, Block] | None = None) -> Template:
    return Template(group, label, description, default, dict([LEVEL]) | placeholders,
                    blocks or {}, category, severity)


def _line(group: str, label: str, description: str, default: str, parent: str,
          placeholders: dict[str, tuple[str, Any]]) -> Template:
    return Template(group, label, description, default, placeholders, parent=parent)


RULES = "Alert rules"
REPORTS = "Reports"
NAS = "From the NAS"
TRAIN = "Your train"

CATALOG: dict[str, Template] = {
    # --- alert rules ---------------------------------------------------------------
    "disk_space": _msg(
        RULES, "Disk space", "A storage pool above the Disk space threshold.",
        "<b>{level}</b> · <b>{pool} is {used_pct}% full</b>\n"
        "{free} left of {total}", "rules", "warning",
        {"pool": ("Pool name", "volume2"), "used_pct": ("Percentage used", "92"),
         "free": ("Space left", "1,4 TB"), "total": ("Pool size", "17,9 TB")}),
    "storage_box": _msg(
        RULES, "Storage box space", "The Hetzner storage box above the threshold.",
        "<b>{level}</b> · <b>The storage box is {used_pct}% full</b>\n"
        "{free} left of {total}", "rules", "warning",
        {"used_pct": ("Percentage used", "86"), "free": ("Space left", "150,0 GB"),
         "total": ("Box size", "1,1 TB")}),
    "token_expiry": _msg(
        RULES, "GitHub token expiry", "A GitHub token for Repos and the mirror expires soon.",
        "<b>{level}</b> · <b>GitHub token for {owners} {when}</b>\n"
        "Valid until {date}. Make a new one on GitHub and put it in the hub's .env on the NAS.",
        "rules", "warning", {"owners": ("The owners it reads", "Mine and GEWIS"),
                             "when": ("expires in … days, or expired on …", "expires in 13 days"),
                             "date": ("Expiry date", "Sat 21 Nov 2026")}),
    "ups_outage": _msg(
        NAS, "Power cut", "Sent once after a power cut, when Telegram can be reached again.",
        "<b>{level}</b> · <b>Power cut of {duration}</b>\n"
        "From {start} to {end}, the UPS went down to {lowest}%.\n{stopped}",
        "rules", "warning",
        {"duration": ("How long it lasted", "39 min"),
         "start": ("When it began", "Tue 06 Oct 10:02"),
         "end": ("When power was back", "10:41"), "lowest": ("Lowest battery charge", "62"),
         "stopped": ("A note when the NAS stopped its services at 15%, else empty", "")}),
    "exposure_unexpected": _msg(
        RULES, "Exposure audit", "A public hostname leads to the house but is not allowed.",
        "<b>{level}</b> · <b>{hostname} is public</b>\n"
        "{how}; it {answer}. Only the hostnames in config.yaml may be public.",
        "rules", "error",
        {"hostname": ("The public hostname", "immich.example.com"),
         "how": ("How it leads to the house", "A tunnel route to http://192.168.1.10:2283"),
         "answer": ("What it answered", "answers with 200")}),
    "port_open": _msg(
        RULES, "Open port", "A port on the home IP answered the scan from outside.",
        "<b>{level}</b> · <b>Port {port} is open on the home IP</b>\n"
        "Found by the nightly scan from outside ({ports_checked} ports). Check the router's "
        "port forwards and UPnP.",
        "rules", "error", {"port": ("The open TCP port", "32400"),
                           "ports_checked": ("How many ports were scanned", "65535")}),
    "port_scan_missing": _msg(
        RULES, "Port scan missing", "No good scan from outside for too long.",
        "<b>{level}</b> · <b>No port scan from outside in {hours} h</b>\n"
        "Last good scan: {last}\n{error}",
        "rules", "warning", {"hours": ("The rule's limit", "48"),
                             "last": ("When it last worked", "Thu 08 Oct 04:21"),
                             "error": ("The last error, if any", "Home IP not found")}),
    "apple_offline": _msg(
        RULES, "Apple device offline",
        "An Apple TV or HomePod has not answered for the set minutes.",
        "<b>{level}</b> · <b>{device} is offline</b>\n"
        "Not answering in the {room} for {minutes} min.",
        "rules", "warning",
        {"device": ("The Apple TV or HomePod", "Badkamer"),
         "room": ("Its room", "Bathroom"),
         "minutes": ("How long it has been quiet", "10")}),
    "adguard_down": _msg(
        RULES, "AdGuard not answering",
        "AdGuard Home has not answered for the set minutes: no ad blocking in the house.",
        "<b>{level}</b> · <b>AdGuard is not answering</b>\n"
        "{why} for {minutes} min. The house looks names up through Quad9, without blocking.",
        "rules", "warning",
        {"why": ("Which part fails", "DNS lookups get no answer"),
         "minutes": ("How long it has failed", "5")}),
    "desk_panel_quiet": _msg(
        RULES, "Desk panel quiet",
        "A desk panel board has not asked the hub for the set minutes.",
        "<b>{level}</b> · <b>The {panel} panel is quiet</b>\n"
        "Board {mac} has not asked the hub for {minutes} min: off, out of Wi-Fi reach, or stuck.",
        "rules", "warning",
        {"panel": ("Which panel", "Now"),
         "mac": ("The board's MAC address, as on its back", "e8:f6:0a:e4:42:b0"),
         "minutes": ("How long it has been quiet", "10")}),
    "outside_incident": _msg(
        RULES, "Outside service", "An outside service reports a problem on a part the house uses.",
        "<b>{level}</b> · <b>{service}: {what}</b>\n"
        "{state} on their status page.\n{url}",
        "rules", "warning",
        {"service": ("The service", "Cloudflare"),
         "what": ("The incident's title", "Tunnel errors in Western Europe"),
         "state": ("Degraded or Outage", "Degraded"),
         "url": ("The incident on the status page", "https://stspg.io/abc123")}),
    "train_late": _msg(
        TRAIN, "Train late",
        "The morning train is late (from the set minutes, again when it gets worse).",
        "<b>{level}</b> · <b>The {time} is {delay} min late</b>\n"
        "{name} now leaves at {new_time} from platform {track}.",
        "train", "warning",
        {"time": ("Its planned departure", "07:16"), "name": ("The train", "IC 3522"),
         "delay": ("Minutes late", 6), "new_time": ("Its expected departure", "07:22"),
         "track": ("The platform", "6")}),
    "train_cancelled": _msg(
        TRAIN, "Train cancelled", "The morning train does not run.",
        "<b>{level}</b> · <b>{day}: the {time} does not run</b>\n{name} is cancelled. {next}",
        "train", "warning",
        {"day": ("Today, or Tomorrow the evening before", "Tomorrow"),
         "time": ("Its planned departure", "07:16"), "name": ("The train", "IC 3522"),
         "next": ("The next direct train, or that there is none",
                  "Next direct train: 07:46 from platform 6, arrives 08:58.")}),
    "train_missing": _msg(
        TRAIN, "Train not in the planner", "NS's planner no longer lists the morning train.",
        "<b>{level}</b> · <b>{day}: the {time} is not in NS's planner</b>\n"
        "It may be cancelled; check the NS app. {next}",
        "train", "warning",
        {"day": ("Today, or Tomorrow the evening before", "Tomorrow"),
         "time": ("Its planned departure", "07:16"),
         "next": ("The next direct train, or that there is none",
                  "Next direct train: 07:46 from platform 6, arrives 08:58.")}),
    "train_track": _msg(
        TRAIN, "Platform change", "The morning train leaves from another platform.",
        "<b>{level}</b> · <b>The {time} leaves from platform {new}</b>\nNot platform {old}.",
        "train", "warning",
        {"time": ("Its planned departure", "07:16"), "old": ("The planned platform", "6"),
         "new": ("The new platform", "4")}),
    "train_stops": _msg(
        TRAIN, "Stops cancelled", "The morning train skips stops on the way.",
        "<b>{level}</b> · <b>{day}: the {time} does not stop at {stops}</b>",
        "train", "warning",
        {"day": ("Today, or Tomorrow the evening before", "Tomorrow"),
         "time": ("Its planned departure", "07:16"),
         "stops": ("The skipped stops", "Rotterdam Centraal")}),
    "train_disruption": _msg(
        TRAIN, "Disruption on the route",
        "NS reports a disruption or works on the train's stretch.",
        "<b>{level}</b> · <b>{day}, on your route: {title}</b>\n{text}\n{until}",
        "train", "warning",
        {"day": ("Today, or Tomorrow the evening before", "Tomorrow"),
         "title": ("NS's title", "Utrecht - Amsterdam."),
         "text": ("What happens, in NS's words", "Door werkzaamheden rijden er minder treinen."),
         "until": ("NS's expected end, or empty", "Dit duurt tot ongeveer 10:00 uur.")}),
    "smart_failing": _msg(
        RULES, "Disk failing (SMART)", "Scrutiny marks a disk as failed.",
        "<b>{level}</b> · <b>Disk {disk} is failing (SMART)</b>\n"
        "Check Scrutiny and plan a replacement.",
        "rules", "error", {"disk": ("Disk name", "sdb")}),
    "smart_warning": _msg(
        RULES, "Disk SMART warning", "Scrutiny has warnings for a disk.",
        "<b>{level}</b> · <b>Disk {disk} has SMART warnings</b>\n"
        "Check Scrutiny.", "rules", "warning",
        {"disk": ("Disk name", "sdb")}),
    "container_unhealthy": _msg(
        RULES, "Container unhealthy", "A running container failing its health check.",
        "<b>{level}</b> · <b>{name} is unhealthy</b>\nfor {minutes} min", "rules", "warning",
        {"name": ("Container name", "immich_server"), "minutes": ("Minutes so far", "6")}),
    "container_down": _msg(
        RULES, "Service down", "A service from the catalog whose container is not running.",
        "<b>{level}</b> · <b>{service} is down</b>\n"
        "container {container}: {state}", "rules", "error",
        {"service": ("Service name", "Jellyfin"), "container": ("Container name", "jellyfin"),
         "state": ("Container state", "exited")}),
    "container_restarting": _msg(
        RULES, "Container restarting", "A container that keeps restarting.",
        "<b>{level}</b> · <b>{name} keeps restarting</b>\n"
        "{count} restarts in {window} min", "rules",
        "warning", {"name": ("Container name", "tandoor"), "count": ("Restarts", "4"),
                    "window": ("Window in minutes", "10")}),
    "backup_missing": _msg(
        RULES, "Backup missing", "No successful backup of a volume for too long.",
        "<b>{level}</b> · <b>No successful backup of {volume} in {hours} h</b>\n"
        "Last success: {last_success}", "rules", "error",
        {"volume": ("Volume, or \"the NAS\"", "volume3"), "hours": ("The rule's limit", "26"),
         "last_success": ("When it last worked", "Fri 02 Oct 03:23")}),
    "mirror_missing": _msg(
        RULES, "GitHub mirror missing", "No complete GitHub mirror for too long.",
        "<b>{level}</b> · <b>No complete GitHub mirror in {hours} h</b>\n"
        "Last success: {last_success}",
        "rules", "error", {"hours": ("The rule's limit", "26"),
                           "last_success": ("When it last worked", "Fri 02 Oct 02:01")}),
    "dump_missing": _msg(
        RULES, "Database dump failed", "A database's newest dump failed, or none is recent.",
        "<b>{level}</b> · <b>No good dump of the {database} database</b>\n"
        "Last success: {last_success}\n{error}",
        "rules", "error", {"database": ("Database", "Ghostfolio"),
                           "last_success": ("When it last worked", "Fri 02 Oct 02:30"),
                           "error": ("The error, if any", "pg_dump: connection refused")}),
    "restore_check": _msg(
        RULES, "Restore check", "The monthly restore check failed, or none passed recently.",
        "<b>{level}</b> · <b>Restore check failed, or none passed in {days} days</b>\n"
        "Last good check: {last_verified}\n{error}",
        "rules", "error", {"days": ("The rule's limit in days", "45"),
                           "last_verified": ("When it last passed", "Thu 01 Oct 05:02"),
                           "error": ("What failed, if anything",
                                     "ghostfolio: pg_restore failed")}),
    "portfolio_move": _msg(
        RULES, "Portfolio move", "The portfolio moved more than the threshold today.",
        "<b>{level}</b> · <b>Portfolio moved {move} today</b>\nNow € {value}", "portfolio", "info",
        {"move": ("Signed move", "−3,4%"), "value": ("Total value", "9.119")}),
    "resolved": _msg(
        RULES, "Resolved", "Sent when an alert's problem is gone.",
        "<b>{level}</b> · <b>Resolved: {title}</b>\nafter {duration}", "rules", "ok",
        {"title": ("The alert's first line", "volume2 is 92% full"),
         "duration": ("How long it lasted", "2 h 5 min")}),
    # --- reports -------------------------------------------------------------------
    "portfolio_report": _msg(
        REPORTS, "Portfolio report", "The weekday morning and evening report.",
        "<b>{title}</b> · {when}\n<b>{total}</b>  {change} ({change_pct}) today\n"
        "<pre>{holdings}\n\n{indices}</pre>\n{stale_note}",
        "portfolio", "info",
        {"title": ("Morning report or Evening report", "Morning report"),
         "when": ("Date and time", "Mon 05 Oct, 08:30"), "total": ("Total value", "€ 9.119"),
         "change": ("Today's change", "+€ 84,20"),
         "change_pct": ("Today's change in %", "+0,93%"),
         "holdings": ("One row per holding, in a table", [
             {"symbol": "VWRL   ", "pct": "+1,12%", "change": "+€ 61,30"},
             {"symbol": "NVDA   ", "pct": "−0,40%", "change": " −€ 4,10"}]),
         "indices": ("One row per index, in the same table", [
             {"label": "S&P 500", "pct": "+0,52%"},
             {"label": "AEX    ", "pct": "+0,31%"}]),
         "stale_note": ("Only when Ghostfolio is not answering", [])},
        {"holdings": Block("portfolio_holding"), "indices": Block("portfolio_index"),
         "stale_note": Block("portfolio_stale")}),
    "portfolio_holding": _line(
        REPORTS, "Portfolio report: holding row",
        "One table row per holding, best first. The values are padded to line up.",
        "{symbol}  {pct}  {change}", "portfolio_report",
        {"symbol": ("Ticker", "VWRL   "), "pct": ("Today in %", "+1,12%"),
         "change": ("Today in euro", "+€ 61,30")}),
    "portfolio_index": _line(
        REPORTS, "Portfolio report: index row",
        "One table row per index, under the holdings. The values are padded to line up.",
        "{label}  {pct}", "portfolio_report",
        {"label": ("Index", "S&P 500"), "pct": ("Today in %", "+0,52%")}),
    "portfolio_stale": _line(
        REPORTS, "Portfolio report: old figures", "Added when Ghostfolio is not answering.",
        "<i>Figures from {as_of}; Ghostfolio is not answering.</i>", "portfolio_report",
        {"as_of": ("When the figures are from", "Mon 18:30")}),
    "mirror_failed": _msg(
        REPORTS, "GitHub mirror failed", "A nightly mirror run with failures.",
        "<b>{level}</b> · <b>GitHub mirror failed</b>\n"
        "{problems}\nSee the Backups page", "backup", "error",
        {"problems": ("What failed, one per line",
                      "Hubble-Community-Cafe/pos-app: Token refused (401)")}),
    # --- from the NAS --------------------------------------------------------------
    "backup_ok": _msg(
        NAS, "Backup succeeded", "The nightly rclone backup to Hetzner, all volumes OK.",
        "<b>{level}</b> · <b>NAS backup done</b>\n{volumes}\n{minutes} min", "backup", "ok",
        {"minutes": ("How long it took", "23"),
         "volumes": ("One line per volume", [
             {"status": "OK", "name": "volume1", "label": "docker"},
             {"status": "OK", "name": "volume3", "label": "files"}])},
        {"volumes": Block("backup_volume")}),
    "backup_failed": _msg(
        NAS, "Backup failed", "The nightly rclone backup, with a failed volume.",
        "<b>{level}</b> · <b>NAS backup failed</b>\n{volumes}\n{minutes} min, see the Backups page",
        "backup", "error",
        {"minutes": ("How long it took", "23"),
         "volumes": ("One line per volume", [
             {"status": "OK", "name": "volume1", "label": "docker"},
             {"status": "FAILED", "name": "volume3", "label": "files"}])},
        {"volumes": Block("backup_volume")}),
    "backup_volume": _line(
        NAS, "Backup: volume line", "One line per volume, in both backup messages.",
        "{name} ({label}): {status}", "backup_ok",
        {"status": ("OK or FAILED", "OK"), "name": ("Volume", "volume1"),
         "label": ("What is on it", "docker")}),
    "watchtower": _msg(
        NAS, "Watchtower updates", "Watchtower's nightly report, when it updated something.",
        "<b>{level}</b> · <b>Watchtower: {scanned} scanned, {updated_count} updated, "
        "{failed_count} failed</b>\n{updated}\n{failed}", "updates", "info",
        {"scanned": ("Containers checked", "24"), "updated_count": ("Updated", "2"),
         "failed_count": ("Failed", "1"),
         "updated": ("One line per updated container", [
             {"name": "sonarr", "image": "lscr.io/linuxserver/sonarr:latest"},
             {"name": "readeck", "image": "codeberg.org/readeck/readeck:latest"}]),
         "failed": ("One line per failed container", [
             {"name": "bazarr", "error": "pull access denied"}])},
        {"updated": Block("watchtower_updated"), "failed": Block("watchtower_failed")}),
    "watchtower_updated": _line(
        NAS, "Watchtower: updated line", "One line per updated container.",
        "Updated {name} ({image})", "watchtower",
        {"name": ("Container", "sonarr"), "image": ("Image", "lscr.io/linuxserver/sonarr:latest")}),
    "watchtower_failed": _line(
        NAS, "Watchtower: failed line", "One line per container that failed to update.",
        "Failed {name}: {error}", "watchtower",
        {"name": ("Container", "bazarr"), "error": ("Watchtower's error", "pull access denied")}),
    "kuma": _msg(
        NAS, "Uptime Kuma", "A monitor going down, up, pending or into maintenance.",
        "<b>{level}</b> · <b>{monitor} {state}</b>\n{message}", "uptime", "error",
        {"monitor": ("Monitor name", "Jellyfin"),
         "state": ("is down, is up, is pending, is in maintenance", "is down"),
         "message": ("Kuma's message", "connect ECONNREFUSED 192.168.1.10:8096")}),
}


class TemplateError(ValueError):
    """A template that cannot be saved, with a message fit for the form."""


# --- storage ----------------------------------------------------------------------------


def _migrate(text: str) -> str:
    for old, new in _RENAMED:
        text = text.replace(old, new)
    return text


def overrides(store: Store) -> dict[str, str]:
    return {tid: _migrate(text) for tid, text in core.get_setting(store, SETTING, {}).items()}


def text_of(store: Store | None, template_id: str, drafts: dict[str, str] | None = None) -> str:
    if drafts and template_id in drafts:
        return drafts[template_id]
    saved = overrides(store) if store is not None else {}
    return saved.get(template_id, CATALOG[template_id].default)


def save(store: Store, template_id: str, text: str) -> None:
    check(template_id, text)
    saved = overrides(store)
    if text == CATALOG[template_id].default:
        saved.pop(template_id, None)
    else:
        saved[template_id] = text
    core.put_setting(store, SETTING, saved)


def reset(store: Store, template_id: str) -> None:
    saved = overrides(store)
    saved.pop(template_id, None)
    core.put_setting(store, SETTING, saved)


# --- rendering --------------------------------------------------------------------------


def _escape_template(text: str) -> str:
    return _ESCAPED_TAG.sub(r"<\1\2>", html.escape(text, quote=False))


def _render(store: Store | None, template_id: str, values: dict[str, Any],
            drafts: dict[str, str] | None) -> str:
    template = CATALOG[template_id]
    text = text_of(store, template_id, drafts)
    lines = []
    for line in _escape_template(text).split("\n"):
        had_placeholder = False

        def fill(match: re.Match[str]) -> str:
            nonlocal had_placeholder
            name = match.group(1)
            if name not in template.placeholders:
                return match.group(0)  # never saved like this; shown as typed
            had_placeholder = True
            if name in template.blocks:
                block = template.blocks[name]
                items = values.get(name) or []
                return block.joiner.join(_render(store, block.template, item, drafts)
                                         for item in items)
            value = values.get(name)
            return "" if value is None else html.escape(str(value), quote=False)

        rendered = PLACEHOLDER.sub(fill, line)
        if had_placeholder and not rendered.strip():
            continue
        lines.append(rendered)
    return "\n".join(lines).strip()


def render(store: Store | None, template_id: str, values: dict[str, Any],
           severity: core.Severity | None = None,
           drafts: dict[str, str] | None = None) -> str:
    """Telegram HTML. `drafts` are unsaved texts by id, for previews and tests."""
    template = CATALOG[template_id]
    level = core.LEVEL.get(severity or template.severity, "")
    text = _render(store, template_id, {"level": level} | values, drafts)
    text = _PRE_EDGES.sub(lambda m: m.group(0).strip(), text)
    return re.sub(r"\n?<pre></pre>", "", text).strip()


def plain(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text))


@dataclass(frozen=True)
class Rendered:
    html: str
    title: str  # plain first line without the level, for the message log
    body: str


def message(store: Store | None, template_id: str, values: dict[str, Any],
            severity: core.Severity | None = None,
            drafts: dict[str, str] | None = None) -> Rendered:
    text = render(store, template_id, values, severity, drafts)
    first, _, rest = plain(text).partition("\n")
    level = core.LEVEL.get(severity or CATALOG[template_id].severity, "")
    title = first.strip()
    if level:
        title = title.removeprefix(f"{level} · ").removeprefix(level).strip()
    return Rendered(text, title[:200] or "(empty)", rest.strip())


# --- samples and checks -----------------------------------------------------------------


def sample_values(template_id: str) -> dict[str, Any]:
    return {name: sample for name, (_, sample) in CATALOG[template_id].placeholders.items()
            if name != "level"}


def sample(template_id: str, drafts: dict[str, str] | None = None,
           store: Store | None = None) -> Rendered:
    """The message as it would go out with sample values; a line template is
    shown inside its message."""
    template = CATALOG[template_id]
    target = template.parent or template_id
    return message(store, target, sample_values(target), CATALOG[target].severity, drafts)


def check(template_id: str, text: str) -> None:
    """Raise TemplateError for text that would not render as a valid message."""
    template = CATALOG[template_id]
    if not text.strip():
        raise TemplateError("The message cannot be empty.")
    if len(text) > MAX_TEXT:
        raise TemplateError(f"Keep it under {MAX_TEXT} characters.")
    unknown = sorted({m for m in PLACEHOLDER.findall(text) if m not in template.placeholders})
    if unknown:
        names = ", ".join("{" + n + "}" for n in unknown)
        raise TemplateError(f"Unknown placeholder: {names}.")
    stack: list[str] = []
    for closing, tag in _TAG.findall(text):
        if tag not in TAGS:
            raise TemplateError(f"<{tag}> is not allowed; use {', '.join(f'<{t}>' for t in TAGS)}.")
        if not closing:
            stack.append(tag)
        elif not stack or stack.pop() != tag:
            raise TemplateError(f"</{tag}> does not close an open <{tag}>.")
    if stack:
        raise TemplateError(f"<{stack[-1]}> is never closed.")
    rendered = sample(template_id, {template_id: text}).html
    if _TAG_IN_PRE.search(rendered):
        raise TemplateError("Telegram allows no other tags inside <pre>.")
    if len(rendered) > MAX_MESSAGE:
        raise TemplateError("With the sample values this is longer than Telegram allows.")
