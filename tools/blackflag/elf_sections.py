#!/usr/bin/env python3
"""List ELF sections of a (PS3) ELF: prints names, sizes, flags. Flags DWARF presence."""
import struct
import sys

path = sys.argv[1] if len(sys.argv) > 1 else r'D:\Games\acbf_ps3_gold\scimitar_final.elf'
f = open(path, 'rb')
d = f.read(0x4000)

# ELF header (32-bit or 64-bit)
if d[:4] != b'\x7fELF':
    print('not an ELF'); sys.exit(1)
is64 = d[4] == 2
end = '<' if d[5] == 1 else '>'
if not is64:
    (e_shoff,) = struct.unpack_from(end + 'I', d, 0x20)
    (e_shentsize,) = struct.unpack_from(end + 'H', d, 0x2E)
    (e_shnum,) = struct.unpack_from(end + 'H', d, 0x30)
    (e_shstrndx,) = struct.unpack_from(end + 'H', d, 0x32)
else:
    (e_shoff,) = struct.unpack_from(end + 'Q', d, 0x28)
    (e_shentsize,) = struct.unpack_from(end + 'H', d, 0x3A)
    (e_shnum,) = struct.unpack_from(end + 'H', d, 0x3C)
    (e_shstrndx,) = struct.unpack_from(end + 'H', d, 0x3E)

print('64bit=%s endian=%s shoff=0x%x shentsize=%d shnum=%d shstrndx=%d'
      % (is64, end, e_shoff, e_shentsize, e_shnum, e_shstrndx))
if e_shnum == 0 or e_shentsize == 0:
    print('no section table (stripped/custom ELF)')
    sys.exit(0)

def read_sh(i):
    off = e_shoff + i * e_shentsize
    f.seek(off)
    b = f.read(e_shentsize)
    if is64:
        name, typ, flags, addr, offset, size = struct.unpack_from(end + 'IIQQQQ', b, 0)
    else:
        name, typ, flags, addr, offset, size = struct.unpack_from(end + 'IIIIII', b, 0)
    return name, typ, flags, addr, offset, size

shs = [read_sh(i) for i in range(e_shnum)]
strtab_off = shs[e_shstrndx][4]
f.seek(strtab_off)
strtab = f.read(max(s[5] for s in shs) + 0x1000)

dwarf = []
print('%-28s %-10s %-12s %s' % ('name', 'type', 'addr', 'size'))
for name, typ, flags, addr, offset, size in shs:
    endn = strtab.find(b'\0', name)
    nm = strtab[name:endn].decode('latin1') if 0 <= name < len(strtab) else '?'
    print('%-28s 0x%-8x 0x%-10x %d' % (nm, typ, addr, size))
    if 'debug' in nm:
        dwarf.append(nm)

print()
print('DWARF sections:', dwarf if dwarf else 'NONE')
