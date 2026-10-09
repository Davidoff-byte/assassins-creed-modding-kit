#!/usr/bin/env python3
"""Caller/callee edges for the anim-channel functions, with names resolved."""
import sqlite3
import sys

DB = r"C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite"
con = sqlite3.connect(DB)
cur = con.cursor()

def fid(name):
    r = cur.execute("SELECT id FROM functions WHERE name LIKE ?", (name + '%',)).fetchone()
    return r[0] if r else None

def name_of(i):
    r = cur.execute("SELECT name FROM functions WHERE id=?", (i,)).fetchone()
    return r[0] if r else ('id' + str(i))

def fname_of(i):
    r = cur.execute("SELECT name, file_id FROM functions WHERE id=?", (i,)).fetchone()
    return r

TARGETS = sys.argv[1:] or ["FUN_01ac1ad0", "FUN_01ab52c0", "FUN_01ad9190", "FUN_013aec10", "FUN_01aa3ea0"]
for t in TARGETS:
    i = fid(t)
    if not i:
        print(t, 'NOT FOUND'); continue
    callers = cur.execute(
        "SELECT src_id, COUNT(*), MIN(line) FROM edges WHERE dst_id=? GROUP BY src_id ORDER BY 2 DESC",
        (i,)).fetchall()
    callees = cur.execute(
        "SELECT dst_id, COUNT(*), MIN(line) FROM edges WHERE src_id=? GROUP BY dst_id ORDER BY 2 DESC",
        (i,)).fetchall()
    print("==", t, "id", i)
    print("   callers (%d):" % len(callers))
    for c, n, ln in callers[:15]:
        r = fname_of(c)
        print("     %s  (file %s) x%d" % ((r[0] if r else c), (r[1] if r else '?'), n))
    print("   callees (%d):" % len(callees))
    for c, n, ln in callees[:15]:
        r = fname_of(c)
        print("     %s  (file %s) x%d" % ((r[0] if r else c), (r[1] if r else '?'), n))
