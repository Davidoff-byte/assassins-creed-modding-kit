#!/usr/bin/env python3
"""Parse the AC.BlackFlag.PatchFix.log AnimApply/AnimWrite probe output.

Summarize per-object value vocabularies:
 - AnimApply: request-slot tuples (when any slot != 0xFFFFFFFF)
 - AnimWrite: distinct (a,b,c,d) tuples + (e,f) bytes, with counts and times
Optionally filter lines after a given timestamp prefix (e.g. "17:1").
"""
import re
import sys
from collections import defaultdict, Counter

log = sys.argv[1] if len(sys.argv) > 1 else (
    r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins"
    r"\AC.BlackFlag.PatchFix.log")
since = sys.argv[2] if len(sys.argv) > 2 else None

ts_re = re.compile(r"^\[(\d{4}-\d{2}-\d{2} (\d{2}:\d{2}:\d{2}\.\d+))\]")
apply_re = re.compile(
    r"AnimApply: #(\d+) this=0x([0-9A-F]+) slots=0x([0-9A-F]+),0x([0-9A-F]+),0x([0-9A-F]+),"
    r"0x([0-9A-F]+),0x([0-9A-F]+),0x([0-9A-F]+)")
write_re = re.compile(
    r"AnimWrite: #(\d+) this=0x([0-9A-F]+) a=0x([0-9A-F]+) b=0x([0-9A-F]+) c=0x([0-9A-F]+) "
    r"d=0x([0-9A-F]+) e=0x([0-9A-F]+) f=0x([0-9A-F]+) caller=0x([0-9A-F]+)")

apply_by_obj = defaultdict(list)
write_by_obj = defaultdict(list)
write_seq = []
apply_seq = []
all_ts = []

with open(log, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        if since and since not in line:
            continue
        m = ts_re.match(line)
        if not m:
            continue
        t = m.group(2)
        all_ts.append((t, line.strip()))
        am = apply_re.search(line)
        if am:
            k, thisv = int(am.group(1)), am.group(2)
            slots = tuple(int(am.group(i), 16) for i in range(3, 9))
            apply_by_obj[thisv].append((t, k, slots))
            apply_seq.append((t, thisv, slots))
        wm = write_re.search(line)
        if wm:
            k, thisv = int(wm.group(1)), wm.group(2)
            abcd = tuple(int(wm.group(i), 16) for i in range(3, 7))
            ef = (int(wm.group(7), 16), int(wm.group(8), 16))
            caller = wm.group(9)
            write_by_obj[thisv].append((t, k, abcd, ef, caller))
            write_seq.append((t, thisv, abcd, ef, caller))

print("=== window: %s .. %s  (%d probe lines)" % (
    all_ts[0][0] if all_ts else "?", all_ts[-1][0] if all_ts else "?", len(all_ts)))

print("\n=== AnimApply (request slots; non-FF only) ===")
for obj, rows in sorted(apply_by_obj.items(), key=lambda x: -len(x[1])):
    cnt = Counter(r[2] for r in rows)
    print(" this=0x%s  calls-with-log: %d" % (obj, len(rows)))
    for slots, n in cnt.most_common(12):
        print("   x%-4d %s   first=%s last=%s" % (
            n, ",".join("%08X" % s for s in slots),
            rows[0][0], rows[-1][0]))

print("\n=== AnimWrite (live writes) ===")
for obj, rows in sorted(write_by_obj.items(), key=lambda x: -len(x[1])):
    cnt = Counter(r[2] for r in rows)
    efs = Counter(r[3] for r in rows)
    callers = Counter(r[4] for r in rows)
    print(" this=0x%s  logged: %d   t=%s..%s  callers=%s" % (
        obj, len(rows), rows[0][0], rows[-1][0], dict(callers)))
    print("   distinct (a,b,c,d) values:")
    for abcd, n in cnt.most_common(20):
        print("     x%-5d a=%08X b=%08X c=%08X d=%08X" % (n, *abcd))
    print("   distinct (e,f): %s" % dict(efs.most_common(8)))

print("\n=== timeline (both, first 200 mixed entries) ===")
merged = [(t, "A", obj, slots) for (t, obj, slots) in apply_seq] + \
         [(t, "W", obj, abcd, ef) for (t, obj, abcd, ef, _c) in write_seq]
# interleave by order in file = already in file order if we kept; simpler: just show seqs
for (t, obj, slots) in apply_seq[:40]:
    print(" %s A 0x%s %s" % (t, obj, ",".join("%08X" % s for s in slots)))
print(" ...")
for (t, obj, abcd, ef, c) in write_seq[:80]:
    print(" %s W 0x%s a=%08X b=%08X c=%08X d=%08X e=%02X f=%02X" % (t, obj, *abcd, *ef))
print("done")
