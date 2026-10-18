"""Music: Spotify's Web API for the owner's account (plan.md M18).

Read only while someone looks: the hub asks Spotify when the Music page, the
Home card or a panel asks the hub, at most every couple of seconds, and keeps
nothing about what was played. Playback control is a deliberate write.

Signing in uses PKCE (no client secret): Settings → Music sends the browser to
Spotify, which comes back to /api/music/callback on the hub's ts.net address.
The refresh token is kept in the hub's database on the NAS, never logged.

Covers go through the hub as small WebP copies (only covers seen in Spotify's
answers, so this is not an open proxy), with their main colour for the glow.
"""

from __future__ import annotations

import asyncio
import base64
import colorsys
import hashlib
import io
import logging
import secrets
import time
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
from PIL import Image, ImageOps

from ..store import Store

log = logging.getLogger(__name__)

ACCOUNTS = "https://accounts.spotify.com"
API = "https://api.spotify.com/v1"
SCOPES = ("user-read-playback-state user-modify-playback-state user-read-currently-playing "
          "user-read-recently-played playlist-read-private playlist-read-collaborative")
TIMEOUT_SECONDS = 10
LOGIN_FOR = 600  # seconds a started login may take
COVER_SIZE = 300
FAVOURITES = 4
# How long an answer from Spotify is reused: playback moves, devices and the
# last played item hardly do.
FRESH = {"player": 2.0, "devices": 10.0, "recent": 60.0}

TABLES = """
CREATE TABLE IF NOT EXISTS spotify_auth (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    refresh_token TEXT NOT NULL,
    connected_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS spotify_login (
    state      TEXT PRIMARY KEY,
    verifier   TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS music_favourite (
    position INTEGER PRIMARY KEY,
    id       TEXT NOT NULL,
    name     TEXT NOT NULL,
    cover    TEXT
);
-- Spotify's id for a device name that several devices share ("Apple TV"),
-- learnt while only one of them was listed.
CREATE TABLE IF NOT EXISTS music_device (
    name TEXT PRIMARY KEY,
    id   TEXT NOT NULL
);
-- Covers seen in Spotify's answers, by a short key; the image once fetched.
CREATE TABLE IF NOT EXISTS music_cover (
    key    TEXT PRIMARY KEY,
    url    TEXT NOT NULL,
    image  BLOB,
    colour TEXT
);
"""


class SpotifyError(Exception):
    """A short reason fit for the page; never a token."""

    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.status = status


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    music = cfg.get("music") or {}
    client_id = (music.get("client_id") or "").strip()
    return {"enabled": bool(client_id), "client_id": client_id,
            "redirect_uri": music.get("redirect_uri") or "",
            "default_device": music.get("default_device") or "",
            # How the page names it; Spotify calls every Apple TV "Apple TV".
            "default_label": music.get("default_label") or music.get("default_device") or ""}


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.executescript(TABLES)


# --- signing in ------------------------------------------------------------------------


def login_url(cfg: dict[str, Any], store: Store, now: float | None = None) -> str:
    """Where to send the browser; remembers the PKCE verifier for the callback."""
    s = settings(cfg)
    now = now or time.time()
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state = secrets.token_urlsafe(24)
    with store.connect() as conn:
        conn.execute("DELETE FROM spotify_login WHERE created_at < ?", (now - LOGIN_FOR,))
        conn.execute("INSERT INTO spotify_login (state, verifier, created_at) VALUES (?, ?, ?)",
                     (state, verifier, now))
    return f"{ACCOUNTS}/authorize?" + urlencode({
        "client_id": s["client_id"], "response_type": "code", "redirect_uri": s["redirect_uri"],
        "code_challenge_method": "S256", "code_challenge": challenge, "state": state,
        "scope": SCOPES})


def connected(store: Store) -> bool:
    with store.connect() as conn:
        return conn.execute("SELECT 1 FROM spotify_auth WHERE id = 1").fetchone() is not None


def disconnect(store: Store) -> None:
    with store.connect() as conn:
        conn.execute("DELETE FROM spotify_auth")
    CLIENT.forget()


# --- talking to Spotify ----------------------------------------------------------------


class Client:
    """Spotify for the one account: a short-lived access token in memory, the
    refresh token in the database, and short caches of read answers."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.transport = transport
        self.token: str | None = None
        self.token_until = 0.0
        self.cache: dict[str, tuple[float, Any]] = {}
        self.lock = asyncio.Lock()

    def forget(self) -> None:
        self.token, self.token_until, self.cache = None, 0.0, {}

    def http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=self.transport)

    async def finish_login(self, cfg: dict[str, Any], store: Store, code: str, state: str,
                           now: float | None = None) -> None:
        now = now or time.time()
        with store.connect() as conn:
            row = conn.execute("SELECT verifier, created_at FROM spotify_login WHERE state = ?",
                               (state,)).fetchone()
            conn.execute("DELETE FROM spotify_login WHERE state = ?", (state,))
        if row is None or row["created_at"] < now - LOGIN_FOR:
            raise SpotifyError("This sign-in link has expired; start again from Settings.", 400)
        s = settings(cfg)
        answer = await self._token(store, {
            "grant_type": "authorization_code", "code": code, "redirect_uri": s["redirect_uri"],
            "client_id": s["client_id"], "code_verifier": row["verifier"]}, now)
        if not answer.get("refresh_token"):
            raise SpotifyError("Spotify did not hand out a refresh token.")

    async def _token(self, store: Store, form: dict[str, str], now: float) -> dict[str, Any]:
        async with self.http() as http:
            resp = await http.post(f"{ACCOUNTS}/api/token", data=form)
        if resp.status_code == 400 and form["grant_type"] == "refresh_token":
            # invalid_grant: the access was revoked in Spotify's account settings.
            disconnect(store)
            raise SpotifyError("Spotify no longer accepts the hub; connect it again in Settings.",
                               401)
        if resp.status_code >= 400:
            raise SpotifyError(f"Spotify's sign-in answered {resp.status_code}")
        answer = resp.json()
        self.token = answer["access_token"]
        self.token_until = now + int(answer.get("expires_in", 3600)) - 60
        if answer.get("refresh_token"):  # Spotify may hand out a new one
            with store.connect() as conn:
                conn.execute(
                    "INSERT INTO spotify_auth (id, refresh_token, connected_at) VALUES (1, ?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET refresh_token = excluded.refresh_token",
                    (answer["refresh_token"], now))
        return answer

    async def _access(self, cfg: dict[str, Any], store: Store) -> str:
        async with self.lock:
            now = time.time()
            if self.token and now < self.token_until:
                return self.token
            with store.connect() as conn:
                row = conn.execute("SELECT refresh_token FROM spotify_auth WHERE id = 1").fetchone()
            if row is None:
                raise SpotifyError("Spotify is not connected; connect it in Settings → Music.", 401)
            await self._token(store, {"grant_type": "refresh_token",
                                      "refresh_token": row["refresh_token"],
                                      "client_id": settings(cfg)["client_id"]}, now)
            return self.token or ""

    async def call(self, cfg: dict[str, Any], store: Store, method: str, path: str,
                   params: dict[str, Any] | None = None, body: Any = None) -> Any:
        for attempt in (1, 2):
            token = await self._access(cfg, store)
            async with self.http() as http:
                resp = await http.request(method, f"{API}{path}", params=params, json=body,
                                          headers={"Authorization": f"Bearer {token}"})
            if resp.status_code == 401 and attempt == 1:
                self.token = None  # expired early: one fresh token, then give up
                continue
            break
        if resp.status_code == 429:
            raise SpotifyError("Spotify asks the hub to slow down; try again in a moment.", 429)
        if resp.status_code == 404 and "device" in resp.text.lower():
            raise SpotifyError("No active Spotify device; start one or pick a device.", 409)
        if resp.status_code == 403 and "premium" in resp.text.lower():
            raise SpotifyError("Playback control needs Spotify Premium.", 403)
        if resp.status_code >= 400:
            raise SpotifyError(f"Spotify answered {resp.status_code}")
        if resp.status_code == 204 or not resp.content:
            return None  # nothing playing, or a write that has no answer
        return resp.json()

    async def cached(self, cfg: dict[str, Any], store: Store, name: str, path: str,
                     params: dict[str, Any] | None = None) -> Any:
        # Only an answer actually fetched counts; monotonic time starts at boot,
        # so a missing entry must not look like one fetched at 0.
        if name in self.cache:
            at, value = self.cache[name]
            if time.monotonic() - at < FRESH[name]:
                return value
        value = await self.call(cfg, store, "GET", path, params)
        self.cache[name] = (time.monotonic(), value)
        return value

    def changed(self) -> None:
        """After a write, the next read asks Spotify again."""
        self.cache.pop("player", None)
        self.cache.pop("devices", None)


CLIENT = Client()


# --- covers ----------------------------------------------------------------------------


def _cover_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def main_colour(picture: Image.Image) -> str:
    """The cover's most vivid colour that is neither near black nor near white."""
    small = picture.convert("RGB").resize((48, 48))
    palette = small.quantize(colors=6).convert("RGB").getcolors(48 * 48) or []
    best, score = (124, 108, 242), -1.0
    for count, (r, g, b) in palette:
        _, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        if not 0.18 < light < 0.85:
            continue
        weight = sat * (count / (48 * 48)) ** 0.5
        if weight > score:
            best, score = (r, g, b), weight
    return "#{:02x}{:02x}{:02x}".format(*best)


def shrink(data: bytes) -> tuple[bytes, str]:
    with Image.open(io.BytesIO(data)) as raw:
        picture = ImageOps.exif_transpose(raw).convert("RGB")
    out = io.BytesIO()
    ImageOps.fit(picture, (COVER_SIZE, COVER_SIZE), Image.Resampling.LANCZOS).save(
        out, "WEBP", quality=80)
    return out.getvalue(), main_colour(picture)


# Spotify's image hosts; a cover from anywhere else is not fetched.
COVER_HOSTS = ("scdn.co", "spotifycdn.com")


def remember_cover(store: Store, url: str | None) -> str | None:
    """A key for a cover seen in an answer; the image is fetched on first use."""
    if not url:
        return None
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.scheme != "https" or not any(host == h or host.endswith("." + h)
                                          for h in COVER_HOSTS):
        return None
    key = _cover_key(url)
    with store.connect() as conn:
        conn.execute("INSERT OR IGNORE INTO music_cover (key, url) VALUES (?, ?)", (key, url))
    return key


async def cover(store: Store, key: str, transport: httpx.AsyncBaseTransport | None = None,
                ) -> tuple[bytes, str] | None:
    with store.connect() as conn:
        row = conn.execute("SELECT url, image, colour FROM music_cover WHERE key = ?",
                           (key,)).fetchone()
    if row is None:
        return None
    if row["image"] is None:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport) as http:
            resp = await http.get(row["url"])
            resp.raise_for_status()
        image, colour = await asyncio.to_thread(shrink, resp.content)
        with store.connect() as conn:
            conn.execute("UPDATE music_cover SET image = ?, colour = ? WHERE key = ?",
                         (image, colour, key))
        return image, colour
    return row["image"], row["colour"]


async def colour_of(store: Store, key: str | None,
                    transport: httpx.AsyncBaseTransport | None = None) -> str | None:
    if not key:
        return None
    try:
        found = await cover(store, key, transport)
    except Exception as exc:
        log.info("cover failed: %s", type(exc).__name__)
        return None
    return found[1] if found else None
