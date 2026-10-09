#!/usr/bin/env python3
"""CONTROLLED test: set the 'moving' flag (c14+0x88 bit9) on ONE standing crowd NPC,
watch it for a few seconds, then restore the original value.

Safety: single 2-byte flag field on a random crowd NPC; original value restored.
Never targets the player (ch32) or Edwards (ch29).

Usage: flagtest.py <pid>
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)
k32.WriteProcessMemory.restype = ctypes.c_bool


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok and g.value == n else None


def wr2(a, v):
    b = struct.pack('<H', v & 0xFFFF)
    g = ctypes.c_size_t(0)
    return k32.WriteProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, 2, ctypes.byref(g))


def u16(a):
    b = rd(a, 2)
    return struct.unpack('<H', b)[0] if b else 0


def u32(a):
    b = rd(a, 4)
    return struct.unpack('<I', b)[0] if b else 0


def f3(a):
    b = rd(a, 12)
    return struct.unpack('<fff', b) if b else None


def f32(a):
    b = rd(a, 4)
    return struct.unpack('<f', b)[0] if b else 0.0


class M(ctypes.Structure):
    _fields_ = [('b', ctypes.c_void_p), ('ab', ctypes.c_void_p), ('ap', ctypes.c_ulong),
                ('rs', ctypes.c_size_t), ('st', ctypes.c_ulong), ('pr', ctypes.c_ulong),
                ('ty', ctypes.c_ulong)]


m = M()
addr = 0x10000
chars = []
vt = struct.pack('<I', 0x01E4CE90)
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
                j = b.find(vt)
                while j >= 0:
                    a = base + off + j
                    blob = rd(a, 0x100)
                    if blob and len(blob) >= 0xF0:
                        cnt, ch = struct.unpack_from('<HH', blob, 0x64)
                        if 16 <= ch <= 40 and cnt <= 64:
                            chars.append(a)
                    j = b.find(vt, j + 4)
            off += n
    addr = base + size

# player pos for proximity
pl = None
for a in chars:
    if u16(a + 0x64) == 32:
        pl = f3(a + 0x40)
        if pl:
            break

def dist(a):
    p = f3(a + 0x40)
    if not p or not pl:
        return 1e9
    return ((p[0] - pl[0]) ** 2 + (p[1] - pl[1]) ** 2) ** 0.5

subj = []
for a in chars:
    ch = u16(a + 0x64)
    if ch in (29, 32):
        continue
    kb = u32(a + 0x60)
    cnt = u16(a + 0x66)
    c14 = None
    for i in range(min(cnt, 48)):
        k = u32(kb + i * 4)
        if u32(k) == 0x01E41E58:
            c14 = k
            break
    if c14:
        subj.append((dist(a), a, c14))
subj.sort()
# pick a stander: sample speed twice
def speed2(a, dt=0.6):
    p0 = f3(a + 0x40)
    time.sleep(dt)
    p1 = f3(a + 0x40)
    if not p0 or not p1:
        return 99.0
    return ((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2) ** 0.5 / dt

test = None
for d, a, c14 in subj[:12]:
    s = speed2(a)
    if s < 0.05:
        test = (d, a, c14)
        break
if not test:
    print('no standing NPC found')
    sys.exit(1)
d, a, c14 = test
flag_addr = c14 + 0x88
old = u16(flag_addr)
print('TEST NPC ent=0x%08X c14=0x%08X dist=%.1f pos=%s' % (a, c14, d, f3(a + 0x40)))
print('before: c14+0x88=0x%04X  ent+0x70=%.3f  c14+0x100=%.3f' % (old, f32(a + 0x70), f32(c14 + 0x100)))

# baseline pose churn (idle)
def pose_churn(n=0x200, dt=0.3):
    pose = u32(u32(c14 + 0x134) + 0xa4)
    if not pose:
        return -1
    b1 = rd(pose, n)
    time.sleep(dt)
    b2 = rd(pose, n)
    if not b1 or not b2:
        return -1
    return sum(1 for i in range(n) if b1[i] != b2[i])

print('idle pose churn: %d bytes/0.3s' % pose_churn())

ok = wr2(flag_addr, old | 0x200)
print('SET bit9 (%s): 0x%04X -> 0x%04X' % ('ok' if ok else 'FAILED', old, u16(flag_addr)))
t0 = time.time()
while time.time() - t0 < 8.0:
    time.sleep(0.8)
    print('  t=%.1f flag=0x%04X pos=%s speed~%.2f posechurn=%d' % (
        time.time() - t0, u16(flag_addr), f3(a + 0x40), speed2(a, 0.4), pose_churn(0x200, 0.2)))
wr2(flag_addr, old)
print('restored: 0x%04X (now 0x%04X)' % (old, u16(flag_addr)))
