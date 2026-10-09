#!/usr/bin/env python3
"""With the game running, bind the SAME port again (SO_REUSEADDR) and listen.
If these receive anything, the OS is delivering port traffic to a later binder
instead of the game's socket."""
import socket
import time

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(("0.0.0.0", 27973))
except OSError as e:
    print("second bind failed:", e)
    raise SystemExit(1)
s.settimeout(1.0)
print("second binder active on 27973 for 10 s ...")
t0 = time.time()
n = 0
while time.time() - t0 < 10:
    try:
        d, a = s.recvfrom(2048)
        n += 1
        if n <= 8:
            print("RX %d bytes from %s: %s" % (len(d), a, d[:16].hex()))
    except socket.timeout:
        pass
print("total received by second binder: %d" % n)
