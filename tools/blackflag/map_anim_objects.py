#!/usr/bin/env python3
"""Map anim request objects -> characters (read-only).

For every char entity found: print entity, vt, ch/cnt, pos, the behavior ctl
(ent+0xE8), the request object [[ctl+0x18]+0xC], its slots at +0x2F50..0x2F64,
and the live fields at ctl+0x8D0..0x8E8. Lets us resolve the `this=` values
seen in the AnimApply/AnimWrite probe logs to actual characters.
"""
import ctypes
import struct
import sys

pid = int(sys.argv[1])
k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok else None


def u32(a):
    b = rd(a, 4)
    return struct.unpack('<I', b)[0] if b and len(b) == 4 else 0


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", ctypes.c_ulong), ("RegionSize", ctypes.c_size_t),
                ("State", ctypes.c_ulong), ("Protect", ctypes.c_ulong), ("Type", ctypes.c_ulong)]


VT = struct.pack('<I', 0x01E4CE90)
mbi = MBI()
addr = 0x10000
chars = []
while addr < 0x7FFF0000 and len(chars) < 400:
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
                        if ch >= 16 and cnt >= 16:
                            chars.append((a, ch, cnt))
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

print('chars:', len(chars))
for a, ch, cnt in sorted(chars, key=lambda x: (-x[2], x[1])):
    pos = rd(a + 0x40, 12)
    p = struct.unpack('<fff', pos) if pos and len(pos) == 12 else (0, 0, 0)
    vt = u32(a)
    ctl = u32(a + 0xE8)
    req = 0
    if 0x10000 <= ctl < 0x7FFF0000:
        o1 = u32(ctl + 0x18)
        if 0x10000 <= o1 < 0x7FFF0000:
            req = u32(o1 + 0xC)
    slots = '-'
    if 0x10000 <= req < 0x7FFF0000:
        sl = rd(req + 0x2F50, 24)
        if sl and len(sl) == 24:
            slots = ','.join('%08X' % v for v in struct.unpack('<6I', sl))
    live = '-'
    if 0x10000 <= ctl < 0x7FFF0000:
        lv = rd(ctl + 0x8D0, 0x18)
        if lv and len(lv) == 0x18:
            live = lv.hex().upper()
    print('ent=0x%08X vt=0x%08X ch=%d cnt=%d pos=(%.1f,%.1f,%.1f)' % (a, vt, ch, cnt, *p))
    print('   ctl=0x%08X req=0x%08X slots=%s' % (ctl, req, slots))
    print('   live8D0=%s' % live)
print('done')
