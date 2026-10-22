"""Save a panel's screen as a PNG over the USB serial console (main/devshot.c).

    panels/.venv/bin/python panels/tools/shot.py /dev/cu.usbmodem… out.png [screen]

The panel starts on its first screen; `screen` (1, 2, ...) turns to a later one
first. Either way the screen is held while it is captured.

The panel sends numbered base64 lines, each with a CRC32. Other parts of the
firmware can print in between and break a line, so the good lines are kept
and the panel is asked again for the missing ones (up to five times).
"""

import base64
import re
import struct
import sys
import time
import zlib

import serial
from PIL import Image

LINE = re.compile(r"L(\d+) ([A-Za-z0-9+/]+={0,2}) ([0-9a-f]{8})")


def open_link(port: str) -> serial.Serial:
    # The board's reset and boot pins hang on RTS and DTR: keep both released.
    link = serial.Serial(None, 921600, timeout=1)
    link.port, link.dtr, link.rts = port, False, False
    link.open()
    # On macOS opening the port resets the panel all the same: wait until it has
    # the hub's answer (its "clock set" line), or for a long quiet moment if it did not.
    started, quiet_since = time.time(), time.time()
    while time.time() - started < 30:
        line = link.readline()
        if line:
            quiet_since = time.time()
            if b"clock set from the hub" in line:
                time.sleep(2)  # let the screen draw the answer
                break
        elif time.time() - quiet_since > 10:  # Wi-Fi retries can leave the log quiet for seconds
            break
    return link


def one_transfer(link: serial.Serial, chunks: dict[int, bytes]) -> tuple[int, int, int, int] | None:
    """One screenshot: read in large blocks (line by line loses lines here) and
    keep the lines whose checksum matches."""
    link.reset_input_buffer()
    link.write(b"shot\n")
    raw, deadline = b"", time.time() + 60
    while time.time() < deadline and b"\nEND" not in raw:
        raw += link.read(8192)
    header = None
    for line in raw.decode("ascii", "replace").splitlines():
        line = line.strip()
        if line.startswith("SHOT "):
            header = tuple(int(n) for n in line.split()[1:5])
        elif header and (m := LINE.fullmatch(line)):
            data = base64.b64decode(m.group(2))
            if zlib.crc32(data) == int(m.group(3), 16):
                chunks[int(m.group(1))] = data
    return header


def main(port: str, out: str, screen: int = 0) -> None:
    link = open_link(port)
    # Hold the screen (as a touch does) or turn to the one asked for, then let it fade in.
    # One turn at a time: the panel ignores a "next" while it is still turning.
    for _ in range(max(screen, 1)):
        link.write(b"hold\n" if screen == 0 else b"next\n")
        time.sleep(1.5)
    # Lines per screen (its header): only transfers of the very same screen are merged.
    seen: dict[tuple[int, int, int, int], dict[int, bytes]] = {}
    header = None
    for attempt in range(1, 9):
        chunks: dict[int, bytes] = {}
        header = one_transfer(link, chunks)
        if not header:
            continue
        merged = seen.setdefault(header, {})
        merged.update(chunks)
        if len(merged) == header[3]:
            break
        print(f"transfer {attempt}: {header[3] - len(merged)} of {header[3]} lines still missing")
    else:
        sys.exit("no complete screen from the panel")
    chunks = seen[header]
    width, height, size, lines = header
    raw = b"".join(chunks[i] for i in range(lines))
    if len(raw) != size:
        sys.exit(f"got {len(raw)} of {size} bytes")
    pixels = bytearray()
    for count, b, g, r in struct.iter_unpack("<HBBB", raw):
        pixels += bytes((r, g, b)) * count
    Image.frombytes("RGB", (width, height), bytes(pixels)).save(out)
    print(f"saved {out} ({width} x {height}, {size} bytes over the wire)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 0)
