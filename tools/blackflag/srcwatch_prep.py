#!/usr/bin/env python3
"""READ-ONLY: find a hot dword in the SRC skeleton pose array of a live NPC.

Walks: mover NPC -> c14 (vt 0x01E41E58) -> A = *(c14+0x138) (src skeleton)
       -> pose = *(A+0xa4); churn-sample pose[0..0x400] twice, print HOT <addr>.

Usage: srcwatch_prep.py <pid>
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
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


def u16(a):
    b = rd(a, 2)
    return struct.unpack('<H', b)[0] if b else 0


def f3(a):
    b = rd(a, 12)
    return struct.unpack('<fff', b) if b else None


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", ctypes.c_ulong), ("RegionSize", ctypes.c_size_t),
                ("State", ctypes.c_ulong), ("Protect", ctypes.c_ulong), ("Type", ctypes.c_ulong)]


VT = struct.pack('<I', 0x01E4CE90)
mbi = MBI()
addr = 0x10000
chars = []
while addr < 0x7FFF0000:
    if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        break
    base = mbi.BaseAddress or 0
    size = mbi.RegionSize
    if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x08, 0x40, 0x80):
        off = 0
        while off < size:
            n = min(1024 * 1024, size - off)
            b = rd(base + off, n)
            if b:
                j = b.find(VT)
                while j >= 0:
                    a = base + off + j
                    blob = rd(a, 0x100)
                    if blob and len(blob) >= 0xF0:
                        cnt, ch = struct.unpack_from('<HH', blob, 0x64)
                        if 16 <= ch <= 40 and cnt <= 64:
                            chars.append(a)
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

p0 = {a: f3(a + 0x40) for a in chars}
time.sleep(0.8)
scored = []
for a in chars:
    p = f3(a + 0x40)
    q = p0.get(a)
    if p and q:
        d = ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5
        scored.append((d, a))
scored.sort(reverse=True)

for d, a in scored[:15]:
    kb = u32(a + 0x60)
    cnt = u16(a + 0x66)
    c14 = None
    for i in range(min(cnt, 48)):
        k = u32(kb + i * 4)
        if u32(k) == 0x01E41E58:
            c14 = k
            break
    if not c14:
        continue
    A = u32(c14 + 0x138)
    B = u32(c14 + 0x134)
    C = u32(c14 + 0x144)
    pose = u32(A + 0xa4) if A else 0
    print('npc=0x%08X moved=%.1f c14=0x%08X A=0x%08X B=0x%08X C=0x%08X poseA=0x%08X' % (
        a, d, c14, A, B, C, pose))
    if not pose:
        continue
    b1 = rd(pose, 0x400)
    if not b1:
        continue
    time.sleep(0.15)
    b2 = rd(pose, 0x400)
    if not b2:
        continue
    best = []
    for off in range(0, 0x400, 4):
        ch = sum(1 for i in range(4) if b1[off + i] != b2[off + i])
        if ch:
            best.append((ch, pose + off))
    best.sort(reverse=True)
    print('   pose churn dwords=%d top=%s' % (len(best), best[:5]))
    if best and best[0][0] >= 3:
        print('HOT 0x%08X' % best[0][1])
        sys.exit(0)
print('NO HOT DWORD')
sys.exit(1)
