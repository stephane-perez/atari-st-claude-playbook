#!/usr/bin/env python3
"""Inspects the header of a GEMDOS program (.PRG/.TOS/.APP): sizes, flags,
symbol table, relocations, and known packer signatures.

  python3 tools/prg_info.py PROG.PRG            # summary
  python3 tools/prg_info.py PROG.PRG --relocs   # list of relocated addresses

First reflex before any reverse engineering: is it really a PRG (word $601A)?
is it packed (Pack-Ice "ICE!", Atomik "ATM5"...)? is there a symbol table?
Many files called "floppy image" or "game" are in reality just packed PRGs.
"""
import struct
import sys

PACKERS = [(b"ICE!", "Pack-Ice ('ICE!' stream)"), (b"Ice!", "old Pack-Ice ('Ice!')"),
           (b"Pack-Ice", "Pack-Ice ('Pack-Ice' string)"), (b"ATM5", "Atomik ('ATM5')"),
           (b"ATOM", "Atomik ('ATOM')"), (b"LSD!", "LSD packer"), (b"JEK!", "JAM packer"),
           (b"RNC", "Rob Northen Compression"), (b"AUT2", "Automation 2.x"),
           (b"Fire", "Fire packer")]


def relocs(d, base):
    """Returns the list of offsets (in the text+data image) to relocate."""
    out = []
    if base + 4 > len(d):
        return out
    off = struct.unpack(">I", d[base:base + 4])[0]
    if off == 0:
        return out
    p = base + 4
    out.append(off)
    while p < len(d):
        b = d[p]
        p += 1
        if b == 0:
            break
        if b == 1:
            off += 254
        else:
            off += b
            out.append(off)
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    d = open(sys.argv[1], "rb").read()
    print("file           :", sys.argv[1], "(%d bytes)" % len(d))
    if d[:2] != b"\x60\x1a":
        print("header         : NOT a GEMDOS PRG (word $%04X instead of $601A)" % struct.unpack(">H", d[:2])[0])
        print("                 -> raw memory image, disk image, or data file?")
        return
    magic, tlen, dlen, blen, slen, _res, flags, absf = struct.unpack(">HIIIIIIH", d[:28])
    print("text           : $%X (%d)" % (tlen, tlen))
    print("data           : $%X (%d)" % (dlen, dlen))
    print("bss            : $%X (%d)" % (blen, blen))
    print("symbols        : %d bytes%s" % (slen, " (DRI/GST table)" if slen else " (none)"))
    ftxt = []
    if flags & 1: ftxt.append("fastload (clears only the bss)")
    if flags & 2: ftxt.append("load into TT-RAM")
    if flags & 4: ftxt.append("malloc in TT-RAM")
    print("flags          : $%X %s" % (flags, ", ".join(ftxt)))
    base = 28 + tlen + dlen + slen
    rl = relocs(d, base) if not absf else []
    print("relocation     : %s" % ("disabled (absflag=%d)" % absf if absf else "%d entries" % len(rl)))
    img = d[28:28 + tlen + dlen]
    print("first bytes    :", img[:16].hex(" "))
    found = []
    for sig, name in PACKERS:
        i = d.find(sig, 0, 4096)
        if i >= 0:
            found.append("%s at file offset $%X" % (name, i))
    print("packed?         :", "; ".join(found) if found else "no known signature in the first 4 KB")
    if tlen + 28 + dlen + slen > len(d):
        print("WARNING        : header sizes larger than the file size")
    if "--relocs" in sys.argv:
        print("relocations    :", " ".join("$%X" % r for r in rl))


if __name__ == "__main__":
    main()
