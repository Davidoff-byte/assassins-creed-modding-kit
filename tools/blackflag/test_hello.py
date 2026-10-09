#!/usr/bin/env python3
"""Probe: send valid Hello envelopes straight at the plugin's UDP port and
report any replies. Used to test whether the plugin's recv path works."""
import socket
import struct
import time

HOST, PORT = "127.0.0.1", 27973
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("127.0.0.1", 27975))
s.settimeout(0.4)
seq = 0


def new_env(t, cid):
    global seq
    seq += 1
    return struct.pack("<IHHII", 0x50524341, 1, t, seq, cid)


def hello(name):
    payload = struct.pack("<HHI", 1, 0, 0) + name.encode().ljust(32, b"\0")
    return new_env(4, 7) + payload


rx = 0
for i in range(15):
    s.sendto(hello("probe"), (HOST, PORT))
    try:
        data, addr = s.recvfrom(2048)
        typ = struct.unpack_from("<H", data, 6)[0]
        print("RX %d bytes from %s type=%d" % (len(data), addr, typ))
        rx += 1
    except socket.timeout:
        pass
    time.sleep(0.4)
print("done, replies=%d" % rx)
