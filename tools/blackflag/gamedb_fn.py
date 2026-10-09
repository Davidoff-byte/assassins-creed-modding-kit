#!/usr/bin/env python3
"""gamedb_fn.py - fetch decompiled function bodies from the corpus.

Usage: gamedb_fn.py FUN_00abcdef [FUN_... ...]
Prints params/signature/file/line range, then the body (capped).
"""
import os
import sqlite3
import sys

DB = r"C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite"
SRC = r"C:\Users\Administrator\bf4_re\sp_src"
CAP = 120  # max body lines printed (head+tail beyond)

con = sqlite3.connect(DB)
cur = con.cursor()
print('== files schema ==')
print(cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='files'").fetchone())


def filepath(fid):
    row = cur.execute("SELECT * FROM files WHERE id=?", (fid,)).fetchone()
    if not row:
        return None
    for v in row:
        if isinstance(v, str) and ('part_' in v or '.c' in v):
            return v
    return None


for name in sys.argv[1:]:
    row = cur.execute(
        "SELECT file_id, start_line, end_line, params, sig FROM functions WHERE name=?",
        (name,)).fetchone()
    if not row:
        print('== %s: NOT FOUND in functions ==' % name)
        continue
    fid, s, e, params, sig = row
    fp = filepath(fid)
    print()
    print('== %s  file_id=%s part=%s lines %s..%s ==' % (name, fid, fp, s, e))
    if params:
        print('   params: %s' % params)
    if sig:
        print('   sig: %s' % sig[:400])
    if not fp:
        print('   <no file path>')
        continue
    path = fp if os.path.isabs(fp) else os.path.join(SRC, os.path.basename(fp))
    if not os.path.exists(path):
        cand = os.path.join(SRC, 'part_%05d.c' % fid) if fid is not None else None
        path = cand if cand and os.path.exists(cand) else path
    if not os.path.exists(path):
        print('   <file not found: %s>' % path)
        continue
    lines = open(path, encoding='utf-8', errors='replace').read().splitlines()
    if s is None or e is None:
        print('   <no line range>')
        continue
    body = lines[s - 1:e]
    if len(body) > CAP + 40:
        show = body[:CAP] + ['... (%d lines elided) ...' % (len(body) - CAP - 20)] + body[-20:]
    else:
        show = body
    for i, ln in enumerate(show):
        no = s + i if i < CAP or len(body) <= CAP + 40 else (e - 20 + (i - CAP - 1))
        print('%6d: %s' % (no, ln))
