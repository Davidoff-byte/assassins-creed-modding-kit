#!/usr/bin/env python3
"""READ-ONLY: find vtables containing given function addresses.

Scans readable data regions (skips RX code) for each function dword, walks back
while entries are code pointers to find the vtable base, and reports
(base, slot_index). Resolves slots' names via the gamedb sqlite index if present.

Usage: vt_find.py <pid> <funcaddr_hex> [more...]
"""
import ctypes
import struct
import sqlite3
import sys

pid = int(sys.argv[1])
vals = [int(x, 16) for x in sys.argv[2:]]
k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok and g.value == n else None


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", ctypes.c_ulong), ("RegionSize", ctypes.c_size_t),
                ("State", ctypes.c_ulong), ("Protect", ctypes.c_ulong), ("Type", ctypes.c_ulong)]


def is_code(v):
    return 0x400000 <= v <= 0x6F00000


DB = r"C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite"
try:
    con = sqlite3.connect(DB)
    cur = con.cursor()
except Exception:
    cur = None


def name_of(v):
    if not cur:
        return ''
    for fmt in ('FUN_%08x', 'FUN_%08X'):
        r = cur.execute("SELECT name FROM functions WHERE name=?", (fmt % v,)).fetchone()
        if r:
            return r[0]
    return ''


regions = []
mbi = MBI()
addr = 0x10000
while addr < 0x7FFF0000:
    if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        break
    base = mbi.BaseAddress or 0
    size = mbi.RegionSize
    if mbi.State == 0x1000 and mbi.Protect in (0x02, 0x04, 0x08, 0x40, 0x80):
        regions.append((base, size, mbi.Protect, mbi.Type))
    addr = base + size

print('data regions: %d' % len(regions))

for v in vals:
    pat = struct.pack('<I', v)
    hits = []
    for base, size, prot, typ in regions:
        off = 0
        while off < size:
            n = min(1 << 20, size - off)
            b = rd(base + off, n)
            if b:
                j = b.find(pat)
                while j >= 0:
                    hits.append(base + off + j)
                    j = b.find(pat, j + 4)
            off += n
    print()
    print('=== %s 0x%08X   hits=%d ===' % (name_of(v), v, len(hits)))
    shown = 0
    for hh in hits:
        # walk back to vtable base
        base = hh
        for _ in range(256):
            prev = rd(base - 4, 4)
            if not prev:
                break
            pv = struct.unpack('<I', prev)[0]
            if is_code(pv):
                base -= 4
            else:
                break
        # verify forward run
        run = 0
        a = base
        while run < 512:
            b4 = rd(a, 4)
            if not b4:
                break
            if not is_code(struct.unpack('<I', b4)[0]):
                break
            run += 1
            a += 4
        if run >= 8:
            slot = (hh - base) // 4
            print('  vtable~0x%08X slot=0x%02X (dword slot %.0f) run=%d  [%s]' % (
                base, slot, slot, run, name_of(v)))
        else:
            print('  raw hit @0x%08X (no vtable run)' % hh)
        shown += 1
        if shown >= 12:
            print('  ... (%d more)' % (len(hits) - shown))
            break
