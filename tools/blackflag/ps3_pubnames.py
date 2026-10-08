#!/usr/bin/env python3
"""Fast dump of .debug_pubnames (name -> DIE offset index) from the PS3 ELF."""
import struct
import sys

path = sys.argv[1] if len(sys.argv) > 1 else r'D:\Games\acbf_ps3_gold\scimitar_final.elf'
out = sys.argv[2] if len(sys.argv) > 2 else r'C:\Users\Administrator\Documents\Default Project\bf-coop\logs\ps3_pubnames.txt'

f = open(path, 'rb')
d = f.read(0x4000)
is64 = d[4] == 2
end = '<' if d[5] == 1 else '>'
if is64:
    e_shoff, = struct.unpack_from(end + 'Q', d, 0x28)
    e_shentsize, = struct.unpack_from(end + 'H', d, 0x3A)
    e_shnum, = struct.unpack_from(end + 'H', d, 0x3C)
    e_shstrndx, = struct.unpack_from(end + 'H', d, 0x3E)
else:
    e_shoff, = struct.unpack_from(end + 'I', d, 0x20)
    e_shentsize, = struct.unpack_from(end + 'H', d, 0x2E)
    e_shnum, = struct.unpack_from(end + 'H', d, 0x30)
    e_shstrndx, = struct.unpack_from(end + 'H', d, 0x32)

def sh(i):
    f.seek(e_shoff + i * e_shentsize)
    b = f.read(e_shentsize)
    if is64:
        return struct.unpack_from(end + 'IIQQQQ', b, 0)
    return struct.unpack_from(end + 'IIIIII', b, 0)

shs = [sh(i) for i in range(e_shnum)]
stroff = shs[e_shstrndx][4]
f.seek(stroff)
strtab = f.read(shs[e_shstrndx][5] + 0x1000)

pub = None
for name, typ, flags, addr, offset, size in shs:
    e = strtab.find(b'\0', name)
    nm = strtab[name:e].decode('latin1')
    if nm == '.debug_pubnames':
        pub = (offset, size)

if not pub:
    print('no .debug_pubnames')
    sys.exit(1)

off, size = pub
f.seek(off)
data = f.read(size)
print('pubnames size', size)

pos = 0
count = 0
with open(out, 'w', encoding='latin1') as w:
    while pos + 4 <= len(data):
        unit_length, = struct.unpack_from(end + 'I', data, pos)
        if unit_length == 0:
            break
        if unit_length == 0xFFFFFFFF:
            print('DWARF64 pubnames not handled'); break
        version, debug_info_offset, debug_info_length = struct.unpack_from(end + 'IHI', data, pos + 4)
        p = pos + 4 + 10
        endp = pos + 4 + unit_length
        while p + 4 <= endp:
            die_off, = struct.unpack_from(end + 'I', data, p)
            p += 4
            if die_off == 0:
                break
            e = data.find(b'\0', p, endp)
            if e < 0:
                break
            nm = data[p:e].decode('latin1', 'replace')
            p = e + 1
            w.write('0x%08x %s\n' % (debug_info_offset + die_off, nm))
            count += 1
        pos += 4 + unit_length
print('dumped', count, 'names ->', out)
