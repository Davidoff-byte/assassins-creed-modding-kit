#!/usr/bin/env python3
"""Send valid Welcome envelopes (which the host plugin logs a warning about,
once) to check whether the plugin's recv path can see our packets at all."""
import socket
import struct
import time

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("127.0.0.1", 27975))
s.settimeout(0.3)
seq = 0


def new_env(t, cid):
    global seq
    seq += 1
    return struct.pack("<IHHII", 0x50524341, 1, t, seq, cid)


def welcome():
    payload = struct.pack("<III", 0xAABBCCDD, 9, 0) + b"probeW".ljust(32, b"\0")
    return new_env(5, 8) + payload


for i in range(10):
    s.sendto(welcome(), ("127.0.0.1", 27973))
    time.sleep(0.3)
print("welcomes sent")
