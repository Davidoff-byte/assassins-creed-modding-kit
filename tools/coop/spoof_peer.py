#!/usr/bin/env python3
"""Spoof a peer position so the game's HijackAvatar moves a donor NPC there (solo test).

Sends Player packets (same format as fake_peer) to the game's LocalPort. Point the game's
[Coop] RemotePort at a different port (e.g. LocalPort=27701, RemotePort=27700) so the game
doesn't also receive its own sends.

  python spoof_peer.py 1084 424 6            # stand a donor at (1084,424,6)
  python spoof_peer.py 1084 424 6 --radius 8 --seconds 60
"""
from __future__ import annotations

import argparse
import math
import os
import socket
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_peer as fp  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("x", type=float)
    ap.add_argument("y", type=float)
    ap.add_argument("z", type=float)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=27701, help="the game's LocalPort")
    ap.add_argument("--hz", type=float, default=20.0)
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--radius", type=float, default=6.0)
    a = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    n = max(1, int(a.seconds * a.hz))
    dt = 1.0 / a.hz
    t0 = time.time()
    for i in range(1, n + 1):
        t = i * dt
        px = a.x + a.radius * math.cos(t)
        pz = a.z + a.radius * math.sin(t)
        body = struct.pack(
            fp.PLAYER,
            px, a.y, pz,
            0.0, 0.0, 0.0, 1.0,
            0.0, 0.0, 0.0,
            100.0, 0, int(t * 1000.0), 0,
        )
        sock.sendto(fp.tag(dict(type=fp.MSG_PLAYER, seq=i, client_id=7)) + body,
                    (a.host, a.port))
        time.sleep(dt)
    print(f"sent {n} spoofed peer positions to {a.host}:{a.port} "
          f"(center {a.x},{a.y},{a.z}, radius {a.radius}, {time.time()-t0:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
