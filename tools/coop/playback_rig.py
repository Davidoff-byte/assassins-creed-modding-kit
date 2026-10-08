#!/usr/bin/env python3
"""AccCoop A3 rig: prove the remote-playback algorithm offline, on a real captured walk.

Takes a `fake_peer.py --listen` capture (the in-game samples), replays it through two
playback strategies at render rate, optionally under packet loss + jitter, and reports
smoothness (jerk) and coverage. No game required.

  naive  : draw the most recent snapshot as-is (what you get with no interpolation)
  interp : render `delay` in the past and interpolate between the two bracketing snapshots,
           extrapolating by up to `max_extrap` when a snapshot is missing

Usage:
  python tools/playback_rig.py tools/listen_capture.log [--loss 0.1] [--jitter-ms 30]
"""
from __future__ import annotations

import argparse
import math
import re
import sys

POS = re.compile(r"seq=(\d+).*?pos=\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)"
                 r".*?quat=\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)")


def load(path: str):
    raw = open(path, "rb").read()
    text = raw.decode("utf-16", errors="ignore") if (raw[:2] in (b"\xff\xfe", b"\xfe\xff")
             or b"\x00" in raw[:128]) else raw.decode("utf-8", errors="ignore")
    snaps = []
    for line in text.splitlines():
        m = POS.search(line)
        if m:
            g = [float(m.group(i)) for i in range(1, 9)]
            snaps.append(g)  # seq,x,y,z,qx,qy,qz,qw
    return snaps


def slerp(a, b, t):
    d = sum(x * y for x, y in zip(a, b))
    if d < 0:
        b = [-y for y in b]
        d = -d
    if d > 0.9995:
        r = [x + t * (y - x) for x, y in zip(a, b)]
    else:
        th0 = math.acos(max(-1.0, min(1.0, d)))
        th = th0 * t
        s0 = math.sin(th0 - th) / math.sin(th0)
        s1 = math.sin(th) / math.sin(th0)
        r = [x * s0 + y * s1 for x, y in zip(a, b)]
    n = math.sqrt(sum(c * c for c in r)) or 1.0
    return [c / n for c in r]


def playback(times, pos, quat, dt_render, delay, max_extrap, extrapolate):
    """Return per-render positions. Render proceeds forward; state arrives at `times`."""
    out = []
    idx = 0
    n = len(times)
    t = times[0]
    end = times[-1]
    while t <= end:
        rt = t - delay
        while idx + 1 < n and times[idx + 1] <= rt:
            idx += 1
        if rt <= times[0]:
            out.append(pos[0])
        elif rt >= times[idx]:
            if extrapolate and rt - times[idx] <= max_extrap and idx + 1 < n:
                span = times[idx + 1] - times[idx] or dt_render
                a = min(1.0, (rt - times[idx]) / span)
                out.append([p + a * (q - p) for p, q in zip(pos[idx], pos[idx + 1])])
            else:
                out.append(pos[idx])
        else:
            j = max(0, idx)
            span = times[j + 1] - times[j] or dt_render
            a = (rt - times[j]) / span
            out.append([p + a * (q - p) for p, q in zip(pos[j], pos[j + 1])])
        t += dt_render
    return out


def jerk(positions, dt):
    """Max change in per-frame velocity (m/s^2-ish); lower is smoother."""
    worst = 0.0
    prev_v = None
    for a, b in zip(positions, positions[1:]):
        v = [(y - x) / dt for x, y in zip(a, b)]
        if prev_v is not None:
            worst = max(worst, math.dist(v, prev_v))
        prev_v = v
    return worst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("capture")
    ap.add_argument("--loss", type=float, default=0.0, help="packet loss fraction")
    ap.add_argument("--jitter-ms", type=float, default=0.0)
    ap.add_argument("--delay-ms", type=float, default=100.0)
    ap.add_argument("--max-extrap-ms", type=float, default=150.0)
    ap.add_argument("--render-hz", type=float, default=60.0)
    ap.add_argument("--window", default=None, help="index slice start:end for a clean segment")
    a = ap.parse_args()

    snaps = load(a.capture)
    if a.window:
        s, e = a.window.split(":")
        snaps = snaps[int(s):int(e)]
    if len(snaps) < 20:
        print(f"not enough samples ({len(snaps)})")
        return 1

    import random
    random.seed(7)
    base_dt = 0.05  # 20 Hz sender
    times, pos, quat = [], [], []
    t = 0.0
    for k, s in enumerate(snaps):
        # arrival time = send time + jitter
        arr = k * base_dt + (random.uniform(-a.jitter_ms, a.jitter_ms) / 1000.0 if a.jitter_ms else 0.0)
        if a.loss and random.random() < a.loss:
            continue
        if times and arr <= times[-1]:
            arr = times[-1] + 1e-4
        times.append(arr)
        pos.append(s[1:4])
        quat.append(s[4:8])

    dt_render = 1.0 / a.render_hz
    delay = a.delay_ms / 1000.0
    max_extrap = a.max_extrap_ms / 1000.0

    naive = playback(times, pos, quat, dt_render, 0.0, 0.0, False)
    interp = playback(times, pos, quat, dt_render, delay, max_extrap, True)

    print(f"samples: {len(snaps)} -> delivered {len(times)}  "
          f"(loss {a.loss:.0%}, jitter {a.jitter_ms:.0f}ms, delay {a.delay_ms:.0f}ms)")
    print(f"renders @ {a.render_hz:.0f}Hz: {len(naive)}")
    print(f"jerk  naive : {jerk(naive, dt_render):10.1f}")
    print(f"jerk  interp: {jerk(interp, dt_render):10.1f}   "
          f"(lower is smoother; ratio {jerk(naive, dt_render)/max(1e-9, jerk(interp, dt_render)):.1f}x)")

    # coverage: fraction of renders whose velocity is finite (no frozen-forever)
    def frozen_runs(seq):
        runs, cur = [], 0
        for x, y in zip(seq, seq[1:]):
            if all(abs(c - d) < 1e-6 for c, d in zip(x, y)):
                cur += 1
            else:
                if cur:
                    runs.append(cur)
                cur = 0
        if cur:
            runs.append(cur)
        return max(runs) if runs else 0
    print(f"longest frozen run  naive={frozen_runs(naive)}  interp={frozen_runs(interp)} frames")
    return 0


if __name__ == "__main__":
    sys.exit(main())
