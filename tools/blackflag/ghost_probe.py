#!/usr/bin/env python3
"""READ-ONLY: check the ghost body's anim state (children, c14, pose churn).

Usage: ghost_probe.py <pid> <ent_hex>
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
ent = int(sys.argv[2], 16)
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


def churn(a, n=0x200, dt=0.15):
    b1 = rd(a, n)
    if not b1:
        return None
    time.sleep(dt)
    b2 = rd(a, n)
    if not b2:
        return None
    best = []
    for off in range(0, n, 4):
        ch = sum(1 for i in range(4) if b1[off + i] != b2[off + i])
        if ch:
            best.append((ch, a + off))
    best.sort(reverse=True)
    return best


vt = u32(ent)
cnt, ch = struct.unpack('<HH', rd(ent + 0x64, 4))
kb = u32(ent + 0x60)
ctl = u32(ent + 0xE8)
print('ent=0x%08X vt=0x%08X ch=%d cnt=%d ctl=0x%08X pos=%s' % (
    ent, vt, ch, cnt, ctl, f3(ent + 0x40)))
kids = [u32(kb + i * 4) for i in range(min(cnt, 48))]
for i, k in enumerate(kids):
    if k:
        kv = u32(k)
        marks = []
        if kv == 0x01E41E58:
            marks.append('c14-walkchild')
        if kv == 0x026E34D8:
            marks.append('crowd-ctl')
        if marks:
            print('  child[%d] 0x%08X vt=0x%08X %s' % (i, k, kv, ','.join(marks)))
        if kv == 0x01E41E58:
            for off in (0x134, 0x138, 0x140, 0x144):
                skel = u32(k + off)
                if not skel:
                    continue
                pose = u32(skel + 0xa4)
                res = churn(pose) if pose else None
                top = ('%d dwords, top %s' % (len(res), res[:3])) if res else 'no churn'
                print('     c14+0x%X skel=0x%08X mode=%d pose=0x%08X -> %s' % (
                    off, skel, u32(skel + 0x90), pose, top))
# also the ctl header anim region
a = rd(ctl + 0x8C0, 0x40)
if a:
    for row in range(0, 0x40, 0x10):
        print('  ctl+%03X: %s' % (0x8C0 + row, ' '.join('%08X' % struct.unpack_from('<I', a, row + k * 4)[0] for k in range(4))))
