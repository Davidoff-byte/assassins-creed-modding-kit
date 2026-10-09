#!/usr/bin/env python3
"""READ-ONLY: locate player + Edward bodies and their skeleton addresses.

Usage: anim_objects.py <pid>
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

for a in chars:
    ch = u16(a + 0x64)
    if ch not in (29, 32):
        continue
    cnt = u16(a + 0x66)
    kb = u32(a + 0x60)
    ctl = u32(a + 0xE8)
    c14 = None
    for i in range(min(cnt, 48)):
        k = u32(kb + i * 4)
        if u32(k) == 0x01E41E58:
            c14 = k
            break
    tag = 'PLAYER' if ch == 32 else 'EDWARD'
    print('== %s ent=0x%08X ch=%d cnt=%d ctl=0x%08X c14=%s pos=%s ==' % (
        tag, a, ch, cnt, ctl, ('0x%08X' % c14) if c14 else 'NONE', f3(a + 0x40)))
    if c14:
        for off in (0x134, 0x138, 0x140, 0x144):
            skel = u32(c14 + off)
            if skel:
                print('   c14+0x%X skel=0x%08X mode=%d pose=0x%08X hier=0x%08X' % (
                    off, skel, u32(skel + 0x90), u32(skel + 0xa4), u32(skel + 0xa0)))
