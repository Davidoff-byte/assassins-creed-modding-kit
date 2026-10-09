#!/usr/bin/env python3
"""Print decompiled bodies for the crash-chain functions."""
import os
import sqlite3

DB = r"C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite"
SRC = r"C:\Users\Administrator\bf4_re\sp_src"

con = sqlite3.connect(DB)
cur = con.cursor()
print("files cols:", [r[1] for r in cur.execute("PRAGMA table_info(files)")])

def show(fname, maxlines=70):
    row = cur.execute(
        "SELECT file_id, start_line, end_line FROM functions WHERE name=?",
        (fname,)).fetchone()
    if not row:
        row = cur.execute(
            "SELECT file_id, start_line, end_line FROM functions WHERE name LIKE ?",
            (fname.upper() + '%',)).fetchone()
    if not row:
        print("== %s: NOT FOUND IN INDEX" % fname)
        return
    fid, s, e = row
    fr = cur.execute("SELECT * FROM files WHERE id=?", (fid,)).fetchone()
    cols = [c[1] for c in cur.execute("PRAGMA table_info(files)")]
    fdict = dict(zip(cols, fr))
    path = None
    for key in ("path", "name", "filename"):
        if key in fdict and fdict[key]:
            path = fdict[key]
            break
    print("== %s: file_id=%s %s lines %s-%s" % (fname, fid, fdict, s, e))
    if not path:
        return
    fp = os.path.join(SRC, path)
    if not os.path.exists(fp):
        print("   file missing:", fp)
        return
    with open(fp, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    for i in range(s - 1, min(e, s - 1 + maxlines)):
        print("%s| %s" % (i + 1, lines[i].rstrip()))

import sys
for fn in (sys.argv[1:] or ("FUN_007437A0",)):
    show(fn, maxlines=110)
    print()
