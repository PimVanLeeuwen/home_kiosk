"""Install the hub's firmware on a panel now, instead of at night (main/update.c).

    panels/.venv/bin/python panels/tools/update.py /dev/cu.usbmodem…

Opening the port restarts the panel on macOS, so this waits until the panel
has the hub's answer (as shot.py does), types "update" on its console and
follows the log until the new firmware has reached the hub, or the panel says
why not.
"""

import re
import sys
import time

from shot import open_link

DONE = (b"reached the hub: kept", b"is the newest", b"offers no firmware", b"failed", b"stopped at",
        b"back to the previous one")


def main(port: str) -> None:
    link = open_link(port)
    link.write(b"update\n")
    log, deadline = b"", time.time() + 300
    while time.time() < deadline:
        log += link.read(4096)
        lines = re.sub(rb"\x1b\[[0-9;]*m", b"", log).splitlines()
        if any(done in line for line in lines for done in DONE) and log.endswith(b"\n"):
            break
    for line in re.sub(rb"\x1b\[[0-9;]*m", b"", log).decode("utf-8", "replace").splitlines():
        if " update: " in line or "panel: board" in line:
            print(line.strip())


if __name__ == "__main__":
    main(sys.argv[1])
