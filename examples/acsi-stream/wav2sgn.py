#!/usr/bin/env python3
# wav2sgn.py in.wav out.sgn : converts the unsigned 8-bit samples of a WAV (standard) to signed ones (what the STE DMA plays)
import sys
b = bytearray(open(sys.argv[1], 'rb').read()); p = 12
while p < len(b):
    cid, sz = bytes(b[p:p+4]), int.from_bytes(b[p+4:p+8], 'little')
    if cid == b'data': break
    p += 8 + sz + (sz & 1)
for i in range(p + 8, min(len(b), p + 8 + sz)): b[i] ^= 0x80
open(sys.argv[2], 'wb').write(b)
