#!/usr/bin/env python3
"""Scimitar .forge TOC parser / validator / redirector.

Implements the TOC logic from scimitar_alt.bms (RetingencyPlan compendium),
for VER in 0x1b..0x1c (plain-name forges, e.g. DataPC_extra_chr.forge).

Commands:
  validate <forge> <extract_dir>
      Parse TOC, compare each entry's computed data range against the
      extracted file (size + sampled content). Prints mismatches.

  list <forge> [substring ...]
      Print entries whose name contains any given substring
      (case-insensitive). Without substrings prints all.

  redirect <forge_in> <forge_out> <source_name> <target_name> [target_name ...]
      Copy forge_in to forge_out, then retarget each target entry to the
      source entry's data: copies the source's offset-table record and
      name-record (keeping the target's own NAME string and HASH32).
"""
import mmap
import shutil
import struct
import sys
from hashlib import sha1

NAME_REC = 192          # VER >= 0x1b
OT_REC = 20             # VER >= 0x1b


def parse_forge(path):
    f = open(path, 'rb')
    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    if mm[:9] != b'scimitar\x00':
        raise SystemExit('not a scimitar forge: %r' % mm[:10])
    VER, INFO_OFF, D3, D4, D5, D6 = struct.unpack_from('<6I', mm, 9)
    if VER < 0x1b or VER > 0x1c:
        raise SystemExit('unsupported VER 0x%x (expected 0x1b..0x1c)' % VER)
    pos = INFO_OFF
    TOTAL_FILES, TOTAL_UNKNOWN, DUMMY9 = struct.unpack_from('<3I', mm, pos)
    pos += 12
    (DUMMY10,) = struct.unpack_from('<q', mm, pos)
    pos += 8
    (DUMMY11,) = struct.unpack_from('<q', mm, pos)
    pos += 8
    CHUNK_FILES_MAX, CHUNK_COUNT = struct.unpack_from('<2I', mm, pos)
    pos += 8
    (chunk_next,) = struct.unpack_from('<q', mm, pos)
    pos += 8

    entries = []
    chunks = []
    guard = 0
    while chunk_next > 0 and guard < 100000:
        guard += 1
        cpos = chunk_next
        CHUNK_FILES, CHUNK_UNKNOWN = struct.unpack_from('<2I', mm, cpos)
        CHUNK_START, CHUNK_NEXT = struct.unpack_from('<2q', mm, cpos + 8)
        FILE_MIN, FILE_MAX = struct.unpack_from('<2I', mm, cpos + 24)
        NAME_OFFSET, DATA_OFFSET = struct.unpack_from('<2q', mm, cpos + 32)
        chunks.append(dict(pos=cpos, files=CHUNK_FILES, unknown=CHUNK_UNKNOWN,
                           start=CHUNK_START, name_off=NAME_OFFSET,
                           data_off=DATA_OFFSET, next=CHUNK_NEXT,
                           fmin=FILE_MIN, fmax=FILE_MAX))
        base = len(entries)
        otpos = cpos + 48
        for i in range(CHUNK_FILES):
            OFFSET, DUMMY2, HASH32, DUMMY4, SIZE = struct.unpack_from(
                '<5I', mm, otpos + OT_REC * i)
            entries.append(dict(
                ot_pos=otpos + OT_REC * i,
                offset=OFFSET, d2=DUMMY2, hash32=HASH32, d4=DUMMY4,
                size_tab=SIZE,
                ot_raw=bytes(mm[otpos + OT_REC * i: otpos + OT_REC * (i + 1)])))
        np_ = NAME_OFFSET
        for i in range(CHUNK_FILES):
            SIZE, D29, D30a, D30b = struct.unpack_from('<4I', mm, np_)
            D31, = struct.unpack_from('<q', mm, np_ + 16)
            D32a, D32b, D33, D34, TYPE = struct.unpack_from('<5I', mm, np_ + 24)
            name_raw = bytes(mm[np_ + 44: np_ + 44 + 0x80])
            NAME = name_raw.split(b'\x00')[0].decode('latin1')
            e = entries[base + i]
            e.update(name_rec_pos=np_, name_rec_raw=bytes(mm[np_: np_ + NAME_REC]),
                     name=NAME, size_rec=SIZE, type=TYPE)
            np_ += NAME_REC
        chunk_next = CHUNK_NEXT

    info = dict(path=path, f=f, mm=mm, VER=VER, INFO_OFF=INFO_OFF, D6=D6,
                TOTAL_FILES=TOTAL_FILES, CHUNK_FILES_MAX=CHUNK_FILES_MAX,
                CHUNK_COUNT=CHUNK_COUNT, entries=entries, chunks=chunks)
    if len(entries) != TOTAL_FILES:
        print('WARNING: parsed %d entries, TOTAL_FILES=%d'
              % (len(entries), TOTAL_FILES))
    return info


def data_range(e, D6):
    if D6 == 1:
        return e['offset'], e['size_rec']
    return e['offset'] + 4, e['size_rec'] - 4


def cmd_validate(forge, extract_dir):
    info = parse_forge(forge)
    print('VER=0x%x INFO_OFF=%d D6=%d entries=%d chunks=%d'
          % (info['VER'], info['INFO_OFF'], info['D6'],
             len(info['entries']), len(info['chunks'])))
    mm = info['mm']
    D6 = info['D6']
    ok = miss = mismatch = 0
    for e in info['entries']:
        p = None
        for cand in (e['name'], e['name'] + '.compressed'):
            q = __import__('os').path.join(extract_dir, cand)
            if __import__('os').path.isfile(q):
                p = q
                break
        if not p:
            miss += 1
            continue
        off, sz = data_range(e, D6)
        if off + sz > len(mm):
            print('OUT OF RANGE: %s off=0x%x size=%d' % (e['name'], off, sz))
            mismatch += 1
            continue
        fsz = __import__('os').path.getsize(p)
        if fsz != sz:
            print('SIZE MISMATCH: %s toc=%d disk=%d off=0x%x'
                  % (e['name'], sz, fsz, off))
            mismatch += 1
            continue
        # sampled content check
        disk = open(p, 'rb')
        head_disk = disk.read(64)
        disk.seek(max(0, fsz - 64))
        tail_disk = disk.read(64)
        disk.close()
        head_toc = mm[off: off + 64]
        tail_toc = mm[off + max(0, sz - 64): off + sz]
        if head_disk != head_toc or tail_disk != tail_toc:
            print('CONTENT MISMATCH: %s off=0x%x size=%d' % (e['name'], off, sz))
            mismatch += 1
            continue
        ok += 1
    print('validated ok=%d mismatch=%d missing=%d' % (ok, mismatch, miss))


def cmd_list(forge, substrings):
    info = parse_forge(forge)
    D6 = info['D6']
    subs = [s.lower() for s in substrings]
    for e in info['entries']:
        n = e['name']
        if subs and not any(s in n.lower() for s in subs):
            continue
        off, sz = data_range(e, D6)
        print('%-64s off=0x%08x size=%-9d type=0x%08x hash32=0x%08x'
              % (n, off, sz, e['type'], e['hash32']))


def cmd_redirect(forge_in, forge_out, source_name, targets):
    info = parse_forge(forge_in)
    src = None
    tmap = {}
    for e in info['entries']:
        if e['name'] == source_name:
            src = e
        if e['name'] in targets:
            tmap[e['name']] = e
    if not src:
        raise SystemExit('source not found: %s' % source_name)
    print('source: %s off=0x%x size_rec=%d size_tab=%d hash32=0x%08x'
          % (src['name'], src['offset'], src['size_rec'], src['size_tab'],
             src['hash32']))
    if not tmap:
        raise SystemExit('no targets found')
    print('copying forge...')
    shutil.copyfile(forge_in, forge_out)
    with open(forge_out, 'r+b') as out:
        for name in targets:
            e = tmap[name]
            # offset table: copy source record, keep target HASH32 (bytes 8..12)
            new_ot = bytearray(src['ot_raw'])
            new_ot[8:12] = struct.pack('<I', e['hash32'])
            out.seek(e['ot_pos'])
            out.write(bytes(new_ot))
            # name record: copy source record, keep target NAME (44..44+0x80)
            new_nr = bytearray(src['name_rec_raw'])
            new_nr[44:44 + 0x80] = e['name_rec_raw'][44:44 + 0x80]
            out.seek(e['name_rec_pos'])
            out.write(bytes(new_nr))
            print('redirected %s -> %s  (ot @0x%x, name rec @0x%x)'
                  % (name, source_name, e['ot_pos'], e['name_rec_pos']))
    print('wrote %s' % forge_out)


def cmd_redirect_eof(forge_in, forge_out, source_name, targets):
    """Safest redirect: append a private copy of the source data at EOF and
    point the targets at that copy. Only OFFSET + SIZE fields change; every
    other field keeps the target's own values. The appended copy is shared by
    all targets given in one call, so pass a single target per call while
    testing whether data sharing is what crashes the loader."""
    info = parse_forge(forge_in)
    src = None
    tmap = {}
    for e in info['entries']:
        if e['name'] == source_name:
            src = e
        if e['name'] in targets:
            tmap[e['name']] = e
    if not src:
        raise SystemExit('source not found: %s' % source_name)
    sof, ssz = data_range(src, info['D6'])
    data = info['mm'][sof:sof + ssz]
    print('source %s: off=0x%x size=%d' % (src['name'], sof, ssz))
    shutil.copyfile(forge_in, forge_out)
    with open(forge_out, 'r+b') as out:
        out.seek(0, 2)
        eof = out.tell()
        out.write(data)
        for name in targets:
            e = tmap.get(name)
            if e is None:
                raise SystemExit('target not found: %s' % name)
            ot = bytearray(e['ot_raw'])
            struct.pack_into('<I', ot, 0, eof)
            if len(ot) >= OT_REC:
                struct.pack_into('<I', ot, 16, ssz)
            out.seek(e['ot_pos'])
            out.write(bytes(ot))
            nr = bytearray(e['name_rec_raw'])
            struct.pack_into('<I', nr, 0, ssz)
            out.seek(e['name_rec_pos'])
            out.write(bytes(nr))
            print('target %s: OFFSET=0x%x SIZE=%d (ot @0x%x, name rec @0x%x)'
                  % (name, eof, ssz, e['ot_pos'], e['name_rec_pos']))
    print('appended copy at 0x%x (%d bytes); wrote %s' % (eof, len(data), forge_out))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd == 'validate':
        cmd_validate(sys.argv[2], sys.argv[3])
    elif cmd == 'list':
        cmd_list(sys.argv[2], sys.argv[3:])
    elif cmd == 'redirect':
        cmd_redirect(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:])
    elif cmd == 'redirect_eof':
        cmd_redirect_eof(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
