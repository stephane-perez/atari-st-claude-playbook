#!/usr/bin/env python3
"""Creates an Atari ST floppy image (.ST), FAT12, and copies files into it.
No external dependency (no mtools, no root). Reproducible result.

  python3 tools/mkst.py disk.st LABEL  source:DEST  [source:DEST ...]  [--tracks 80 --spt 9 --sides 2]

  DEST is an 8.3 path; only one folder level is handled:
    build/INTRO.PRG:AUTO/INTRO.PRG   -> started by itself at boot (AUTO folder)
    build/INTRO.PRG:INTRO.PRG        -> at the root

Default geometry: 80 tracks x 2 sides x 9 sectors = 720 KB (media $F9).
For an "820 KB" floppy: --tracks 82 --spt 10.
To check: mdir -i disk.st ::  ;  fsck.fat -n disk.st
File date: SOURCE_DATE_EPOCH variable, otherwise 2026-01-01 09:00.
"""
import argparse
import os
import struct
import sys
import time

SECTOR = 512


def name83(n):
    base, _, ext = n.upper().partition(".")
    if not (1 <= len(base) <= 8 and len(ext) <= 3):
        sys.exit("invalid 8.3 name: " + n)
    return (base.ljust(8) + ext.ljust(3)).encode("ascii")


class Disk:
    def __init__(self, label, tracks, sides, spt, spc=2, root_entries=112, epoch=None):
        self.total = tracks * sides * spt
        self.spc, self.spt, self.sides, self.root_entries = spc, spt, sides, root_entries
        self.reserved, self.nfats = 1, 2
        self.media = 0xF9 if sides == 2 else 0xF8
        # number of FAT sectors: the smallest that covers all clusters
        spf = 1
        while True:
            data0 = self.reserved + self.nfats * spf + root_entries * 32 // SECTOR
            ncl = (self.total - data0) // spc
            if (ncl + 2) * 3 // 2 <= spf * SECTOR:
                break
            spf += 1
        self.spf, self.data0, self.ncl = spf, data0, ncl
        self.img = bytearray(self.total * SECTOR)
        self.fat = [0] * (ncl + 2)
        self.fat[0], self.fat[1] = 0xF00 | self.media, 0xFFF
        self.next = 2
        t = time.gmtime(epoch if epoch is not None else 1767258000)  # 2026-01-01 09:00
        self.date = ((t.tm_year - 1980) << 9) | (t.tm_mon << 5) | t.tm_mday
        self.time = (t.tm_hour << 11) | (t.tm_min << 5) | (t.tm_sec // 2)
        self.label = label
        self.root = []            # 32-byte entries
        self.dirs = {}            # name -> (first cluster, list of entries)

    def entry(self, name11, attr, cluster, size):
        return struct.pack("<11sB10xHHHL", name11, attr, self.time, self.date, cluster, size)

    def alloc(self, nbytes):
        n = max(1, -(-nbytes // (self.spc * SECTOR))) if nbytes else 0
        if not n:
            return 0, []
        if self.next + n > self.ncl + 2:
            sys.exit("floppy full")
        cl = list(range(self.next, self.next + n))
        self.next += n
        for a, b in zip(cl, cl[1:]):
            self.fat[a] = b
        self.fat[cl[-1]] = 0xFFF
        return cl[0], cl

    def write_chain(self, chain, data):
        csz = self.spc * SECTOR
        for i, c in enumerate(chain):
            off = (self.data0 + (c - 2) * self.spc) * SECTOR
            chunk = data[i * csz:(i + 1) * csz]
            self.img[off:off + len(chunk)] = chunk

    def add(self, src, dest):
        data = open(src, "rb").read()
        parts = dest.replace("\\", "/").split("/")
        first, chain = self.alloc(len(data))
        self.write_chain(chain, data)
        e = self.entry(name83(parts[-1]), 0x20, first, len(data))
        if len(parts) == 1:
            self.root.append(e)
        elif len(parts) == 2:
            d = parts[0].upper()
            if d not in self.dirs:
                cl, _ = self.alloc(self.spc * SECTOR)   # one cluster for the folder
                self.dirs[d] = (cl, [])
                self.root.append(self.entry(name83(d), 0x10, cl, 0))
            self.dirs[d][1].append(e)
        else:
            sys.exit("only one folder level is handled: " + dest)

    def finish(self):
        for d, (cl, ents) in self.dirs.items():
            dot = self.entry(b".          ", 0x10, cl, 0)
            dotdot = self.entry(b"..         ", 0x10, 0, 0)
            blob = b"".join([dot, dotdot] + ents)
            if len(blob) > self.spc * SECTOR:
                sys.exit("folder too large: " + d)
            self.write_chain([cl], blob)
        if len(self.root) > self.root_entries:
            sys.exit("root full")
        # boot sector (BPB)
        b = bytearray(SECTOR)
        b[0:3] = b"\xEB\x3C\x90"
        b[3:11] = b"MKST    "
        struct.pack_into("<HBHBHHBHHHL", b, 11, SECTOR, self.spc, self.reserved, self.nfats,
                         self.root_entries, self.total, self.media, self.spf, self.spt, self.sides, 0)
        b[510:512] = b"\x55\xAA"
        self.img[0:SECTOR] = b
        # FAT12, 2 copies
        fb = bytearray(self.spf * SECTOR)
        for i in range(0, len(self.fat), 2):
            a = self.fat[i]
            c = self.fat[i + 1] if i + 1 < len(self.fat) else 0
            o = i * 3 // 2
            fb[o:o + 3] = bytes([a & 0xFF, (a >> 8) | ((c & 0xF) << 4), c >> 4])
        for k in range(self.nfats):
            o = (self.reserved + k * self.spf) * SECTOR
            self.img[o:o + len(fb)] = fb
        # root (the label first)
        root = self.entry(self.label.upper().ljust(11)[:11].encode("ascii"), 0x08, 0, 0) if self.label else b""
        blob = root + b"".join(self.root)
        o = (self.reserved + self.nfats * self.spf) * SECTOR
        self.img[o:o + len(blob)] = blob
        return bytes(self.img)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("label")
    ap.add_argument("files", nargs="*", help="source:DEST")
    ap.add_argument("--tracks", type=int, default=80)
    ap.add_argument("--sides", type=int, default=2)
    ap.add_argument("--spt", type=int, default=9)
    a = ap.parse_args()
    epoch = int(os.environ["SOURCE_DATE_EPOCH"]) if "SOURCE_DATE_EPOCH" in os.environ else None
    d = Disk(a.label, a.tracks, a.sides, a.spt, epoch=epoch)
    for f in a.files:
        s, _, dest = f.rpartition(":")
        if not s:
            sys.exit("expected format source:DEST: " + f)
        d.add(s, dest)
    open(a.image, "wb").write(d.finish())
    used = d.next - 2
    print("%s: %d KB, %d/%d clusters used" % (a.image, len(d.img) // 1024, used, d.ncl))


if __name__ == "__main__":
    main()
