#!/usr/bin/env python3
"""READ-ONLY: decode c14 flags/basis for the driven ghost vs real walkers.

Usage: decode_flags.py <pid> <ghost_ent_hex>
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
ghost = int(sys.argv[2], 16)
k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok and g.value == n else None


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


def show(tag, ent):
    kb = u32(ent + 0x60)
    cnt = u16(ent + 0x66)
    c14 = None
    for i in range(min(cnt, 48)):
        k = u32(kb + i * 4)
        if u32(k) == 0x01E41E58:
            c14 = k
            break
    if not c14:
        print('%s ent=0x%08X: no c14' % (tag, ent))
        return
    fl = u16(c14 + 0x88)
    mode_lo = (fl >> 3) & 7
    mode_hi = (fl >> 6) & 7
    print('%s ent=0x%08X c14=0x%08X flags=0x%04X bits9=%d mode3-5=%d mode6-8=%d '
          'b336=0x%02X speed(e+0x70)=%.3f c14+0x100=%.3f basis=(%.4f,%.4f,%.4f | %.4f,%.4f,%.4f | %.4f,%.4f)' % (
              tag, ent, c14, fl, (fl >> 9) & 1, mode_lo, mode_hi,
              u32(c14 + 0x336) & 0xFF, f32(ent + 0x70), f32(c14 + 0x100),
              f32(c14 + 0x150), f32(c14 + 0x154), f32(c14 + 0x158),
              f32(c14 + 0x15C), f32(c14 + 0x160), f32(c14 + 0x164),
              f32(c14 + 0x168), f32(c14 + 0x16C)))


show('GHOST  ', ghost)

# find walkers + standers for comparison
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

p0 = {a: f3(a + 0x40) for a in chars}
time.sleep(0.9)
show_w, show_s = [], []
for a in chars:
    if a == ghost:
        continue
    p = f3(a + 0x40)
    q = p0.get(a)
    if not p or not q:
        continue
    d = ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 / 0.9
    if d > 0.8:
        show_w.append(a)
    elif d < 0.02:
        show_s.append(a)
for a in show_w[:3]:
    show('WALKER ', a)
for a in show_s[:2]:
    show('STANDER', a)
