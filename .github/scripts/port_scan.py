"""TCP connect scan of the home IP from outside the house (exposure-scan workflow).

    port_scan.py HOST             scan every TCP port, print the result as JSON
    port_scan.py --error MESSAGE  print a failed result instead

The JSON (stdout) is what the hub's POST /api/exposure/scan takes; a one-line
summary for the workflow log goes to stderr. Standard library only.
The house needs no open port at all (Tandoor and CouchDB go through a Cloudflare
tunnel, which connects outward), so every open port is reported.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime

PORTS = range(1, 65536)
CONCURRENCY = 800
TIMEOUT_SECONDS = 2.0  # a home router drops unwanted packets, so most ports time out


async def is_open(host: str, port: int, slots: asyncio.Semaphore) -> bool:
    async with slots:
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(host, port),
                                               TIMEOUT_SECONDS)
        except (OSError, TimeoutError):
            return False
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass
        return True


async def scan(host: str) -> list[int]:
    slots = asyncio.Semaphore(CONCURRENCY)
    answers = await asyncio.gather(*(is_open(host, port, slots) for port in PORTS))
    return [port for port, answered in zip(PORTS, answers, strict=True) if answered]


def result(started: datetime, open_ports: list[int], checked: int,
           error: str | None = None) -> str:
    return json.dumps({"started": started.isoformat(), "finished": datetime.now(UTC).isoformat(),
                       "ports_checked": checked, "open": open_ports, "error": error})


def main(argv: list[str]) -> int:
    started = datetime.now(UTC)
    if len(argv) == 3 and argv[1] == "--error":
        print(result(started, [], 0, argv[2][:300]))
        print(f"Not scanned: {argv[2]}", file=sys.stderr)
        return 0
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    open_ports = asyncio.run(scan(argv[1]))
    print(result(started, open_ports, len(PORTS)))
    print(f"{len(open_ports)} open of {len(PORTS)} ports checked", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
