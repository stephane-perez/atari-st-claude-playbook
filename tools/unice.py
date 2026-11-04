#!/usr/bin/env python3
"""unice.py: depacks Pack-Ice 2.3x data (header "Ice!", lower case).

usage:
  unice.py IN OUT              depack one file (IN starts with "Ice!")
  unice.py --scan IN [OUTDIR]  list every "Ice!" block inside IN (memory dump,
                               flat floppy image...), depack the ones that are
                               coherent and, with OUTDIR, write them there

Format (big-endian):
  +0 "Ice!"   +4 packed length (header included)   +8 unpacked length
The stream is read BACKWARDS from the end of the packed data and the output is
written backwards from the end of the destination. The bit buffer is a long
word with a sentinel bit. An optional last pass ("picture" bit) re-interleaves
4000 blocks of 4 words (ST low-resolution bitplanes) at the end of the output.

Pack-Ice 2.40 ("ICE!", upper case) uses a byte-wide bit buffer and different
offset tables: it is NOT handled here (refused with a message).

Verified: output identical byte for byte to the depacker routine of a 1992
commercial program executed in Unicorn (68000), on 47 files (docs/03).
Mutation test: an error in the length or distance tables is detected. NOT
exercised by those 47 files: runs of more than 268 literal bytes (15-bit
count, base 269, taken from the original routine's table): untested.
Note: a game may add its own transformation after depacking (one game keeps
its pictures bit-transposed and undoes it itself): check the result.
"""
import struct
import sys

# literal-run table: (number of bits, escape value, base), tried in this order
DIRECT = [(2, 3, 1), (2, 3, 4), (3, 7, 7), (8, 0xFF, 14), (15, None, 269)]
# string length: index = number of leading 1 bits (0..4)
LEN_READ = [0, 0, 1, 2, 10]      # bits read after the prefix (0 = none)
LEN_BASE = [0, 1, 2, 4, 8]       # length = base + bits; copied bytes = length + 2
# string distance: index = number of leading 1 bits (0..2) -> (bits, base)
DIST = [(8, 0x20), (5, 0), (12, 0x120)]


class IceError(Exception):
    pass


class _Bits:
    def __init__(self, data, end):
        self.d = data
        self.p = end
        self.buf = self._long()

    def _long(self):
        self.p -= 4
        if self.p < 0:
            raise IceError("read before the start of the packed data")
        return struct.unpack_from(">I", self.d, self.p)[0]

    def bit(self):
        c = self.buf >> 31
        self.buf = (self.buf << 1) & 0xFFFFFFFF
        if self.buf == 0:                     # sentinel reached: refill
            nb = self._long()
            c = nb >> 31
            self.buf = ((nb << 1) | 1) & 0xFFFFFFFF
        return c

    def bits(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | self.bit()
        return v

    def byte(self):
        self.p -= 1
        if self.p < 0:
            raise IceError("read before the start of the packed data")
        return self.d[self.p]


def header(data, off=0):
    if data[off:off + 4] == b"ICE!":
        raise IceError("Pack-Ice 2.40 (\"ICE!\") is not supported")
    if data[off:off + 4] != b"Ice!":
        raise IceError("no \"Ice!\" header")
    return struct.unpack_from(">II", data, off + 4)


def depack(data, off=0):
    """Depacks the Ice! block at data[off:]; returns the unpacked bytes."""
    plen, ulen = header(data, off)
    if plen < 16 or off + plen > len(data):
        raise IceError("packed length %d out of range" % plen)
    if ulen == 0 or ulen > 16 * 1024 * 1024:
        raise IceError("unpacked length %d out of range" % ulen)
    src = bytes(data[off:off + plen])
    b = _Bits(src, plen)
    out = bytearray(ulen)
    w = ulen                                   # write pointer (a6)

    def put(v):
        nonlocal w
        w -= 1
        if w < 0:
            raise IceError("output overflow")
        out[w] = v

    while True:
        # literal run
        if b.bit():
            n = 0
            if b.bit():
                for nbits, esc, base in DIRECT:
                    n = b.bits(nbits)
                    if n != esc:
                        break
                n += base
            for _ in range(n + 1):
                if b.p <= 12:
                    raise IceError("literal read inside the header")
                put(b.byte())
        if w <= 0:
            break
        # string (copy from already written data, higher addresses)
        i = 0
        while i < 4 and b.bit():
            i += 1
        length = LEN_BASE[i] + (b.bits(LEN_READ[i]) if LEN_READ[i] else 0)
        if length:
            j = 0
            while j < 2 and b.bit():
                j += 1
            nb, add = DIST[j]
            dist = b.bits(nb) + add
        else:
            if b.bit():
                dist = b.bits(9) + 0x40
            else:
                dist = b.bits(6)
        s = w + length + 2 + dist
        for _ in range(length + 2):
            s -= 1
            if s >= ulen:
                raise IceError("string outside the output")
            put(out[s])
    # optional "picture" pass
    if b.bit():
        if ulen < 32000:
            raise IceError("picture pass on a file shorter than 32000 bytes")
        a = ulen
        for _ in range(4000):
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


def scan(data):
    """Yields (offset, packed length, unpacked length, bytes or error)."""
    p = data.find(b"Ice!")
    while p >= 0:
        try:
            plen, ulen = header(data, p)
            yield p, plen, ulen, depack(data, p)
        except (IceError, struct.error) as e:
            yield p, None, None, e
        p = data.find(b"Ice!", p + 4)


def main(argv):
    if len(argv) >= 2 and argv[0] == "--scan":
        import os
        data = open(argv[1], "rb").read()
        outdir = argv[2] if len(argv) > 2 else None
        if outdir:
            os.makedirs(outdir, exist_ok=True)
        for off, plen, ulen, res in scan(data):
            if isinstance(res, Exception):
                print("%08x  not depacked: %s" % (off, res))
                continue
            print("%08x  %7d -> %7d bytes" % (off, plen, ulen))
            if outdir:
                open(os.path.join(outdir, "%08x.bin" % off), "wb").write(res)
        return 0
    if len(argv) != 2:
        print(__doc__)
        return 2
    data = open(argv[0], "rb").read()
    out = depack(data)
    open(argv[1], "wb").write(out)
    print("%s: %d -> %d bytes" % (argv[0], len(data), len(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
