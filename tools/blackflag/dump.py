#!/usr/bin/env python3
"""READ-ONLY hex dump. Usage: dump.py <pid> <addr_hex> <len_hex>"""
import ctypes
import struct
import sys

pid = int(sys.argv[1])
addr = int(sys.argv[2], 16)
n = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x100
k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)
b = ctypes.create_string_buffer(n)
g = ctypes.c_size_t(0)
ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(addr), b, n, ctypes.byref(g))
raw = b.raw[:g.value]
print('dump 0x%08X len 0x%X ok=%s got=0x%X' % (addr, n, ok, g.value))
for row in range(0, len(raw), 16):
    chunk = raw[row:row + 16]
    hexs = ' '.join('%02X' % c for c in chunk)
    words = ' '.join('%08X' % struct.unpack_from('<I', chunk, o)[0] for o in range(0, len(chunk) - 3, 4))
    print('  +%04X: %-47s %s' % (row, hexs, words))
