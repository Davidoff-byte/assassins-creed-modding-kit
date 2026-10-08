#!/usr/bin/env python3
"""Try to crack the scimitar name/class hash from known pairs."""
import struct
import zlib

PAIRS = [
    (b'CSrvNPCHealth', 0x57EEEEC7),
    (b'CHR_G_M_Assassin', 0x815F7672),
    (b'CHR_U_AhTabai', 0x2EA6444C),
    (b'CHR_C_M_Generic_Sailors', 0x8FB6DABC),
    (b'CHR_U_Duncan_Walpole', 0x51BAB7D4),
]


def fnv1a32(b):
    h = 0x811C9DC5
    for c in b:
        h ^= c
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def fnv1_32(b):
    h = 0x811C9DC5
    for c in b:
        h = (h * 0x01000193) & 0xFFFFFFFF
        h ^= c
    return h


def djb2(b):
    h = 5381
    for c in b:
        h = ((h * 33) + c) & 0xFFFFFFFF
    return h


def djb2x(b):
    h = 5381
    for c in b:
        h = ((h * 33) ^ c) & 0xFFFFFFFF
    return h


def sdbm(b):
    h = 0
    for c in b:
        h = (c + (h << 6) + (h << 16) - h) & 0xFFFFFFFF
    return h


def jenkins(b):
    h = 0
    for c in b:
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h


def one_at_a_time(b):
    h = 0
    for c in b:
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h


def crc32(b):
    return zlib.crc32(b) & 0xFFFFFFFF


def crc32_lower(b):
    return zlib.crc32(b.lower()) & 0xFFFFFFFF


def crc32_upper(b):
    return zlib.crc32(b.upper()) & 0xFFFFFFFF


algos = {
    'fnv1a32': fnv1a32, 'fnv1_32': fnv1_32, 'djb2': djb2, 'djb2x': djb2x,
    'sdbm': sdbm, 'jenkins_oat': jenkins, 'crc32': crc32,
    'crc32_lower': crc32_lower, 'crc32_upper': crc32_upper,
}

print('%-14s %s' % ('algo', ' '.join('%08X' % p[1] for p in PAIRS)))
for name, fn in algos.items():
    vals = []
    for b, want in PAIRS:
        got = fn(b)
        vals.append('%08X%s' % (got, '*' if got == want else ' '))
    print('%-14s %s' % (name, ' '.join(vals)))
