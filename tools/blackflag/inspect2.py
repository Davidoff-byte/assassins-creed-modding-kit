#!/usr/bin/env python3
"""Find the player entity (ch32/cnt34), read its controller (+0xE8), then diff
the player-ctl vtable against the crowd-behavior vtable (0x026E34D8)."""
import ctypes
import sqlite3
import struct
import sys

pid = int(sys.argv[1])
CROWD_VT = 0x026E34D8

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok else None


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", ctypes.c_ulong), ("RegionSize", ctypes.c_size_t),
                ("State", ctypes.c_ulong), ("Protect", ctypes.c_ulong), ("Type", ctypes.c_ulong)]


VT = struct.pack('<I', 0x01E4CE90)
mbi = MBI()
addr = 0x10000
player = None
while addr < 0x7FFF0000:
    if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        break
    base = mbi.BaseAddress or 0
    size = mbi.RegionSize
    if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x08, 0x40, 0x80):
        off = 0
        while off < size and player is None:
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
                            break
                    j = b.find(VT, j + 4)
            off += n
        if player:
            break
    addr = base + size

print('player entity: 0x%08X' % player if player else 'player not found')
if not player:
    sys.exit(0)

blob = rd(player, 0x100)
pos = struct.unpack_from('<fff', blob, 0x40)
e8 = struct.unpack_from('<I', blob, 0xE8)[0]
print('player pos=(%.1f,%.1f,%.1f) ctl=0x%08X' % (*pos, e8))
pv = rd(e8, 4)
pvt = struct.unpack('<I', pv)[0] if pv else 0
print('player ctl vt = 0x%08X  (crowd vt = 0x%08X)' % (pvt, CROWD_VT))

db = sqlite3.connect(r'C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite')
cur = db.cursor()


def resolve(a):
    cur.execute("SELECT name, file_id, start_line FROM functions WHERE name=?",
                ('FUN_%08x' % a,))
    r = cur.fetchone()
    return r


if pvt:
    pb = rd(pvt, 0x100)
    cb = rd(CROWD_VT, 0x100)
    if pb and cb:
        for i in range(0, 0x100, 4):
            p = struct.unpack_from('<I', pb, i)[0]
            c = struct.unpack_from('<I', cb, i)[0]
            mark = '  <<< DIFF' if p != c else ''
            if p != c:
                rp = resolve(p)
                rc = resolve(c)
                print('slot +%03X player=%08X%s crowd=%08X%s%s' % (
                    i, p, (' [%s]' % rp[0]) if rp else '', c,
                    (' [%s]' % rc[0]) if rc else '', mark))
