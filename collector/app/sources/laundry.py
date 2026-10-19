"""The washer and dryer, for the Laundry card on Home and the Home panel.

Hisense machines report to the ConnectLife cloud; there is no local API. The
hub reads them every minute with its own ConnectLife account (NAS-only .env),
read-only. This is a small client of our own, written from the MIT-licensed
bilan/connectlife-api-connector: log in through ConnectLife's Gigya account
service, trade that for an OAuth token, then ask ConnectLife's gateway for the
status of the account's appliances. The gateway wants each request signed: a
SHA-256 of the parameters, encrypted with ConnectLife's public RSA key
(PKCS#1 v1.5), done here with the standard library.

Unofficial: ConnectLife can change this any day, and too many logins can get
the account blocked for a while, so the token is reused until it stops working.
What the numbers mean (running, door open, which program) is per device type:
the dryer (030) and washer (025) follow the community's published mappings.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from ..models import Envelope
from ..store import Store

log = logging.getLogger(__name__)

CACHE_KEY = "laundry"
TIMEOUT_SECONDS = 20
# A finished machine shows until its door opens, or this long at most.
DONE_FOR = timedelta(hours=2)
# An access token lasts as long as ConnectLife says (expires_in), renewed this
# early; this long when it does not say. A refresh token renews it without a
# login, so Gigya is asked only when ConnectLife refuses the refresh token.
TOKEN_FOR = timedelta(hours=12)
RENEW_EARLY = timedelta(seconds=90)
# After a refused login Gigya keeps refusing (403048) while it is asked again,
# so the client waits before the next try: 15 minutes, doubling up to 2 hours.
LOGIN_PAUSE = timedelta(minutes=15)
LOGIN_PAUSE_MAX = timedelta(hours=2)

TABLES = """
CREATE TABLE IF NOT EXISTS connectlife_auth (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    access_token  TEXT,
    token_until   TEXT,
    paused_until  TEXT,
    pause_seconds INTEGER NOT NULL,
    refresh_token TEXT,
    refresh_until TEXT
);
"""

# The ConnectLife app's own public identifiers, as in the MIT reference: the same
# in every copy of the app, not secrets of ours (hence gitleaks:allow; see
# .gitleaksignore for the commit that added them).
GIGYA = "https://accounts.eu1.gigya.com"
OAUTH = "https://oauth.hijuconn.com/oauth"
GATEWAY = "https://clife-eu-gateway.hijuconn.com"
API_KEY = "4_yhTWQmHFpZkQZDSV1uV-_A"  # gitleaks:allow
CLIENT_ID = "5065059336212"
CLIENT_SECRET = "07swfKgvJhC3ydOUS9YV_SwVz0i4LKqlOLGNUukYHVMsJRF1b-iWeUGcNlXyYCeK"  # gitleaks:allow
REDIRECT = "https://api.connectlife.io/swagger/oauth2-redirect.html"
APP_ID = "47110565134383"
APP_SECRET = "yOzhz6junYno-nmULM3Wr7PU_dpSZN22ZdluvVWZ4uW5ZwwG8fIGCHTbrhcnU-iv"  # gitleaks:allow
SIGN_SALT = "D9519A4B756946F081B7BB5B5E8D1197"
PUBLIC_KEY = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAyyWrNG6q475HIHu7sMVu"
    "vHof6vlgPeixmxa4EL/UsvVvHPz33NnWoQetQqit9TBNzUjMXw0KlY9PXM4iqHUU"
    "U+dSyNDq1jZWIiJ2C2FccppswJtIKL3NRMFvT9PFh6NlP/4FUcQKojgKFbF7Kacc"
    "JPKYHlwaO7qgoIjLxAHlSOXGpucJcOkPzT2EqsSVnW8sn8kenvNmghXDayhgxsh6"
    "AyxK4kehJplEnmX/iYCfNoFXknGcLqFWYccgBz3fybvx30C/0IgU1980L8QsUAv5"
    "esZmN8ugnbRgLRxKRlkQQLxQAiZMZdKTAx665YflT3YMHJvEFE8c2XFgoxHzSMc4"
    "BwIDAQAB")
UA = {"User-Agent": "Runner/2.0.6 (iPhone; iOS 17.2.1; Scale/3.00)"}

Kind = Literal["washer", "dryer"]
State = Literal["idle", "running", "paused", "done", "error"]

# Per device type: machine_status values, the door's open value, the dryer's
# program names and finished phases. From the community's published mappings.
WASHER, DRYER = "025", "030"
RUNNING, PAUSED, ALARM = 2, 3, 4
DOOR_OPEN = {WASHER: 1, DRYER: 2}
DRYER_FINISHED_PHASES = {4, 5}  # anti-crease, finished
DRYER_PROGRAMS = {1: "Auto", 2: "Allergy care", 3: "Refresh", 4: "Sportswear", 5: "Towels",
                  7: "Time", 8: "Cotton", 9: "Baby care", 10: "Synthetic", 11: "Wool",
                  12: "Delicates", 13: "Quick 30", 17: "Shirts", 18: "Bedding", 19: "Down"}
# Learnt one wash at a time (the numbers do not follow the dial); unknown ones
# show as "Program 6".
WASHER_PROGRAMS = {9: "Cotton"}
WASHER_ERRORS = {100: "Unbalanced load"}


class Machine(BaseModel):
    id: str  # a short hash of ConnectLife's device id; the id itself stays out
    name: str  # as named in the ConnectLife app
    kind: Kind
    state: State
    online: bool
    program: str | None = None
    remaining_minutes: int | None = None
    total_minutes: int | None = None
    ready_at: datetime | None = None
    done_at: datetime | None = None
    door_open: bool = False
    error: str | None = None  # "F05" or a reason ConnectLife names


class Laundry(Envelope):
    machines: list[Machine]  # washers first
    showing: bool  # a machine runs, is paused, has an error or is done


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    c = cfg.get("connectlife") or {}
    user, password = (c.get("username") or "").strip(), (c.get("password") or "").strip()
    return {"enabled": bool(user and password), "username": user, "password": password}


# --- signing -------------------------------------------------------------------------


def _der(data: bytes) -> list[tuple[int, bytes]]:
    """The (tag, value) items of DER data at one level."""
    items, pos = [], 0
    while pos < len(data):
        tag, length = data[pos], data[pos + 1]
        pos += 2
        if length & 0x80:
            size = length & 0x7F
            length = int.from_bytes(data[pos:pos + size], "big")
            pos += size
        items.append((tag, data[pos:pos + length]))
        pos += length
    return items


def rsa_key(b64: str) -> tuple[int, int]:
    """(n, e) of a base64 SubjectPublicKeyInfo."""
    ((_, spki),) = _der(base64.b64decode(b64))
    _, bits = _der(spki)[1]
    ((_, rsa),) = _der(bits[1:])  # past the unused-bits byte
    (_, n), (_, e) = _der(rsa)
    return int.from_bytes(n, "big"), int.from_bytes(e, "big")


def rsa_encrypt(message: bytes, key: tuple[int, int]) -> bytes:
    """RSA PKCS#1 v1.5 encryption with a public key (what the reference's PHP
    openssl_public_encrypt does)."""
    n, e = key
    size = (n.bit_length() + 7) // 8
    need = size - len(message) - 3
    padding = b""
    while len(padding) < need:
        padding += bytes(b for b in secrets.token_bytes(size) if b)
    block = b"\x00\x02" + padding[:need] + b"\x00" + message
    return pow(int.from_bytes(block, "big"), e, n).to_bytes(size, "big")


def sign_text(params: dict[str, Any]) -> str:
    """What gets hashed: the parameters sorted by name, as k=v joined by &."""
    return "&".join(f"{k}={json.dumps(v) if isinstance(v, (dict, list)) else v}"
                    for k, v in sorted(params.items()))


def signed(params: dict[str, Any], key: tuple[int, int] | None = None) -> dict[str, Any]:
    digest = hashlib.sha256((sign_text(params) + SIGN_SALT).encode()).digest()
    cipher = rsa_encrypt(digest, key or rsa_key(PUBLIC_KEY))
    return params | {"sign": base64.b64encode(cipher).decode()}


def _iso(when: datetime | None) -> str | None:
    return when.isoformat() if when else None


def _when(text: str | None) -> datetime | None:
    return datetime.fromisoformat(text) if text else None


def refresh_expiry(value: Any) -> datetime | None:
    """ConnectLife's refreshTokenExpiredTime: epoch milliseconds or ISO 8601."""
    if value is None or isinstance(value, bool):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).strip().isdigit():
            return datetime.fromtimestamp(int(value) / 1000, UTC)
        when = datetime.fromisoformat(str(value).strip())
    except (ValueError, OverflowError, OSError):
        return None
    return when if when.tzinfo else when.replace(tzinfo=UTC)


# --- the ConnectLife conversation ------------------------------------------------------


class ConnectLifeError(Exception):
    """A refusal with a reason fit for the log, without the account or tokens."""


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.executescript(TABLES)
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(connectlife_auth)")}
        # Added for the refresh token (2026-10-19).
        for column in ("refresh_token", "refresh_until"):
            if column not in columns:
                conn.execute(f"ALTER TABLE connectlife_auth ADD COLUMN {column} TEXT")


class Client:
    """Logs in once, then renews the token with the refresh token for as long
    as ConnectLife takes it. The tokens and a login pause are kept in SQLite,
    so a restart neither logs in again nor forgets a pause."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.transport = transport  # for tests
        self.token: str | None = None
        self.token_until: datetime | None = None
        self.pause = LOGIN_PAUSE
        self.paused_until: datetime | None = None
        self.refresh_token: str | None = None
        self.refresh_until: datetime | None = None
        self.loaded = False

    def _state(self) -> tuple[Any, ...]:
        return (self.token, _iso(self.token_until), _iso(self.paused_until),
                int(self.pause.total_seconds()), self.refresh_token, _iso(self.refresh_until))

    def _load(self, store: Store) -> None:
        if self.loaded:
            return
        with store.connect() as conn:
            row = conn.execute("SELECT access_token, token_until, paused_until, pause_seconds, "
                               "refresh_token, refresh_until FROM connectlife_auth "
                               "WHERE id = 1").fetchone()
        if row:
            self.token, self.token_until = row["access_token"], _when(row["token_until"])
            self.paused_until = _when(row["paused_until"])
            self.pause = timedelta(seconds=row["pause_seconds"])
            self.refresh_token = row["refresh_token"]
            self.refresh_until = _when(row["refresh_until"])
        self.loaded = True

    def _save(self, store: Store) -> None:
        with store.connect() as conn:
            conn.execute(
                "INSERT INTO connectlife_auth (id, access_token, token_until, paused_until, "
                "pause_seconds, refresh_token, refresh_until) VALUES (1, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET access_token = excluded.access_token, "
                "token_until = excluded.token_until, paused_until = excluded.paused_until, "
                "pause_seconds = excluded.pause_seconds, refresh_token = excluded.refresh_token, "
                "refresh_until = excluded.refresh_until",
                self._state())

    async def _fresh_token(self, http: httpx.AsyncClient, user: str, password: str,
                           now: datetime) -> str:
        if self.paused_until and now < self.paused_until:
            raise ConnectLifeError(
                f"login paused until {self.paused_until:%H:%M} UTC after a refusal")
        try:
            token = self._take(await self._login(http, user, password), now)
        except ConnectLifeError:
            self.paused_until = now + self.pause
            self.pause = min(self.pause * 2, LOGIN_PAUSE_MAX)
            raise
        self.pause, self.paused_until = LOGIN_PAUSE, None
        return token

    def _take(self, answer: dict[str, Any], now: datetime) -> str:
        """Keep the tokens of an /oauth/token answer; ConnectLife may leave out
        a new refresh token, and then the old one stays."""
        token = answer.get("access_token")
        if not token:
            raise ConnectLifeError("no access token")
        try:
            lasts = timedelta(seconds=int(answer["expires_in"])) - RENEW_EARLY
        except (KeyError, TypeError, ValueError):
            lasts = TOKEN_FOR
        self.token, self.token_until = token, now + max(lasts, timedelta(0))
        if answer.get("refresh_token"):
            self.refresh_token = answer["refresh_token"]
            self.refresh_until = refresh_expiry(answer.get("refreshTokenExpiredTime"))
        return token

    async def _refresh(self, http: httpx.AsyncClient, now: datetime) -> str:
        resp = await http.post(f"{OAUTH}/token", data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "redirect_uri": REDIRECT,
            "grant_type": "refresh_token", "refresh_token": self.refresh_token})
        resp.raise_for_status()
        answer = resp.json()
        if not answer.get("access_token"):
            raise ConnectLifeError("refresh token refused")
        return self._take(answer, now)

    async def _login(self, http: httpx.AsyncClient, user: str,
                     password: str) -> dict[str, Any]:
        # No gmid: the one copied from the reference is shared by every copy of it,
        # the likely reason Gigya answered 403048 ("Api rate limit exceeded").
        login = (await http.post(f"{GIGYA}/accounts.login", data={
            "loginID": user, "password": password, "APIKey": API_KEY})).json()
        cookie = (login.get("sessionInfo") or {}).get("cookieValue")
        if not cookie:
            raise ConnectLifeError(f"login refused (Gigya {login.get('errorCode')})")
        jwt = (await http.post(f"{GIGYA}/accounts.getJWT", data={
            "APIKey": API_KEY, "login_token": cookie})).json().get("id_token")
        code = (await http.post(f"{OAUTH}/authorize", json={
            "client_id": CLIENT_ID, "idToken": jwt, "response_type": "code",
            "redirect_uri": REDIRECT, "thirdType": "CDC",
            "thirdClientId": login.get("UID")})).json().get("code")
        return (await http.post(f"{OAUTH}/token", data={
            "client_id": CLIENT_ID, "code": code, "grant_type": "authorization_code",
            "client_secret": CLIENT_SECRET, "redirect_uri": REDIRECT})).json()

    async def _status(self, http: httpx.AsyncClient, token: str) -> list[dict[str, Any]]:
        stamp = str(int(datetime.now(UTC).timestamp() * 1000))
        params = {"appId": APP_ID, "appSecret": APP_SECRET, "languageId": "12",
                  "randStr": hashlib.md5(stamp.encode()).hexdigest(), "timeStamp": stamp,
                  "timezone": "1.0", "version": "5.0", "accessToken": token}
        resp = await http.get(f"{GATEWAY}/clife-svc/pu/get_device_status_list",
                              params=signed(params))
        resp.raise_for_status()
        answer = resp.json().get("response") or {}
        if "deviceList" not in answer:
            raise ConnectLifeError(f"status refused (result {answer.get('resultCode')})")
        return answer["deviceList"]

    async def devices(self, store: Store, user: str, password: str,
                      now: datetime) -> list[dict[str, Any]]:
        """Every failure comes out as a ConnectLifeError naming the step only:
        httpx's own errors carry the request address, and for the status call
        that holds the access token, so they must not reach the log."""
        self._load(store)
        before = self._state()
        try:
            return await self._devices(user, password, now)
        except ConnectLifeError:
            raise
        except httpx.HTTPStatusError as exc:
            step = exc.request.url.path.rsplit("/", 1)[-1]
            raise ConnectLifeError(f"{step}: HTTP {exc.response.status_code}") from None
        except httpx.HTTPError as exc:
            raise ConnectLifeError(f"{type(exc).__name__} talking to ConnectLife") from None
        except ValueError:
            raise ConnectLifeError("an answer that is not JSON") from None
        finally:
            if self._state() != before:
                self._save(store)

    async def _devices(self, user: str, password: str, now: datetime) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, headers=UA,
                                     transport=self.transport) as http:
            if self.token and self.token_until and now < self.token_until:
                try:
                    return await self._status(http, self.token)
                except (ConnectLifeError, httpx.HTTPStatusError):
                    # The token may have expired early.
                    self.token = None
            if self.refresh_token and not (self.refresh_until and now >= self.refresh_until):
                try:
                    return await self._status(http, await self._refresh(http, now))
                except (ConnectLifeError, httpx.HTTPStatusError):
                    # Refused: forget it and log in again below. A network failure
                    # keeps it for the next minute.
                    self.token = self.refresh_token = self.refresh_until = None
            # One fresh login, then give up.
            return await self._status(http, await self._fresh_token(http, user, password, now))


CLIENT = Client()


# --- what the numbers mean ------------------------------------------------------------


def machine_id(device: dict[str, Any]) -> str:
    """A short hash of ConnectLife's device id; the id itself stays out of the hub."""
    raw = str(device.get("puid") or device.get("deviceId"))
    return hashlib.sha256(raw.encode()).hexdigest()[:10]


def _int(props: dict[str, Any], name: str) -> int | None:
    try:
        return int(str(props.get(name, "")).strip())
    except ValueError:
        return None


def _program(type_code: str, props: dict[str, Any]) -> str | None:
    pid = _int(props, "Selected_program_ID")
    if pid is None:
        return None
    if type_code == DRYER:
        return DRYER_PROGRAMS.get(pid, f"Program {pid}")
    return WASHER_PROGRAMS.get(pid, f"Program {pid}")


def read_machine(device: dict[str, Any], previous: dict[str, Any] | None,
                 now: datetime) -> Machine:
    """One machine's state now, from its status and what it was a minute ago:
    a machine that stops running stays done until its door opens."""
    code = device.get("deviceTypeCode")
    props = device.get("statusList") or {}
    status = _int(props, "machine_status") or 0
    door_open = _int(props, "Door_status") == DOOR_OPEN.get(code)
    remaining = _int(props, "Selected_program_remaining_time_in_minutes")
    error_code = _int(props, "error_code") or 0
    was = (previous or {}).get("state")
    done_at = (previous or {}).get("done_at")
    done_at = datetime.fromisoformat(done_at) if isinstance(done_at, str) else done_at

    error = None
    if error_code:
        error = WASHER_ERRORS.get(error_code) if code == WASHER else None
        error = error or f"F{error_code:02d}"
    finished_phase = code == DRYER and _int(props, "Current_program_phase") in DRYER_FINISHED_PHASES

    state: State
    if error_code or status == ALARM:
        state = "error"
    elif status == RUNNING and not finished_phase:
        state = "running"
    elif status == PAUSED:
        state = "paused"
    elif was in ("running", "paused", "done") or (previous is None and finished_phase
                                                    and status != 0):
        # Done only right after running (or, after a restart, when the dryer
        # still says finished): a dryer left in standby keeps its finished
        # phase, and closing its door again must not bring the card back.
        state = "done"
    else:
        state = "idle"

    if state == "done":
        done_at = done_at if was == "done" and done_at else now
        if door_open or now - done_at > DONE_FOR:
            state, done_at = "idle", None
    else:
        done_at = None

    running = state in ("running", "paused")
    return Machine(
        id=machine_id(device),
        name=(device.get("deviceNickName")
              or ("Washing machine" if code == WASHER else "Tumble dryer")).strip(),
        kind="washer" if code == WASHER else "dryer",
        state=state,
        online=device.get("offlineState") == 1,
        program=_program(code, props) if state != "idle" else None,
        remaining_minutes=remaining if running else None,
        total_minutes=_int(props, "Selected_program_total_time_in_minutes") if running else None,
        ready_at=(now + timedelta(minutes=remaining)
                  if state == "running" and remaining else None),
        done_at=done_at,
        door_open=door_open,
        error=error if state == "error" else None,
    )


async def collect(cfg: dict[str, Any], store: Store, now: datetime | None = None,
                  client: Client | None = None) -> Laundry:
    """Raises when ConnectLife cannot be read, so the last good answer stays
    cached, flagged stale."""
    s = settings(cfg)
    now = now or datetime.now(UTC)
    devices = await (client or CLIENT).devices(store, s["username"], s["password"], now)
    before = {m["id"]: m for m in (store.get_cache(CACHE_KEY) or {}).get("machines") or []}
    machines = []
    for device in devices:
        if device.get("deviceTypeCode") not in (WASHER, DRYER):
            continue
        machines.append(read_machine(device, before.get(machine_id(device)), now))
    machines.sort(key=lambda m: m.kind != "washer")
    return Laundry(as_of=now, stale=False, machines=machines,
                   showing=any(m.state != "idle" for m in machines))
