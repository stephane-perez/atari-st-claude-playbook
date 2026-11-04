#!/usr/bin/env python3
"""unice.py: depacks Pack-Ice data, versions 2.3x ("Ice!") and 2.40 ("ICE!").

usage:
  unice.py [--variant 2.3|2.4] IN OUT     depack one file
  unice.py [--variant 2.3|2.4] --scan IN [OUTDIR]
                         list every "Ice!"/"ICE!" block inside IN (memory dump,
                         flat floppy image...), depack the coherent ones and,
                         with OUTDIR, write them there
The variant is chosen from the header ("Ice!" -> 2.3, "ICE!" -> 2.4);
--variant forces it (a lower-case header does not prove the version).

Format (big-endian):
  +0 magic   +4 packed length (header included)   +8 unpacked length
The stream is read BACKWARDS from the end of the packed data, the output is
written backwards from the end of the destination. Both variants share the
literal and length tables; they differ in:
  - bit buffer: 2.3x = long word refilled 4 bytes at a time, 2.40 = byte;
    both with a sentinel bit;
  - distances: 2.3x adds $20 / 0 / $120 (short strings: 0 / $40),
    2.40 adds $1F / -1 / $11F (short strings: -1 / $3F) and turns a negative
    distance into a repeat of the last byte;
  - optional final "picture" pass (bitplane re-interleaving, 4 words per
    block): 2.3x always does 4000 blocks; 2.40 reads a block count, and as
    published its routine clobbers the bit buffer just before (move.w #$0F9F,d7)
    so that the count always starts with the bits 001111: emulated as is.

Verification (docs/03):
  - 2.3x: identical byte for byte to the depacker of a 1992 commercial program
    run in Unicorn (68000) on its 47 packed files, and on random streams
    (differential fuzzing, every path including runs of more than 268 literals);
  - 2.40: identical to the published PACK-ICE 2.40 routine (ice_unpa.s),
    re-typed, assembled with vasm and run in Unicorn, on random streams
    (differential fuzzing, every path including the picture pass).
    No real "ICE!" file was available when this was written: confirm on one.
  - mutation tests: errors in the tables are detected.
A game may transform the data again after depacking (one keeps its pictures
bit-transposed and undoes it itself): look at the result before concluding.
"""
import os
import struct
import sys

# literal run: (number of bits, escape value, base), tried in this order
DIRECT = [(2, 3, 1), (2, 3, 4), (3, 7, 7), (8, 0xFF, 14), (15, None, 269)]
# string length, index = number of leading 1 bits (0..4); copied bytes = length + 2
LEN_READ = [0, 0, 1, 2, 10]
LEN_BASE = [0, 1, 2, 4, 8]

VARIANTS = {
    "2.3": dict(magic=b"Ice!", long_buffer=True,
                dist=[(8, 0x20), (5, 0), (12, 0x120)], short=[(6, 0), (9, 0x40)],
                negative_repeat=False, picture_count=False),
    "2.4": dict(magic=b"ICE!", long_buffer=False,
                dist=[(8, 0x1F), (5, -1), (12, 0x11F)], short=[(6, -1), (9, 0x3F)],
                negative_repeat=True, picture_count=True),
}
MAGICS = {v["magic"]: k for k, v in VARIANTS.items()}


class IceError(Exception):
    pass


class _Bits:
    """Backward bit reader sharing its pointer with the literal bytes."""

    def __init__(self, data, end, long_buffer):
        self.d = data
        self.p = end
        self.long = long_buffer
        self.width = 32 if long_buffer else 8
        self.mask = (1 << self.width) - 1
        self.buf = self._long() if long_buffer else self.byte()

    def _long(self):
        self.p -= 4
        if self.p < 12:
            raise IceError("read inside the header")
        return struct.unpack_from(">I", self.d, self.p)[0]

    def byte(self):
        self.p -= 1
        if self.p < 12:
            raise IceError("read inside the header")
        return self.d[self.p]

    def bit(self):
        top = self.width - 1
        c = self.buf >> top
        self.buf = (self.buf << 1) & self.mask
        if self.buf == 0:                       # sentinel reached: refill
            nb = self._long() if self.long else self.byte()
            # addx: the bit shifted in is the carry of the shift above (the
            # sentinel); the 2.3x routine forces it to 1 on an odd address
            x = 1 if (self.long and self.p & 1) else c
            c = nb >> top
            self.buf = ((nb << 1) | x) & self.mask
        return c

    def bits(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | self.bit()
        return v


def variant_of(data, off=0):
    return MAGICS.get(bytes(data[off:off + 4]))


def header(data, off=0):
    if variant_of(data, off) is None:
        raise IceError("no \"Ice!\"/\"ICE!\" header")
    return struct.unpack_from(">II", data, off + 4)


def depack(data, off=0, variant=None):
    """Depacks the block at data[off:]; returns the unpacked bytes."""
    plen, ulen = header(data, off)
    v = VARIANTS[variant or variant_of(data, off)]
    if plen < 13 or off + plen > len(data):
        raise IceError("packed length %d out of range" % plen)
    if ulen == 0 or ulen > 16 * 1024 * 1024:
        raise IceError("unpacked length %d out of range" % ulen)
    b = _Bits(bytes(data[off:off + plen]), plen, v["long_buffer"])
    out = bytearray(ulen)
    w = ulen                                     # lowest written byte (a6)

    def put(x):
        nonlocal w
        w -= 1
        if w < 0:
            raise IceError("output overflow")
        out[w] = x

    while True:
        if b.bit():                              # literal run
            n = 0
            if b.bit():
                for nbits, esc, base in DIRECT:
                    n = b.bits(nbits)
                    if n != esc:
                        break
                n += base
            for _ in range(n + 1):
                put(b.byte())
        if w <= 0:
            break
        i = 0                                    # string
        while i < 4 and b.bit():
            i += 1
        length = LEN_BASE[i] + (b.bits(LEN_READ[i]) if LEN_READ[i] else 0)
        if length:
            j = 0
            while j < 2 and b.bit():
                j += 1
            nb, add = v["dist"][j]
            dist = b.bits(nb) + add
            if dist < 0 and v["negative_repeat"]:
                dist -= length
        else:
            nb, add = v["short"][b.bit()]
            dist = b.bits(nb) + add
        s = w + length + 2 + dist                # copy downwards, byte by byte
        for _ in range(length + 2):
            s -= 1
            if s >= ulen or s < w:
                raise IceError("string outside the written data")
            put(out[s])
    if b.bit():                                  # optional picture pass
        blocks = 4000
        if v["picture_count"]:
            b.buf = 0x9F                         # move.w #$0F9F,d7 (see above)
            if b.bit():
                blocks = b.bits(16) + 1
            else:                                # unreachable with the published routine
                blocks = 0x0F3E + 1
        a = ulen
        if blocks * 8 > ulen:
            raise IceError("picture pass of %d blocks larger than the output" % blocks)
        for _ in range(blocks):
            planes = [0, 0, 0, 0]
            for _ in range(4):
                a -= 2
                wd = struct.unpack_from(">H", out, a)[0]
                for _ in range(4):
                    for k in range(4):
                        planes[k] = ((planes[k] << 1) | (wd >> 15)) & 0xFFFF
                        wd = (wd << 1) & 0xFFFF
            struct.pack_into(">4H", out, a, *planes)
    return bytes(out)


def scan(data, variant=None):
    """Yields (offset, variant, packed length, unpacked length, bytes or error)."""
    for p in sorted(i for m in MAGICS for i in _find_all(data, m)):
        try:
            plen, ulen = header(data, p)
            yield p, variant or variant_of(data, p), plen, ulen, depack(data, p, variant)
        except (IceError, struct.error, IndexError) as e:
            yield p, variant or variant_of(data, p), None, None, e


def _find_all(data, pat):
    i = data.find(pat)
    while i >= 0:
        yield i
        i = data.find(pat, i + 1)


def main(argv):
    variant = None
    if len(argv) >= 2 and argv[0] == "--variant":
        variant = argv[1]
        if variant not in VARIANTS:
            print("variant: 2.3 or 2.4")
            return 2
        argv = argv[2:]
    if len(argv) >= 2 and argv[0] == "--scan":
        data = open(argv[1], "rb").read()
        outdir = argv[2] if len(argv) > 2 else None
        if outdir:
            os.makedirs(outdir, exist_ok=True)
        for off, var, plen, ulen, res in scan(data, variant):
            if isinstance(res, Exception):
                print("%08x  %s  not depacked: %s" % (off, var, res))
                continue
            print("%08x  %s  %7d -> %7d bytes" % (off, var, plen, ulen))
            if outdir:
                open(os.path.join(outdir, "%08x.bin" % off), "wb").write(res)
        return 0
    if len(argv) != 2:
        print(__doc__)
        return 2
    data = open(argv[0], "rb").read()
    out = depack(data, 0, variant)
    open(argv[1], "wb").write(out)
    print("%s: Pack-Ice %s, %d -> %d bytes" % (argv[0], variant or variant_of(data), len(data), len(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
