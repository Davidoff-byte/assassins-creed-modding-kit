#!/usr/bin/env python3
"""READ-ONLY Edward tree watcher.

Finds a walking Edward (ch29/cnt32), byte-diffs its entity + ctl + all children
across a WALK window and a STAND window, then summarizes changed offsets.
Pure reads - no writes anywhere.

Usage: edw_tree_watch.py <pid> [walk_sec] [stand_sec] [out_file]
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
DUR_WALK = float(sys.argv[2]) if len(sys.argv) > 2 else 14.0
DUR_STAND = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
OUT = sys.argv[4] if len(sys.argv) > 4 else (
    r"C:\Users\Administrator\Documents\Default Project\bf-coop\edw_tree_diff.txt")

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)
if not h:
    raise SystemExit('OpenProcess failed')


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    if not ok or g.value != n:
        return None
    return b.raw


def rd_buf(a, n):
    """Chunked read; zero-fill unreadable chunks."""
    out = bytearray(n)
    ok_any = False
    off = 0
    while off < n:
        m = min(0x1000, n - off)
        b = rd(a + off, m)
        if b:
            out[off:off + m] = b
            ok_any = True
        off += m
    return bytes(out) if ok_any else None


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
edwards = []
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
                    if blob:
                        cnt, ch = struct.unpack_from('<HH', blob, 0x64)
                        if ch == 29 and cnt == 32:
                            edwards.append(a)
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

print('edwards:', ['0x%08X' % e for e in edwards], flush=True)
for e in edwards:
    print('  0x%08X pos=%s' % (e, f3(e + 0x40)), flush=True)


def snap_regions(ent):
    regs = []
    b = rd_buf(ent, 0x400)
    if b:
        regs.append(('ent', ent, b))
    ctl = u32(ent + 0xE8)
    if ctl and 0x10000 <= ctl < 0x7FFF0000:
        cb = rd_buf(ctl, 0x3400)
        if cb:
            regs.append(('ctl', ctl, cb))
    cnt = u16(ent + 0x66)
    if 1 <= cnt <= 60:
        listp = rd(ent + 0x60, cnt * 4)
        if listp:
            for i in range(min(cnt, 40)):
                ch = struct.unpack_from('<I', listp, i * 4)[0]
                if not (0x10000 <= ch < 0x7FFF0000):
                    continue
                cb = rd_buf(ch, 0x1000)
                if cb:
                    regs.append(('c%02d' % i, ch, cb))
    return regs


def diff_window(tag, ent, dur, out):
    base = snap_regions(ent)
    prev = {name: data for (name, _, data) in base}
    t0 = time.time()
    moves = 0
    lastpos = None
    changes = {}
    while time.time() - t0 < dur:
        p = f3(ent + 0x40)
        if p and lastpos and abs(p[0] - lastpos[0]) + abs(p[1] - lastpos[1]) > 0.05:
            moves += 1
        lastpos = p
        for (name, baseaddr, d0) in base:
            cur = rd_buf(baseaddr, len(d0))
            if cur is None:
                continue
            old = prev.get(name)
            if old is None:
                prev[name] = cur
                continue
            if cur != old:
                for i in range(len(cur)):
                    if cur[i] != old[i]:
                        k = (name, i)
                        rec = changes.get(k)
                        if rec is None:
                            changes[k] = [1, old[i], cur[i]]
                        else:
                            rec[0] += 1
                            rec[2] = cur[i]
                prev[name] = cur
        time.sleep(0.12)
    out.append('== %s: %.0fs, move-samples=%d, total changed bytes=%d' %
               (tag, dur, moves, len(changes)))
    byreg = {}
    for (name, i), (c, f, l) in changes.items():
        byreg.setdefault(name, []).append((i, c, f, l))
    for name in sorted(byreg.keys()):
        lst = sorted(byreg[name])
        runs = []
        for (i, c, f, l) in lst:
            if runs and i == runs[-1][1] + 1:
                runs[-1][1] = i
                runs[-1][2] += c
            else:
                runs.append([i, i, c])
        desc = ', '.join('+0x%X-%X x%d' % (a, b, c) for (a, b, c) in runs[:36])
        out.append('   %s: %d bytes / %d runs: %s' % (name, len(lst), len(runs), desc))
    return changes


# pick a moving edward
target = None
for attempt in range(5):
    pos0 = {e: f3(e + 0x40) for e in edwards}
    time.sleep(1.5)
    for e in edwards:
        p = f3(e + 0x40)
        q = pos0.get(e)
        if p and q and abs(p[0] - q[0]) + abs(p[1] - q[1]) > 0.25:
            target = e
            break
    if target:
        break

out = []
if not target:
    out.append('NO MOVING EDWARD (world frozen or all standing)')
else:
    print('target edward 0x%08X — walk window %.0fs' % (target, DUR_WALK), flush=True)
    diff_window('WALK', target, DUR_WALK, out)
    stopped = False
    t0 = time.time()
    while time.time() - t0 < 30:
        a = f3(target + 0x40)
        time.sleep(1.2)
        b = f3(target + 0x40)
        if a and b and abs(b[0] - a[0]) + abs(b[1] - a[1]) < 0.1:
            stopped = True
            break
    if stopped:
        print('stopped — stand window %.0fs' % DUR_STAND, flush=True)
        diff_window('STAND', target, DUR_STAND, out)
    else:
        out.append('== STAND window skipped (still moving)')

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(out) + '\n')
print('written', OUT, flush=True)
for line in out:
    print(line, flush=True)
