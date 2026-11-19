#!/usr/bin/env python3
"""Is a Chrome NV12 readback a per-pixel function of the reference NV12?

pixmap.py CHROME.nv12 REF.nv12 W H

For each luma pixel, key = (Y, U, V) of the reference at that pixel. If the
readback is the reference passed through a fixed colour transform, every key
maps to (nearly) one readback value; decode errors scatter. Prints how much
of the luma error the best per-key mapping explains, and the mapping of the
most common keys.
"""
import sys
from collections import Counter, defaultdict

a = open(sys.argv[1], "rb").read()
b = open(sys.argv[2], "rb").read()
w, h = int(sys.argv[3]), int(sys.argv[4])
n = w * h
groups = defaultdict(Counter)
raw_err = 0
for y in range(h):
    row = y * w
    crow = n + (y // 2) * w
    for x in range(w):
        c = crow + (x // 2) * 2
        key = (b[row + x], b[c], b[c + 1])
        v = a[row + x]
        groups[key][v] += 1
        raw_err += (v - b[row + x]) ** 2
fit_err = 0
for key, cnt in groups.items():
    tot = sum(cnt.values())
    mean = sum(v * k for v, k in cnt.items()) / tot
    fit_err += sum(k * (v - mean) ** 2 for v, k in cnt.items())
shared = sum(sum(c.values()) for c in groups.values() if sum(c.values()) > 1)
print(f"keys={len(groups)} pixels_in_shared_keys={100 * shared / n:.2f}% "
      f"luma MSE raw={raw_err / n:.3f} after per-key mapping={fit_err / n:.3f}")
top = sorted(groups.items(), key=lambda kv: -sum(kv[1].values()))[:8]
for key, cnt in top:
    print(" ref YUV", key, "-> chrome Y", cnt.most_common(3))
