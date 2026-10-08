#!/usr/bin/env python3
"""Disassemble PS3 PPU functions by virtual address from the ELF (via pyelftools + capstone)."""
import sys

from capstone import CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN, Cs
from elftools.elf.elffile import ELFFile

ELF = r'D:\Games\acbf_ps3_gold\scimitar_final.elf'
md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
md.detail = False

f = open(ELF, 'rb')
elf = ELFFile(f)
sections = []
for s in elf.iter_sections():
    try:
        sections.append((s['sh_addr'], s['sh_addr'] + s['sh_size'], s.name, s))
    except Exception:
        pass


def disasm(va, size, label):
    sec = None
    for a, b, nm, s in sections:
        if a <= va < b and (s['sh_flags'] & 0x4):  # executable
            sec = s
            break
    if sec is None:
        # PPC64 ELFv1: the address may be a .opd descriptor (24 bytes: entry, toc, env)
        for a, b, nm, s in sections:
            if a <= va < b:
                raw = s.data()[va - a: va - a + 8]
                if len(raw) == 8:
                    entry = int.from_bytes(raw, 'big')
                    print('=== %s: 0x%x is a .opd descriptor -> entry 0x%x ===' % (label, va, entry))
                    disasm(entry, size, label)
                    return
        print('%s: VA 0x%x not resolvable' % (label, va))
        return
    data = sec.data()
    off = va - sec['sh_addr']
    code = data[off: off + size]
    print('=== %s  @0x%x (%d bytes) ===' % (label, va, size))
    for ins in md.disasm(code, va):
        print('  0x%08x  %-8s %s' % (ins.address, ins.mnemonic, ins.op_str))


funcs = [
    (0x0122D3D0, 0x48, 'SPC Life Fn'),
    (0x0122D460, 0x48, 'SPC MaxLife Fn'),
    (0x0122D418, 0x48, 'SPC IncapLimit Fn'),
    (0x01220554, 0x58, 'SPC IsIncapacitated Fn'),
    (0x002021AC, 0x64, 'GetService<CSrvNPCHealth> alt'),
]
if len(sys.argv) > 2:
    funcs = []
    args = sys.argv[1:]
    for i in range(0, len(args) - 1, 2):
        funcs.append((int(args[i], 0), int(args[i + 1], 0), 'arg%d' % (i // 2)))
for va, size, label in funcs:
    disasm(va, size, label)
