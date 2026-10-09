#!/usr/bin/env python3
"""READ-ONLY: find objects that reference given skeleton addresses.

Candidate object layouts looked for:
  - blend-pair:  [obj+0x10C] == S1 and [obj+0x110] == S2   (FUN_0067B420-like)
  - timed-blend: [obj+0x1B0] == S                              (anim skel)
  - node refs:   [obj+0x94/0x98/0x9C] == S                     (scene node trio)

Usage: refscan.py <pid> <addr_hex> [addr_hex...]
"""
import ctypes
import math
import struct
import sys

pid = int(sys.argv[1])
skels = [int(x, 16) for x in sys.argv[2:]]
k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok and g.value == n else None


def u32(a):
    b = rd(a, 4)
    return struct.unpack('<I', b)[0] if b else 0


def f32(a):
    b = rd(a, 4)
    return struct.unpack('<f', b)[0] if b else float('nan')


def in_module(v):
    return 0x400000 <= v <= 0xF30000


class M(ctypes.Structure):
    _fields_ = [('b', ctypes.c_void_p), ('ab', ctypes.c_void_p), ('ap', ctypes.c_ulong),
                ('rs', ctypes.c_size_t), ('st', ctypes.c_ulong), ('pr', ctypes.c_ulong),
                ('ty', ctypes.c_ulong)]


def scan_for(v):
    needle = struct.pack('<I', v)
    hits = []
    m = M()
    addr = 0x10000
    while addr < 0x7FFF0000:
        if not k32.VirtualQueryEx(ctypes.c_void_p(h), ctypes.c_void_p(addr), ctypes.byref(m), ctypes.sizeof(m)):
            break
        base = m.b or 0
        size = m.rs
        if m.st == 0x1000 and m.pr in (4, 8, 0x40, 0x80):
            off = 0
            while off < size:
                n = min(1 << 20, size - off)
                b = rd(base + off, n)
                if b:
                    j = b.find(needle)
                    while j >= 0:
                        hits.append(base + off + j)
                        j = b.find(needle, j + 4)
                off += n
        addr = base + size
    return hits


def dump_cand(obj, tag):
    vt = u32(obj)
    if not in_module(vt):
        return
    w = f32(obj + 8)
    w4 = f32(obj + 4)
    st = u32(obj + 0xFC)
    s10c = u32(obj + 0x10C)
    s110 = u32(obj + 0x110)
    s1b0 = u32(obj + 0x1B0)
    t1b4 = f32(obj + 0x1B4)
    dur = f32(obj + 0x14)
    p7c = u32(obj + 0x7C)
    print('  %s obj=0x%08X vt=0x%08X w(+8)=%.3f w(+4)=%.3f state=0x%X | +10C=0x%08X +110=0x%08X | +1B0=0x%08X t=%.2f dur=%.2f | +7C=0x%08X' % (
        tag, obj, vt, w, w4, st, s10c, s110, s1b0, t1b4, dur, p7c))


for S in skels:
    print('==== refs to skel 0x%08X ====' % S)
    hits = scan_for(S)
    print('  raw hits: %d' % len(hits))
    seen = set()
    for H in hits:
        # blend-pair where H is at +0x10C or +0x110
        for base_off in (0x10C, 0x110):
            obj = H - base_off
            if obj in seen:
                continue
            if in_module(u32(obj)):
                s10c = u32(obj + 0x10C)
                s110 = u32(obj + 0x110)
                if s10c and s110 and s10c != s110:
                    seen.add(obj)
                    dump_cand(obj, 'PAIR')
        # timed-blend where H is at +0x1B0
        obj = H - 0x1B0
        if obj not in seen and in_module(u32(obj)) and u32(obj + 0x1B0) == S:
            seen.add(obj)
            dump_cand(obj, 'TIMED')
        # scene node trio where H at +0x94/0x98/0x9C
        for base_off in (0x94, 0x98, 0x9C):
            obj = H - base_off
            if obj in seen:
                continue
            if in_module(u32(obj)):
                trio = [u32(obj + 0x94), u32(obj + 0x98), u32(obj + 0x9C)]
                if sum(1 for t in trio if 0x10000 < t < 0xFF000000) >= 2:
                    seen.add(obj)
                    dump_cand(obj, 'NODE')
    if not seen:
        print('  (no validated candidates)')
