#!/usr/bin/env python3
"""Isolation test: is the plugin's publish running? Does it answer Hellos?"""
import socket
import struct
import time

MAGIC = 0x50524341
VER = 1

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(('127.0.0.1', 31724))
s.settimeout(1.0)
print('listening on 30974 for plugin publish (5s)...')
got = 0
types = {}
t0 = time.time()
while time.time() - t0 < 5.0:
    try:
        data, addr = s.recvfrom(1024)
        got += 1
        if len(data) >= 16:
            m, v, t, seq, cid = struct.unpack('<IHHII', data[:16])
            types[t] = types.get(t, 0) + 1
            if got <= 3:
                print('  rx %d bytes from %s: type=%d seq=%d cid=%d mag=%08X' % (
                    len(data), addr, t, seq, cid, m))
    except socket.timeout:
        pass
print('publish packets in 5s: %d  types=%s' % (got, types))

print('sending 4 Hellos to 30973 ...')
name = b'probe\x00'.ljust(32, b'\x00')
for i in range(4):
    env = struct.pack('<IHHII', MAGIC, VER, 4, 100 + i, 2)
    payload = struct.pack('<HHI', 1, 0, 0) + name
    s.sendto(env + payload, ('127.0.0.1', 31723))
    try:
        data, addr = s.recvfrom(1024)
        m, v, t, seq, cid = struct.unpack('<IHHII', data[:16])
        print('  REPLY! type=%d len=%d from %s' % (t, len(data), addr))
    except socket.timeout:
        print('  hello %d: no reply' % (i + 1))
    time.sleep(0.4)
print('done')
