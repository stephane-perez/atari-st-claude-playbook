#!/usr/bin/env python3
"""Recompresses an IFF ILBM picture with ByteRun1 (PackBits).

  python3 tools/packiff.py in.iff out.iff

Drawing programs often save ILBM uncompressed (BMHD compression 0): a
320x200 16-colour picture is then 32,000 bytes of BODY. Packed row by row
(each plane row separately, as the format requires), it is usually 15-30 %
smaller, which matters when the picture is embedded in a program that must
run in 512 KB. Only BMHD, CMAP and BODY are kept (CAMG and other chunks are
dropped); check that the program's decoder reads ByteRun1 (compression 1).
An already packed picture is unpacked first, then repacked.
"""
import struct
import sys


def packrow(row):
    out = bytearray()
    i, n = 0, len(row)
    while i < n:
        j = i
        while j + 1 < n and row[j + 1] == row[i] and j - i < 127:
            j += 1
        run = j - i + 1
        if run >= 3:                          # repeat: -(run-1), byte
            out += bytes([257 - run, row[i]])
            i += run
            continue
        k = i                                 # literal run, up to 128 bytes
        while k < n and k - i < 128:
            if k + 2 < n and row[k] == row[k + 1] == row[k + 2]:
                break
            k += 1
        if k == i:
            k = i + 1
        out += bytes([k - i - 1]) + row[i:k]
        i = k
    return bytes(out)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    d = open(sys.argv[1], "rb").read()
    if d[:4] != b"FORM" or d[8:12] != b"ILBM":
        sys.exit("not an IFF ILBM file")
    chunks, p = {}, 12
    while p + 8 <= len(d):
        cid = d[p:p + 4]
        size = struct.unpack(">I", d[p + 4:p + 8])[0]
        chunks.setdefault(cid, d[p + 8:p + 8 + size])
        p += 8 + size + (size & 1)
    bmhd = bytearray(chunks[b"BMHD"])
    w, h, _, _, planes = struct.unpack(">HHhhB", bmhd[:9])
    if bmhd[9] not in (0, 2):                 # masking: none or transparent colour
        sys.exit("pictures with a mask plane are not handled")
    body, rowb = chunks[b"BODY"], ((w + 15) // 16) * 2
    total = h * planes * rowb
    if bmhd[10] == 0:
        raw = bytes(body[:total])
    else:
        raw, q = bytearray(), 0
        while len(raw) < total:
            c = body[q]
            q += 1
            if c < 128:
                raw += body[q:q + c + 1]
                q += c + 1
            elif c > 128:
                raw += bytes([body[q]]) * (257 - c)
                q += 1
    if len(raw) != total:
        sys.exit("BODY shorter than the picture")
    packed = b"".join(packrow(raw[r * rowb:(r + 1) * rowb]) for r in range(h * planes))
    bmhd[10] = 1

    def chunk(cid, data):
        return cid + struct.pack(">I", len(data)) + data + (b"\0" if len(data) & 1 else b"")

    form = b"ILBM" + chunk(b"BMHD", bytes(bmhd)) + chunk(b"CMAP", chunks[b"CMAP"]) + chunk(b"BODY", packed)
    open(sys.argv[2], "wb").write(b"FORM" + struct.pack(">I", len(form)) + form)
    print("%s: %d -> %d bytes" % (sys.argv[1], len(d), len(form) + 8))


if __name__ == "__main__":
    main()
