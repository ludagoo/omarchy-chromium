#!/usr/bin/env python3
"""Is a Chrome RGBX readback a per-pixel function of a 10-bit reference?

pixmap10.py CHROME.rgba REF.p010 W H

Like pixmap.py, for 10-bit frames that Chrome only reads back as RGBX: key =
(Y, U, V) of the P010 reference at each pixel, value = Chrome's (R, G, B).
Prints the share of pixels whose RGB differs from the most common RGB of
their key; a fixed colour conversion gives (nearly) zero, decode errors do
not.
"""
import struct
import sys
from collections import Counter, defaultdict

a = open(sys.argv[1], "rb").read()
b = open(sys.argv[2], "rb").read()
w, h = int(sys.argv[3]), int(sys.argv[4])
n = w * h
Y = struct.unpack(f"<{n}H", b[:2 * n])
C = struct.unpack(f"<{n // 2}H", b[2 * n:3 * n])
groups = defaultdict(Counter)
for y in range(h):
    row = y * w
    crow = (y // 2) * w
    for x in range(w):
        c = crow + (x // 2) * 2
        key = (Y[row + x] >> 6, C[c] >> 6, C[c + 1] >> 6)
        p = 4 * (row + x)
        groups[key][a[p:p + 3]] += 1
off = 0
maxd = 0
for key, cnt in groups.items():
    mode = cnt.most_common(1)[0][0]
    for v, k in cnt.items():
        if v != mode:
            off += k
            maxd = max(maxd, max(abs(i - j) for i, j in zip(v, mode)))
shared = sum(sum(c.values()) for c in groups.values() if sum(c.values()) > 1)
print(f"keys={len(groups)} pixels_in_shared_keys={100 * shared / n:.2f}% "
      f"pixels_off_their_key's_RGB={100 * off / n:.3f}% max_channel_diff={maxd}")
