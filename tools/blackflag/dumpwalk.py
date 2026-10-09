# -*- coding: utf-8 -*-
"""Walk the crash dump: ebp chain, address->function map, shell references."""
import struct, sqlite3

P = r"C:\Users\Administrator\AppData\Local\CrashDumps\AC4BFSP.exe.25324.dmp"
DB = r"C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite"
data = open(P, "rb").read()

# --- load function address map from gamedb ---
con = sqlite3.connect(DB)
fun = []
for (name,) in con.execute("SELECT name FROM functions WHERE name LIKE 'FUN_%'"):
    h = name[4:]
    if len(h) == 8:
        try: fun.append((int(h, 16), name))
        except ValueError: pass
fun.sort()
addrs = [a for a, _ in fun]
print("functions loaded:", len(fun))

import bisect
def enclosing(addr):
    i = bisect.bisect_right(addrs, addr) - 1
    if i >= 0:
        return fun[i][1], addr - fun[i][0]
    return None, 0

# --- minidump helpers ---
def u32(o): return struct.unpack_from("<I", data, o)[0]
def u64(o): return struct.unpack_from("<Q", data, o)[0]
sig, ver, nstreams, str_rva = struct.unpack_from("<IIII", data, 0)
streams = {}
for i in range(nstreams):
    st, sz, rva = struct.unpack_from("<III", data, str_rva + i * 12)
    streams[st] = (sz, rva)
segs = []
if 5 in streams:
    _, rva = streams[5]
    n = u32(rva)
    for i in range(n):
        o = rva + 4 + i * 16
        st = u64(o); sz = struct.unpack_from("<I", data, o + 8)[0]; r = u32(o + 12)
        segs.append((st, sz, r))
if 9 in streams:
    _, rva = streams[9]
    n = u64(rva); brva = u64(rva + 8); off = brva
    for i in range(n):
        o = rva + 16 + i * 16
        st = u64(o); sz = u64(o + 8)
        segs.append((st, sz, off)); off += sz

def read_mem(addr, size):
    for st, sz, r in segs:
        if st <= addr < st + sz:
            take = min(size, st + sz - addr)
            return data[r + (addr - st): r + (addr - st) + take]
    return None

# --- ebp chain from crash frame ---
_, rva = streams[6]
ctx_rva = u32(rva + 8 + 152)
def creg(off): return u32(ctx_rva + off)
ebp = creg(0xB4); eip = creg(0xB8); esp = creg(0xC4)
print("crash eip=0x%08X enclose=%s" % (eip, enclosing(eip)))
print("--- frame chain ---")
cur = ebp
for depth in range(24):
    b = read_mem(cur, 8)
    if not b: 
        print("  [ebp=0x%08X] UNMAPPED" % cur); break
    saved_ebp, ret = struct.unpack("<II", b)
    fn, off = enclosing(ret)
    print("  frame %2d ebp=0x%08X ret=0x%08X  %s+0x%X" % (depth, cur, ret, fn, off))
    if saved_ebp <= cur or saved_ebp < 0x1000 or abs(saved_ebp - cur) > 0x10000: break
    cur = saved_ebp

# --- map earlier stack candidates ---
print("--- stack candidate mapping ---")
for a in [0x008C11F5,0x008AD828,0x00914000,0x008AF587,0x00924DAC,0x00A398F7,0x00AC6589,
          0x0081014C,0x01364D8A,0x005035A3,0x0092512F,0x009254A9,0x009253D7,0x00925664,
          0x00925C11,0x00925D87,0x0046FFD1,0x00406839,0x00A327A6,0x01E44518,0x00A1DB19,
          0x008165CE,0x00F1DE71,0x0081662E]:
    fn, off = enclosing(a)
    print("  0x%08X -> %s +0x%X" % (a, fn, off))

# --- find 0xFC739B30 occurrences ---
print("--- scan 0xFC739B30 (crash 'this') ---")
pat = struct.pack("<I", 0xFC739B30)
idx = 0
occs = []
while True:
    i = data.find(pat, idx)
    if i < 0: break
    occs.append(i); idx = i + 1
print("occurrences:", len(occs), [hex(o) for o in occs[:20]])
# map file offset to virtual address
def off_to_va(off):
    for st, sz, r in segs:
        if r <= off < r + sz:
            return st + (off - r)
    return None
for o in occs[:10]:
    va = off_to_va(o)
    b = read_mem((va or 0) - 32, 96)
    print("  off=%s va=%s" % (hex(o), hex(va) if va else "?"))
    if b: print("    ctx:", b.hex(" "))

# --- shell ptr refs: shell17 twice, shell9 once ---
print("--- shell pointer contexts ---")
for nm, a in [("shell17", 0x30602770), ("shell9", 0x30601EF0), ("shell3", 0x3157FE10)]:
    pat = struct.pack("<I", a)
    idx = 0
    while True:
        i = data.find(pat, idx)
        if i < 0: break
        idx = i + 1
        va = off_to_va(i)
        print("  %s 0x%08X: off=0x%X va=%s" % (nm, a, i, hex(va) if va else "?"))
        ctx = read_mem((va or 0) - 16, 48) if va else None
        if ctx: print("     ctx±: ", ctx.hex(" "))
