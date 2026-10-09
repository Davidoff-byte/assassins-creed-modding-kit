# -*- coding: utf-8 -*-
"""Analyze the AC4BFSP crash dump (x86 minidump): exception, registers, stack, shells."""
import struct, sys, os

P = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Administrator\AppData\Local\CrashDumps\AC4BFSP.exe.25324.dmp"
data = open(P, "rb").read()
print("dump size:", len(data))

def u32(o): return struct.unpack_from("<I", data, o)[0]
def u64(o): return struct.unpack_from("<Q", data, o)[0]

# header
sig, ver, nstreams, str_rva = struct.unpack_from("<IIII", data, 0)
print("sig:", data[:4], "streams:", nstreams)
streams = {}
for i in range(nstreams):
    st, sz, rva = struct.unpack_from("<III", data, str_rva + i * 12)
    streams[st] = (sz, rva)
print("stream types:", sorted(streams.keys()))

# modules
mods = []
if 4 in streams:
    _, rva = streams[4]
    n = u32(rva)
    for i in range(n):
        o = rva + 4 + i * 108
        base = u64(o); size = u32(o + 8); name_rva = u32(o + 20)
        ln = u32(name_rva) if name_rva else 0
        name = data[name_rva + 4:name_rva + 4 + ln].decode("utf-16-le", "replace") if name_rva else "?"
        mods.append((base, size, name))
        print("MOD 0x%08X-0x%08X %s" % (base, base + size, name))

def mod_of(addr):
    for b, s, n in mods:
        if b <= addr < b + s:
            return "%s+0x%X" % (n, addr - b)
    return None

# memory segments (list + 64)
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
    n = u64(rva); brva = u64(rva + 8)
    off = brva
    for i in range(n):
        o = rva + 16 + i * 16
        st = u64(o); sz = u64(o + 8)
        segs.append((st, sz, off)); off += sz
print("memory segments:", len(segs))

def read_mem(addr, size):
    for st, sz, r in segs:
        if st <= addr < st + sz:
            take = min(size, st + sz - addr)
            return data[r + (addr - st): r + (addr - st) + take], take
    return None, 0

# exception
if 6 in streams:
    _, rva = streams[6]
    tid = u32(rva); 
    code = u32(rva + 8); flags = u32(rva + 12)
    exc_addr = u64(rva + 24); nparam = u32(rva + 32)
    params = [u64(rva + 40 + 8 * i) for i in range(min(nparam, 15))]
    ctx_size = u32(rva + 8 + 152); ctx_rva = u32(rva + 12 + 152)
    print("EXC tid=%d code=0x%X flags=0x%X addr=0x%08X params=%s" % (tid, code, flags, exc_addr, [hex(p) for p in params[:3]]))
    print("EXC addr -> %s" % (mod_of(exc_addr) or "?"))
    # x86 context
    def creg(off): return u32(ctx_rva + off)
    regs = dict(eip=creg(0xB8), esp=creg(0xC4), ebp=creg(0xB4), edi=creg(0x9C), esi=creg(0xA0),
                ebx=creg(0xA4), edx=creg(0xA8), ecx=creg(0xAC), eax=creg(0xB0), efl=creg(0xC0))
    print("REGS: " + " ".join("%s=0x%08X" % (k, v) for k, v in regs.items()))
    print("eip -> %s" % (mod_of(regs["eip"]) or "?"))
    # read at edi/esi/ecx/edx/ebp/esp
    for rn in ["edi", "esi", "ebx", "ecx", "edx", "ebp"]:
        b, got = read_mem(regs[rn], 48)
        if b:
            print("MEM[%s=0x%08X]: %s" % (rn, regs[rn], b.hex(" ")))
        else:
            print("MEM[%s=0x%08X]: UNMAPPED" % (rn, regs[rn]))
    # stack walk
    b, got = read_mem(regs["esp"], 0x300)
    if b:
        print("--- STACK (esp..+0x300) ---")
        for i in range(0, min(got, 0x300) - 3, 4):
            v = struct.unpack_from("<I", b, i)[0]
            ann = mod_of(v)
            if ann and "AC4BFSP" in ann or (ann and "PatchFix" in ann):
                print("  [esp+0x%03X] 0x%08X  %s" % (i, v, ann))
    else:
        print("stack unmapped")
    # scan counts
    print("--- scans ---")
    for name, v in [("def_default 0x1ED02078", 0x1ED02078), ("worldmgr 0x4626FD00", 0x4626FD00),
                    ("recycled 0x4626EEA0", 0x4626EEA0), ("old_worldmgr 0x388AD0C0", 0x388AD0C0)]:
        pat = struct.pack("<I", v)
        print("%s: %d occurrences" % (name, data.count(pat)))
    # shell memory contents
    print("--- shell memory ---")
    shells = {3: 0x3157FE10, 9: 0x30601EF0, 10: 0x30602000, 11: 0x30602110, 12: 0x30602220,
              13: 0x30602330, 17: 0x30602770, 4: 0x33E0F810, 22: 0x2B16E0D0}
    for idx, a in shells.items():
        b, got = read_mem(a, 0xF0)
        if b:
            print("shell[%d] 0x%08X: %s" % (idx, a, b[:0xF0].hex(" ")))
        else:
            print("shell[%d] 0x%08X: UNMAPPED" % (idx, a))
else:
    print("no exception stream")
