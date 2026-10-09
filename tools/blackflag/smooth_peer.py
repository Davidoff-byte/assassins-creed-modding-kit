#!/usr/bin/env python3
"""Smooth-motion fake peer: walks the ghost in a slow circle around the live player.

Drives via the coop protocol (v0.3 handshake + Player samples). The plugin (host)
will target the picked body to our sent position. Circle speed ~0.9 m/s, radius 2.5 m
- a real walking pace - so we can see whether the ghost's legs animate from smooth motion.

Usage: smooth_peer.py <game_pid> [duration_s] [radius] [speed]
Ports: sends from 31724 to plugin 31723 (current ini).
"""
import ctypes
import math
import socket
import struct
import sys
import time

pid = int(sys.argv[1])
duration = float(sys.argv[2]) if len(sys.argv) > 2 else 150.0
radius = float(sys.argv[3]) if len(sys.argv) > 3 else 2.5
speed = float(sys.argv[4]) if len(sys.argv) > 4 else 0.9

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok and g.value == n else None


def u32(a):
    b = rd(a, 4)
    return struct.unpack('<I', b)[0] if b else 0


def f3(a):
    b = rd(a, 12)
    return struct.unpack('<fff', b) if b else None


def player_feet():
    mgr = u32(0x2ABE588)
    if not mgr:
        return None
    holder = u32(mgr + 0x4C)
    if not holder:
        return None
    camobj = u32(holder)
    if not camobj:
        return None
    block = u32(camobj + 0x68)
    if not block:
        return None
    prov = u32(block + 0x174)
    if prov:
        p = f3(prov + 0x110)
        if p:
            return p
    cnt = u32(mgr + 0x130)
    idx = cnt % 5
    return f3(mgr + 0x90 + idx * 0x10)


MAGIC = 0x50524341
VER = 1
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(('127.0.0.1', 31724))
s.settimeout(0.0)
dst = ('127.0.0.1', 31723)

seq = [0]
name = b'smooth\x00'.ljust(32, b'\x00')


def send_hello():
    seq[0] += 1
    env = struct.pack('<IHHII', MAGIC, VER, 4, seq[0], 2)
    s.sendto(env + struct.pack('<HHI', 1, 0, 0) + name, dst)


def send_player(px, py, pz, qz, qw, vx, vy):
    seq[0] += 1
    env = struct.pack('<IHHII', MAGIC, VER, 1, seq[0], 2)
    body = struct.pack('<11fIII', px, py, pz, 0.0, 0.0, qz, qw,
                       vx, vy, 0.0, 100.0, 0, int(time.time() * 1000) & 0xFFFFFFFF, 0)
    s.sendto(env + body, dst)


print('smooth peer: bind 31724 -> plugin 31723, circle r=%.1f v=%.1f m/s for %.0fs' % (
    radius, speed, duration))
send_hello()
time.sleep(0.2)
# drain any welcomes
try:
    while True:
        d, a = s.recvfrom(1024)
        if len(d) >= 16:
            m, v, t, sq, cid = struct.unpack('<IHHII', d[:16])
            print('  rx type=%d from %s' % (t, a))
except socket.timeout:
    pass
except OSError:
    pass

t0 = time.time()
ang = 0.0
last = 0.0
last_hello = time.time()
while time.time() - t0 < duration:
    feet = player_feet()
    if not feet:
        time.sleep(0.1)
        continue
    fx, fy, fz = feet
    ang += speed / radius * 0.05
    gx = fx + radius * math.cos(ang)
    gy = fy + radius * math.sin(ang)
    gz = fz
    yaw = ang + math.pi / 2.0
    qz = math.sin(yaw / 2.0)
    qw = math.cos(yaw / 2.0)
    vx = -speed * math.sin(ang)
    vy = speed * math.cos(ang)
    send_player(gx, gy, gz, qz, qw, vx, vy)
    now = time.time()
    if now - last >= 2.0:
        last = now
        print('  t=%5.1fs player=(%.1f,%.1f,%.1f) ghost=(%.1f,%.1f,%.1f) ang=%.1f' % (
            now - t0, fx, fy, fz, gx, gy, gz, ang))
    if now - last_hello >= 1.0:
        send_hello()
        last_hello = now
    time.sleep(0.05)
print('done')
