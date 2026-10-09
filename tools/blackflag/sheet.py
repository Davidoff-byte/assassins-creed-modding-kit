#!/usr/bin/env python3
"""Extract video frames and tile into a timestamped contact sheet.

Usage: sheet.py <video> <out.png> <start> <end> <every> <cols> [scale]
"""
import os
import subprocess
import sys
import tempfile

import imageio_ffmpeg
from PIL import Image, ImageDraw

video, out, start, end, every, cols = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]), int(sys.argv[6])
scale = int(sys.argv[7]) if len(sys.argv) > 7 else 480

ff = imageio_ffmpeg.get_ffmpeg_exe()
print('ffmpeg:', ff)

tmp = tempfile.mkdtemp(prefix='sheet_')
cmd = [ff, '-hide_banner', '-loglevel', 'error',
       '-ss', str(start), '-to', str(end), '-i', video,
       '-vf', f'fps=1/{every},scale={scale}:-1',
       os.path.join(tmp, 'f%04d.png')]
subprocess.run(cmd, check=True)
frames = sorted(f for f in os.listdir(tmp) if f.endswith('.png'))
print('frames:', len(frames))

if not frames:
    print('NO FRAMES')
    sys.exit(1)

first = Image.open(os.path.join(tmp, frames[0]))
w, h = first.size
c = cols
r = (len(frames) + c - 1) // c
sheet = Image.new('RGB', (w * c, (h + 18) * r), (20, 20, 20))
d = ImageDraw.Draw(sheet)
for i, fn in enumerate(frames):
    img = Image.open(os.path.join(tmp, fn)).convert('RGB')
    x = (i % c) * w
    y = (i // c) * (h + 18)
    sheet.paste(img, (x, y))
    t = start + i * every
    d.text((x + 4, y + h + 2), '%5.1fs' % t, fill=(255, 230, 80))
sheet.save(out)
print('sheet:', out, sheet.size)
