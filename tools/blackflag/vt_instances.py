#!/usr/bin/env python3
"""READ-ONLY: find live objects whose vtable pointer == given address(es).

Scans readable regions for each vtable dword; prints object address, owner
ch/cnt if the object looks like an entity/component, and a small dump.
Usage: vt_instances.py <pid> <vtaddr_hex> [more...]
"""
import ctypes
import struct
import sys

pid = int(sys.argv[1])
vts = [int(x, 16) for x in sys.argv[2:]]
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


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", ctypes.c_ulong), ("RegionSize", ctypes.c_size_t),
                ("State", ctypes.c_ulong), ("Protect", ctypes.c_ulong), ("Type", ctypes.c_ulong)]


mbi = MBI()
regions = []
addr = 0x10000
while addr < 0x7FFF0000:
    if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        break
    base = mbi.BaseAddress or 0
    size = mbi.RegionSize
    if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x08, 0x40, 0x80):
        regions.append((base, size))
    addr = base + size

for vt in vts:
    pat = struct.pack('<I', vt)
    hits = []
    for base, size in regions:
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
    print('=== vt=0x%08X  live instances: %d ===' % (vt, len(hits)))
    for hh in hits[:24]:
        head = rd(hh, 0x40)
        print('  obj=0x%08X  head: %s' % (hh, head.hex().upper() if head else '-'))
        # try entity-ish owner at +4/+8
        for off in (4, 8, 0xC):
            v = u32(hh + off)
            if 0x10000 <= v <= 0x7FFF0000:
                b = rd(v, 0x100)
                if b and len(b) >= 0xF0:
                    cnt, ch = struct.unpack_from('<HH', b, 0x64)
                    if 1 <= ch <= 64 and cnt >= 1:
                        print('      +0x%X -> 0x%08X (ch=%d cnt=%d entity-like)' % (off, v, ch, cnt))
    print()
