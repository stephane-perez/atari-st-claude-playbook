#!/usr/bin/env python3
"""stx.py: reads a Pasti (.STX) floppy image: lists tracks and sectors,
reports protection marks, writes a flat sector image.

usage:
  stx.py IMAGE.stx                 summary + unusual tracks only
  stx.py IMAGE.stx --verbose       every track (sector order, sizes, flags)
  stx.py IMAGE.stx --dump OUT.st   flat image: cylinder by cylinder, side 0 then
                                   side 1, sectors 1..N of 512 bytes
                                   (the order of a .ST file and of most track
                                   loaders); missing sectors filled with $E5

What is reported as unusual: sector size other than 512, ID field not matching
the track (cylinder/side), FDC status flags (CRC error $08, record not found
$10, deleted data $20, fuzzy bits $80), a sector with a timing record
(variable bit rate, typical of key sectors such as Copylock ST), fuzzy masks.

Format notes (Pasti, little-endian):
  file header 16 bytes: "RSY\\0", version, tool, reserved, track count, revision
  track record: size(4) fuzzy-count(4) sectors(2) flags(2) track-length(2)
                number(1: bit 7 = side, bits 0-6 = cylinder) type(1)
  flags bit 0 = sector descriptors present (16 bytes each: data offset(4),
  bit position(2), read time(2), ID track/side/number/size(4), ID CRC(2),
  FDC status(1), reserved(1)); then fuzzy mask; bit 6 = track image present
  (bit 7: preceded by a 2-byte sync offset), then a 2-byte image size.
  Without bit 0: the sectors follow the header, 512 bytes each.

Verified on one Pasti v3 image (80 cylinders x 2 sides x 10 sectors, sector
descriptors and track images on every track): the flat image is coherent
(boot sector checksum $1234, loader files found where its table says). The
"no descriptor" track type was not present in that image: untested.
"""
import collections
import struct
import sys


def parse(path):
    """Returns (header dict, list of track dicts)."""
    d = open(path, "rb").read()
    if d[:4] != b"RSY\0":
        raise ValueError("not a Pasti file (no RSY header)")
    version, tool, _, ntracks, rev = struct.unpack_from("<HHHBB", d, 4)
    hdr = dict(version=version, tool=tool, tracks=ntracks, revision=rev)
    pos = 16
    tracks = []
    for _ in range(ntracks):
        rec, fuzzy, nsec, flags, tlen, tnum, ttype = struct.unpack_from("<IIHHHBB", d, pos)
        base = pos + 16
        t = dict(off=pos, nsec=nsec, flags=flags, tlen=tlen, fuzzy=fuzzy,
                 cyl=tnum & 0x7F, side=tnum >> 7, type=ttype, sectors=[], image=None)
        if flags & 1:
            descs = [struct.unpack_from("<IHHBBBBHBB", d, base + 16 * i) for i in range(nsec)]
            p = base + 16 * nsec + fuzzy
            tdata = p
            if flags & 0x40:
                if flags & 0x80:
                    p += 2
                t["image"] = (p + 2, struct.unpack_from("<H", d, p)[0])
            for (o, bitpos, rtime, ct, ch, cn, cs, crc, fdc, _r) in descs:
                size = 128 << (cs & 3)
                data = None if fdc & 0x10 else d[tdata + o: tdata + o + size]
                t["sectors"].append(dict(id_track=ct, id_side=ch, num=cn, size=size, crc=crc,
                                         fdc=fdc, bitpos=bitpos, rtime=rtime, data=data))
        else:
            for i in range(nsec):
                t["sectors"].append(dict(id_track=t["cyl"], id_side=t["side"], num=i + 1,
                                         size=512, crc=None, fdc=0, bitpos=0, rtime=0,
                                         data=d[base + 512 * i: base + 512 * (i + 1)]))
        tracks.append(t)
        pos += rec
    return hdr, tracks


def unusual(t, s):
    why = []
    if s["size"] != 512:
        why.append("size %d" % s["size"])
    if s["id_track"] != t["cyl"] or s["id_side"] != t["side"]:
        why.append("ID t%d s%d" % (s["id_track"], s["id_side"]))
    if s["fdc"] & 0x08:
        why.append("CRC error")
    if s["fdc"] & 0x10:
        why.append("record not found")
    if s["fdc"] & 0x20:
        why.append("deleted data")
    if s["fdc"] & 0x80:
        why.append("fuzzy bits")
    if s["rtime"]:
        why.append("timing record")
    return why


def flat(tracks):
    """Flat image (bytes) and its geometry (cylinders, sides, sectors/track)."""
    spt = collections.Counter(
        len([s for s in t["sectors"] if s["size"] == 512 and 1 <= s["num"] <= 12])
        for t in tracks).most_common(1)[0][0]
    cyls = max(t["cyl"] for t in tracks) + 1
    sides = max(t["side"] for t in tracks) + 1
    img = bytearray(b"\xE5" * (512 * spt * sides * cyls))
    for t in tracks:
        for s in t["sectors"]:
            if s["data"] is not None and s["size"] == 512 and 1 <= s["num"] <= spt:
                o = ((t["cyl"] * sides + t["side"]) * spt + s["num"] - 1) * 512
                img[o:o + 512] = s["data"]
    return bytes(img), (cyls, sides, spt)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    hdr, tracks = parse(argv[0])
    verbose = "--verbose" in argv
    print("Pasti version %(version)d, tool %(tool)#x, %(tracks)d tracks" % hdr)
    for t in tracks:
        odd = [(s, unusual(t, s)) for s in t["sectors"]]
        odd = [(s, w) for s, w in odd if w]
        if verbose or odd or t["fuzzy"]:
            print("cyl %2d side %d: %2d sectors, order %s, flags %04x, track %d bytes%s" % (
                t["cyl"], t["side"], t["nsec"], [s["num"] for s in t["sectors"]], t["flags"],
                t["tlen"], ", fuzzy mask %d bytes" % t["fuzzy"] if t["fuzzy"] else ""))
            for s, w in odd:
                print("    sector %d: %s" % (s["num"], ", ".join(w)))
    if "--dump" in argv:
        out = argv[argv.index("--dump") + 1]
        img, (c, sd, spt) = flat(tracks)
        open(out, "wb").write(img)
        print("flat image %d x %d x %d -> %s (%d bytes)" % (c, sd, spt, out, len(img)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
