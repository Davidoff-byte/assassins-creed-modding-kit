#!/usr/bin/env python3
"""Listen on the plugin's port and report any datagrams for a few seconds.
Run while the game is closed; the fake peer keeps sending."""
import socket

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("0.0.0.0", 27973))
s.settimeout(1.0)
print("listening on 27973 for 12 s ...")
n = 0
import time
t0 = time.time()
while time.time() - t0 < 12:
    try:
        data, addr = s.recvfrom(2048)
        n += 1
        if n <= 10:
            print("RX %d bytes from %s: %s" % (len(data), addr, data[:24].hex()))
    except socket.timeout:
        pass
print("total received: %d" % n)
