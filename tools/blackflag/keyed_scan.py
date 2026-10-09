#!/usr/bin/env python3
"""Scan a live AC4BFSP process for world-key registry entries (keyed entities).

Usage: python keyed_scan.py <pid> [lo:hi ...]
Defaults: the two persistent Havana dock characters (0xF00056E0:0, 0xF000570A:0).

Registry entry layout (32-bit): entry = pair_addr - 0xC, 0x14 bytes:
  {ptr, rc, flags(0x8000000x), keyLo, keyHi}
Entity fields (vt 0x01E4CE90): +0x40 pos, +0x50 def-slot, +0x5C world link,
  +0x66 ch, +0x7C f7c (-0.5 body), +0xAC fAC, +0xE8 controller.
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
raw_keys = sys.argv[2:] or ["F00056E0:0", "F000570A:0"]
keys = []
for k in raw_keys:
    a, b = k.split(":")
    keys.append((int(a, 16), int(b, 16)))

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)  # QUERY_INFORMATION | VM_READ
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


def read_u32(addr):
    b = read(addr, 4)
    return struct.unpack('<I', b)[0] if b and len(b) == 4 else None


def read_f32(addr):
    b = read(addr, 4)
    return struct.unpack('<f', b)[0] if b and len(b) == 4 else None


pats = [(k, struct.pack('<II', k[0], k[1])) for k in keys]
mbi = MBI()
addr = 0x10000
total = 0
matches = {}
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
                for k, pat in pats:
                    j = b.find(pat)
                    while j >= 0:
                        matches.setdefault(k, []).append(base + off + j)
                        j = b.find(pat, j + 1)
            off += n
    addr = base + size

print("scanned %.1f MB in %.1fs" % (total / 1048576.0, time.time() - t0))
for k, addrs in matches.items():
    print("key %08X:%X -> %d raw hit(s)" % (k[0], k[1], len(addrs)))
    seen = set()
    for pair_addr in addrs[:80]:
        rec = read(pair_addr - 0xC, 0x14)
        if not rec:
            continue
        ptr, rc, flags, lo, hi = struct.unpack('<IIIII', rec)
        if (lo, hi) != k or ptr in seen:
            continue
        seen.add(ptr)
        pos = read(ptr + 0x40, 12)
        x, y, z = struct.unpack('<fff', pos) if pos and len(pos) == 12 else (0.0, 0.0, 0.0)
        chb = read(ptr + 0x66, 2)
        ch = struct.unpack('<H', chb)[0] if chb and len(chb) == 2 else -1
        f7c = read_f32(ptr + 0x7C)
        vt = read_u32(ptr)
        f50 = read_u32(ptr + 0x50)
        w5C = read_u32(ptr + 0x5C)
        fAC = read_u32(ptr + 0xAC)
        ctl = read_u32(ptr + 0xE8)
        print("  entity 0x%08X rc=%d flags=0x%08X pos=(%.1f,%.1f,%.1f) ch=%d f7c=%s" % (
            ptr, rc, flags, x, y, z, ch, f7c))
        print("     vt=0x%08X f50=0x%08X w5C=0x%08X fAC=0x%08X ctl=0x%08X" % (
            vt or 0, f50 or 0, w5C or 0, fAC or 0, ctl or 0))
