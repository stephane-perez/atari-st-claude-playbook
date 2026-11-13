#!/usr/bin/env python3
"""mkacsi.py OUT.img [--size-mb 30] [--add FILE ...] [--cluster-sectors 2]

Builds a raw hard-disk image for Hatari's emulated ACSI port (`--acsi 0=OUT.img`): an MBR with one
FAT16 partition starting at sector 2048, formatted with 1 KB clusters (TOS's own GEMDOS FAT driver
needs clusters of 2 sectors; larger ones make TOS refuse the volume), files copied in contiguous
order into an empty volume (so they are not fragmented).
Needs mkfs.fat (dosfstools) and mtools (mcopy). The image is NOT bootable by itself: Hatari still
needs a hard-disk driver (see docs/11-acsi-streaming.md, "Hatari bench").
"""
import argparse, os, struct, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument('out')
ap.add_argument('--size-mb', type=int, default=30)
ap.add_argument('--cluster-sectors', type=int, default=2)
ap.add_argument('--add', nargs='*', default=[])
a = ap.parse_args()

START = 2048
total = a.size_mb * 2048                     # sectors
part = total - START
with open(a.out, 'wb') as f:
    f.truncate(total * 512)
    mbr = bytearray(512)
    # partition entry 1: active, type 0x06 (FAT16 > 32 MB / BIGDOS), CHS ignored
    mbr[446:462] = struct.pack('<B3sB3sII', 0x80, b'\0\0\0', 0x06, b'\0\0\0', START, part)
    mbr[510:512] = b'\x55\xaa'
    f.write(mbr)
subprocess.check_call(['mkfs.fat', '-F', '16', '-s', str(a.cluster_sectors), '-n', 'ACSITEST',
                       '--offset', str(START), a.out, str(part // 2)], stdout=subprocess.DEVNULL)
env = dict(os.environ, MTOOLS_SKIP_CHECK='1')
for p in a.add:   # copy one by one, in the order given, into the empty volume
    subprocess.check_call(['mcopy', '-i', '%s@@%d' % (a.out, START * 512), p, '::' + os.path.basename(p).upper()], env=env)
print(a.out, 'ok')
