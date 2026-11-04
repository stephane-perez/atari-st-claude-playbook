#!/usr/bin/env python3
"""pi1png.py: ST low-resolution picture (PI1 layout: 1 word + 16 palette words +
32000 bytes of 4 interleaved bitplanes) <-> indexed PNG, exact round trip.

usage: pi1png.py topng IN.PI1 OUT.png
       pi1png.py topi1 IN.png OUT.PI1
The first word (resolution in DEGAS, a marker in some games) is kept in a PNG
text chunk "st_word0"; the ST/STE palette words are kept exactly (4-bit STE
components, bit 3 = least significant bit).
"""
import struct, sys
from PIL import Image, PngImagePlugin

def c8(n):  # STE nibble -> 8 bits
    return (((n & 7) << 1) | ((n >> 3) & 1)) * 17
def nib(v):  # 8 bits -> STE nibble
    v4 = v // 17
    return (v4 >> 1) | ((v4 & 1) << 3)

def topng(src, dst):
    d = open(src, 'rb').read()
    assert len(d) >= 32034, 'too short'
    w0 = struct.unpack('>H', d[:2])[0]
    pal = struct.unpack('>16H', d[2:34])
    px = bytearray(320 * 200)
    for blk in range(4000):
        planes = struct.unpack_from('>4H', d, 34 + blk * 8)
        for x in range(16):
            bit = 15 - x
            px[blk * 16 + x] = sum(((planes[p] >> bit) & 1) << p for p in range(4))
    im = Image.frombytes('P', (320, 200), bytes(px))
    flat = []
    for c in pal:
        flat += [c8((c >> 8) & 15), c8((c >> 4) & 15), c8(c & 15)]
    im.putpalette(flat)
    info = PngImagePlugin.PngInfo()
    info.add_text('st_word0', '%04x' % w0)
    info.add_text('st_palette', ' '.join('%03x' % c for c in pal))
    im.save(dst, pnginfo=info)

def topi1(src, dst):
    im = Image.open(src)
    assert im.mode == 'P' and im.size == (320, 200)
    w0 = int(im.info.get('st_word0', '0'), 16)
    if 'st_palette' in im.info:
        pal = [int(x, 16) for x in im.info['st_palette'].split()]
    else:
        p = im.getpalette()[:48]
        pal = [(nib(p[3*i]) << 8) | (nib(p[3*i+1]) << 4) | nib(p[3*i+2]) for i in range(16)]
    px = im.tobytes()
    out = bytearray(struct.pack('>H16H', w0, *pal))
    for blk in range(4000):
        planes = [0, 0, 0, 0]
        for x in range(16):
            v = px[blk * 16 + x]
            for p in range(4):
                planes[p] |= ((v >> p) & 1) << (15 - x)
        out += struct.pack('>4H', *planes)
    open(dst, 'wb').write(out)

if __name__ == '__main__':
    {'topng': topng, 'topi1': topi1}[sys.argv[1]](sys.argv[2], sys.argv[3])
