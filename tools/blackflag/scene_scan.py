#!/usr/bin/env python3
"""Scan a live AC4BFSP process for Entity-class objects (vt 0x01E4CE90) near a position.

Usage: python scene_scan.py <pid> [px py] [maxdist]
Defaults: around the Havana docks (103,-73.5), radius 120.

Reports character-like entities (ch>=16, f7c==-0.5) and any entity carrying a
registration block at +0xC8 - which is where world key pairs live.
"""
import ctypes
import math
import struct
import sys
import time

pid = int(sys.argv[1])
px = float(sys.argv[2]) if len(sys.argv) > 2 else 103.0
py = float(sys.argv[3]) if len(sys.argv) > 3 else -73.5
maxd = float(sys.argv[4]) if len(sys.argv) > 4 else 120.0

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)
if not h:
    print("OpenProcess failed:", k32.GetLastError())
    sys.exit(1)


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", ctypes.c_ulong), ("RegionSize", ctypes.c_size_t),
                ("State", ctypes.c_ulong), ("Protect", ctypes.c_ulong), ("Type", ctypes.c_ulong)]


def read(addr, size):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    return buf.raw[:got.value] if ok else None


VT = struct.pack('<I', 0x01E4CE90)
mbi = MBI()
addr = 0x10000
total = 0
hits = []
t0 = time.time()
while addr < 0x7FFF0000:
    if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        break
    base = mbi.BaseAddress or 0
    size = mbi.RegionSize
    if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x08, 0x40, 0x80):
        off = 0
        while off < size:
            n = min(1024 * 1024, size - off)
            b = read(base + off, n)
            if b:
                total += len(b)
                j = b.find(VT)
                while j >= 0:
                    hits.append(base + off + j)
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

print("scanned %.1f MB in %.1fs; vt hits: %d" % (total / 1048576.0, time.time() - t0, len(hits)))

chars = []
for a in hits:
    blob = read(a, 0x100)
    if not blob or len(blob) < 0xF0:
        continue
    pos = struct.unpack_from('<fff', blob, 0x40)
    if not all(-9000 < v < 9000 for v in pos) or all(v == 0 for v in pos):
        continue
    f7c = struct.unpack_from('<f', blob, 0x7C)[0]
    ch = struct.unpack_from('<H', blob, 0x66)[0]
    cnt = struct.unpack_from('<H', blob, 0x64)[0]
    d = math.hypot(pos[0] - px, pos[1] - py)
    if d > maxd:
        continue
    f50 = struct.unpack_from('<I', blob, 0x50)[0]
    w5C = struct.unpack_from('<I', blob, 0x5C)[0]
    fAC = struct.unpack_from('<I', blob, 0xAC)[0]
    reg = struct.unpack_from('<I', blob, 0xC8)[0]
    ctl = struct.unpack_from('<I', blob, 0xE8)[0]
    inner = None
    if reg >= 0x10000:
        rb = read(reg, 0x20)
        if rb:
            inner = rb
    chars.append((d, a, pos, ch, f7c, cnt, f50, w5C, fAC, reg, ctl, inner))

alls = len(chars)
chars = [c for c in chars if c[3] >= 16 and abs(c[4] + 0.5) < 0.05]
chars.sort(key=lambda c: c[0])
print("character-like within %.0f m: %d total vt-hits, %d full chars (ch>=16, f7c=-0.5)" % (maxd, alls, len(chars)))
for d, a, pos, ch, f7c, cnt, f50, w5C, fAC, reg, ctl, inner in chars[:80]:
    keytxt = ""
    if inner:
        d1 = struct.unpack_from('<IIIIIII', inner, 0)
        # common layout guess: try to spot key-like pair (second dword small, first arbitrary)
        lo, hi = d1[3], d1[4]
        keytxt = " reg[%08X %08X %08X | %08X %08X | %08X %08X]" % d1[:7]
    print(" d=%5.1f m 0x%08X ch=%-3d f7c=%5.2f cnt=%-2d pos=(%.1f,%.1f,%.1f)" % (
        d, a, ch, f7c, cnt, pos[0], pos[1], pos[2]))
    print("      f50=0x%08X w5C=0x%08X fAC=0x%08X reg=0x%08X ctl=0x%08X%s" % (
        f50, w5C, fAC, reg, ctl, keytxt))

# second pass: every full char with a large component count (Edward-body candidates)
big = [c for c in chars if c[5] >= 26]
print("=== chars with cnt>=26 anywhere within range: %d ===" % len(big))
for d, a, pos, ch, f7c, cnt, f50, w5C, fAC, reg, ctl, inner in big:
    regtxt = ""
    if inner:
        d1 = struct.unpack_from('<IIIIIII', inner, 0)
        regtxt = " key=%08X : %08X" % (d1[3], d1[4])
    print(" cnt=%-3d ch=%-3d 0x%08X pos=(%.1f,%.1f,%.1f) f50=0x%08X%s" % (
        cnt, ch, a, pos[0], pos[1], pos[2], f50, regtxt))
