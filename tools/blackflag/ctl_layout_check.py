#!/usr/bin/env python3
"""READ-ONLY layout check: player vs Edward anim ctl fields.

For player + each Edward: locate ctl=u32(ent+0xE8), dump vt and header fields,
region ctl+0x8C0..0x910, and request slots ctl+0x2F40..0x2F80. Re-read after a
delay and print byte-level changes. NO WRITES.
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
DELAY = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)
if not h:
    raise SystemExit('OpenProcess failed')


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


VT = struct.pack('<I', 0x01E4CE90)
mbi = MBI()
addr = 0x10000
edwards = []
player = 0
while addr < 0x7FFF0000 and len(edwards) < 8:
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
                        if ch == 32 and cnt == 34:
                            player = a
                        if ch == 29 and cnt == 32:
                            edwards.append(a)
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

targets = [('player', player)] + [('edw%d' % i, e) for i, e in enumerate(edwards[:4])]
state = {}

def sample(tag, ent):
    ctl = u32(ent + 0xE8)
    out = {'ctl': ctl}
    if ctl:
        out['vt'] = u32(ctl)
        out['h4'] = u32(ctl + 4)
        out['h8'] = u32(ctl + 8)
        out['hc'] = u32(ctl + 0xC)
        out['h18'] = u32(ctl + 0x18)
        out['r8c0'] = rd(ctl + 0x8C0, 0x58)   # 0x8C0..0x918
        out['slots'] = rd(ctl + 0x2F40, 0x48)  # 0x2F40..0x2F88
    return out


for tag, ent in targets:
    print('== %s ent=0x%08X' % (tag, ent))
    o = sample(tag, ent)
    print('   ctl=0x%08X vt=0x%08X +4=0x%08X +8=0x%08X +C=0x%08X +18=0x%08X' % (
        o.get('ctl', 0), o.get('vt', 0), o.get('h4', 0), o.get('h8', 0),
        o.get('hc', 0), o.get('h18', 0)))
    r = o.get('r8c0')
    if r:
        print('   +8C0: %s' % r[:0x20].hex().upper())
        print('   +8E0: %s' % r[0x20:0x40].hex().upper())
        print('   +900: %s' % r[0x40:].hex().upper())
    sl = o.get('slots')
    if sl:
        print('   slots2F40: %s' % ','.join('%08X' % v for v in struct.unpack('<18I', sl)))
    state[tag] = o

print('--- waiting %.1fs ---' % DELAY)
time.sleep(DELAY)

print('--- changes ---')
for tag, ent in targets:
    o2 = sample(tag, ent)
    o1 = state[tag]
    for key in ('vt', 'h4', 'h8', 'hc', 'h18'):
        if o1.get(key) != o2.get(key):
            print('%s %s: 0x%08X -> 0x%08X' % (tag, key, o1.get(key, 0), o2.get(key, 0)))
    for key in ('r8c0', 'slots'):
        a = o1.get(key); b = o2.get(key)
        if a and b and a != b:
            base = 0x8C0 if key == 'r8c0' else 0x2F40
            i = 0
            while i < min(len(a), len(b)):
                if a[i] != b[i]:
                    j = i
                    while j < min(len(a), len(b)) and a[j] != b[j]:
                        j += 1
                    print('%s %s+0x%03X [%d] %s > %s' % (
                        tag, key, base + i, j - i, a[i:j].hex().upper(), b[i:j].hex().upper()))
                    i = j
                else:
                    i += 1
print('done')
