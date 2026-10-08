#!/usr/bin/env python3
"""AccCoop M1 oracle: stand-in for the in-game plugin, no game required.

Layouts must match ../common/coop_proto.h.  Modes:
  --selftest            pack/unpack round-trip for every message type + a simulated stream
  --loopback            real UDP sockets to ourselves, mixing message types
  --listen [--port N]   bind UDP and print decoded messages
  --send   [--port N]   transmit synthetic player states (default 20 Hz)

Examples:
  python fake_peer.py --selftest
  python fake_peer.py --listen --port 27700                       # terminal 1
  python fake_peer.py --send   --port 27700 --id 1                # terminal 2
"""
from __future__ import annotations

import argparse
import math
import struct
import sys
import time

MAGIC = 0x50524341  # 'ACRP'
VERSION = 1

MSG_PLAYER = 1
MSG_ENTITIES = 2
MSG_EVENT = 3

FLAG_VALID = 1 << 0
FLAG_ALIVE = 1 << 1
FLAG_ON_SHIP = 1 << 2
FLAG_CROUCH = 1 << 3
FLAG_IN_COMBAT = 1 << 4
FLAG_FROZEN = 1 << 5

EV_KILL, EV_KNOCKOUT, EV_DAMAGE, EV_ALARM = 1, 2, 3, 4
EV_BOARD, EV_ENTER_SHIP, EV_EXIT_SHIP, EV_SPAWN, EV_DESPAWN = 5, 6, 7, 8, 9

ENV = "<IHHII"        # magic, version, type, seq, client_id             -> 16
PLAYER = "<11fIII"    # px py pz, quat xyzw, vx vy vz, health, anim, tick, ack -> 56
ENT_HDR = "<HHI"      # count, flags, host_tick                         -> 8
ENT = "<IffffIHH"     # id, x y z yaw, anim_state, flags, pad           -> 28
EVT = "<HHIf"         # kind, arg, target_id, arg_f                     -> 12

assert struct.calcsize(ENV) == 16 and struct.calcsize(PLAYER) == 56
assert struct.calcsize(ENT_HDR) == 8 and struct.calcsize(ENT) == 28 and struct.calcsize(EVT) == 12

PLAYER_BYTES = 16 + 56
EVENT_BYTES = 16 + 12


def tag(msg: dict) -> bytes:
    return struct.pack(ENV, MAGIC, VERSION, msg["type"], msg["seq"], msg["client_id"])


def player(cid: int, seq: int, t: float) -> bytes:
    r = 1200.0
    ang = t * 0.7 + cid
    half = ang * 0.5
    body = struct.pack(
        PLAYER,
        r * math.cos(ang), 0.0, r * math.sin(ang),   # position
        0.0, math.sin(half), 0.0, math.cos(half),    # quaternion (rotation about Y, placeholder)
        -r * 0.7 * math.sin(ang), 0.0, r * 0.7 * math.cos(ang),  # velocity
        100.0, 0, int(t * 1000.0), 0,                # health, anim, tick, ack
    )
    return tag(dict(type=MSG_PLAYER, seq=seq, client_id=cid)) + body


def entities(cid: int, seq: int, ents: list[dict]) -> bytes:
    hdr = struct.pack(ENT_HDR, len(ents), 0, int(time.time() * 1000) & 0xFFFFFFFF)
    body = b"".join(struct.pack(ENT, e["id"], e["x"], e["y"], e["z"], e["yaw"],
                                e["anim"], e["flags"], 0) for e in ents)
    return tag(dict(type=MSG_ENTITIES, seq=seq, client_id=cid)) + hdr + body


def event(cid: int, seq: int, kind: int, target: int, arg: float = 0.0, argi: int = 0) -> bytes:
    body = struct.pack(EVT, kind, argi, target, arg)
    return tag(dict(type=MSG_EVENT, seq=seq, client_id=cid)) + body


def decode(datagram: bytes) -> dict:
    if len(datagram) < 16:
        raise ValueError("short envelope")
    magic, ver, mtype, seq, cid = struct.unpack(ENV, datagram[:16])
    if magic != MAGIC or ver != VERSION:
        raise ValueError(f"bad header magic={magic:#x} ver={ver}")
    msg = dict(type=mtype, seq=seq, client_id=cid)
    p = datagram[16:]
    if mtype == MSG_PLAYER:
        assert len(p) == 56, len(p)
        (px, py, pz, qx, qy, qz, qw, vx, vy, vz, hp, anim, tick, ack) = struct.unpack(PLAYER, p)
        msg.update(px=px, py=py, pz=pz, qx=qx, qy=qy, qz=qz, qw=qw,
                   vx=vx, vy=vy, vz=vz, health=hp, anim_state=anim, tick_ms=tick, ack_seq=ack)
    elif mtype == MSG_ENTITIES:
        count, flags, host_tick = struct.unpack(ENT_HDR, p[:8])
        assert len(p) == 8 + count * 28, (len(p), count)
        ents = []
        for i in range(count):
            (eid, x, y, z, yaw, anim, eflags, _pad) = struct.unpack(ENT, p[8 + i * 28: 8 + i * 28 + 28])
            ents.append(dict(id=eid, x=x, y=y, z=z, yaw=yaw, anim=anim, flags=eflags))
        msg.update(count=count, host_tick=host_tick, entities=ents)
    elif mtype == MSG_EVENT:
        assert len(p) == 12, len(p)
        kind, argi, target, argf = struct.unpack(EVT, p)
        msg.update(kind=kind, argi=argi, target_id=target, arg_f=argf)
    else:
        raise ValueError(f"unknown type {mtype}")
    return msg


def selftest() -> int:
    # player round-trip
    d = player(7, 1, 1.25)
    assert len(d) == PLAYER_BYTES, len(d)
    m = decode(d)
    assert m["type"] == MSG_PLAYER and m["client_id"] == 7 and m["seq"] == 1
    assert abs(m["px"] - (-25.220)) < 0.01 and abs(m["health"] - 100.0) < 1e-3
    assert abs((m["qx"] ** 2 + m["qy"] ** 2 + m["qz"] ** 2 + m["qw"] ** 2) - 1.0) < 1e-4
    print(f"[ok] player 72 B: pos=({m['px']:.1f},{m['py']:.1f},{m['pz']:.1f}) "
          f"quat=({m['qx']:.3f},{m['qy']:.3f},{m['qz']:.3f},{m['qw']:.3f})")

    # entities round-trip
    ents = [dict(id=1000 + i, x=float(i), y=0.0, z=float(-i), yaw=float(i * 15),
                 anim=i, flags=FLAG_VALID | FLAG_ALIVE) for i in range(4)]
    d = entities(1, 2, ents)
    m = decode(d)
    assert m["type"] == MSG_ENTITIES and m["count"] == 4
    assert m["entities"][2]["id"] == 1002 and m["entities"][3]["yaw"] == 45.0
    print(f"[ok] entities {len(d)} B: {m['count']} entities, id[2]={m['entities'][2]['id']}")

    # event round-trip
    d = event(1, 3, EV_KILL, target=4242, arg=100.0, argi=0)
    assert len(d) == EVENT_BYTES, len(d)
    m = decode(d)
    assert m["type"] == MSG_EVENT and m["kind"] == EV_KILL and m["target_id"] == 4242
    print(f"[ok] event 28 B: kind=Kill target={m['target_id']}")

    # simulated mixed stream
    got = 0
    for i in range(1, 41):
        for cid in (1, 2):
            decode(player(cid, i, i / 20.0)); got += 1
        decode(entities(1, i, ents)); got += 1
        decode(event(2, i, EV_DAMAGE, 1000 + (i % 4), arg=12.5)); got += 1
    print(f"[ok] simulated stream: {got} messages decoded")
    print("[ok] M1 oracle passed")
    return 0


def loopback(port: int) -> int:
    import socket
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("127.0.0.1", port))
    rx.settimeout(2.0)
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    out = [player(42, 1, 0.05), player(42, 2, 0.10),
           entities(42, 3, [dict(id=9, x=1.0, y=2.0, z=3.0, yaw=0.0, anim=0, flags=3)]),
           event(42, 4, EV_KILL, target=9)]
    for d in out:
        tx.sendto(d, ("127.0.0.1", port))
    seen = 0
    try:
        while seen < len(out):
            buf, _ = rx.recvfrom(65536)
            decode(buf)
            seen += 1
    except socket.timeout:
        print(f"[fail] got {seen}/{len(out)} before timeout")
        return 1
    print(f"[ok] real-socket loopback: {seen}/{len(out)} mixed messages, all valid")
    return 0


def send(port: int, host: str, cid: int, hz: float, seconds: float) -> int:
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dt = 1.0 / hz
    n = max(1, int(seconds * hz))
    for i in range(1, n + 1):
        sock.sendto(player(cid, i, i * dt), (host, port))
        time.sleep(dt)
    print(f"[ok] sent {n} player packets to {host}:{port} as client {cid}")
    return 0


def listen(port: int) -> int:
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", port))
    print(f"[ok] listening on udp/{port}; Ctrl-C to stop")
    try:
        while True:
            buf, addr = sock.recvfrom(65536)
            try:
                m = decode(buf)
            except (ValueError, AssertionError) as e:
                print(f"[skip] {addr}: {e}")
                continue
            if m["type"] == MSG_PLAYER:
                print(f"[{m['client_id']}] PLAYER seq={m['seq']:<6} "
                      f"pos=({m['px']:8.1f},{m['py']:7.1f},{m['pz']:8.1f}) "
                      f"quat=({m['qx']:.2f},{m['qy']:.2f},{m['qz']:.2f},{m['qw']:.2f}) "
                      f"hp={m['health']:.0f} from {addr[0]}")
            elif m["type"] == MSG_ENTITIES:
                print(f"[{m['client_id']}] ENTITIES seq={m['seq']} n={m['count']} from {addr[0]}")
            else:
                print(f"[{m['client_id']}] EVENT seq={m['seq']} kind={m['kind']} "
                      f"target={m['target_id']} from {addr[0]}")
    except KeyboardInterrupt:
        print("\n[ok] stopped")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="AccCoop M1 oracle")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--loopback", action="store_true")
    ap.add_argument("--listen", action="store_true")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=27700)
    ap.add_argument("--id", type=int, default=1, dest="cid")
    ap.add_argument("--hz", type=float, default=20.0)
    ap.add_argument("--seconds", type=float, default=3.0)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.loopback:
        return loopback(a.port)
    if a.listen:
        return listen(a.port)
    if a.send:
        return send(a.port, a.host, a.cid, a.hz, a.seconds)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
