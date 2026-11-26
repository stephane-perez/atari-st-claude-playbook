# 15 — Atari disk structures: partitions, boot sector, FAT, directories

What a program that reads or repairs disks on the Atari must know: physical sector 0, partition
types, the partition layout, the FAT, directory entries, and what modern media (DOS/GPT
partition tables, VFAT long names, FAT32) add. Learnt while porting and testing a GPL disk
utility (Medic / optimiser / undelete family) on ST, STE and Falcon.

Main written source: the Diamond Edge 2.57 manual, chapter 2 "The Anatomy of a Disk" (Roger
Burrows, CC BY-SA 4.0, not in this repository):
<https://sourceforge.net/projects/diamond-edge/files/releases/v2.57/v257_manual.pdf/download>.

## Status of the information (read this first)

| Point | Status |
|---|---|
| AHDI root sector, GEM/BGM/XGM, ICD entries, boot sector, FAT values, directory entry | From the manual (2017), consistent with what the disk images of the sessions contained. ICD/Supra extra entries and XGM chains **not exercised** in the sessions. |
| DOS MBR / GPT on Atari media, hybrid sectors, `F32` partitions | Seen in real images (Falcon CompactFlash card: MBR; SD cards: GPT, and AHDI with a `F32` entry made by HDDRIVER). Not in the manual. |
| XHDI `XHInqDev2` partition ids (`F32`, `\0D` + DOS type) | Read in the EmuTOS 1.4 sources; verified in Hatari with EmuTOS 1.4 and with TOS 1.62 + HDDRIVER 12.53. |
| VFAT long names, end-of-chain `$FFF8`, read-error simulation | Verified **in Hatari** (EmuTOS 1.3, TOS 1.62 + HDDRIVER) against `fsck.fat` and against the original program. |
| Optimising a partition with the ported utility | Done by the user on a real Falcon030 (CompactFlash); STE and Falcon CT60 also used. |

## Physical sector 0 (AHDI root sector)

Big-endian (Motorola). Physical sectors are always 512 bytes.

| Offset | Content |
|---|---|
| `0x1C2` | total disk size (long, sectors) |
| `0x1C6`, `0x1D2`, `0x1DE`, `0x1EA` | 4 partition entries of 12 bytes |
| `0x1F6` / `0x1FA` | start / size of the bad sector list |
| whole sector | word checksum `$1234` = bootable root sector (driver code, e.g. HDDRIVER) |

Partition entry: flag byte (bit 0 active, bit 7 bootable), 3-character id, start sector (long),
size in sectors (long).

- **GEM**: logical sector = physical sector (512 bytes); ≤ 16 MB on TOS 1.00/1.02, ≤ 32 MB on
  TOS ≥ 1.04.
- **BGM** ("big GEM"): logical sectors of 512·2^n bytes (1024, 2048…), translated by the driver.
  Partitions ≤ 32767 sectors on TOS 1.00, ≤ 65535 on TOS ≥ 1.04; TOS 4.00 accepts logical sectors
  up to 16384 bytes. A 1-byte file takes a whole cluster: 2 × 2048 bytes on a 2 KB-sector BGM.
- **XGM**: extended partition; points to another pseudo-root sector, chainable (more than four
  partitions).
- Others: `F32` (FAT32, written by HDDRIVER), `ACK`/`OOP` (Spectre), `OS9`.
- **ICD/Supra**: up to 12 entries in sector 0, the extra ones at `0x156`, `0x162`, … `0x1AA`
  (step 12). An Atari (AHDI) driver only sees the first four.

### DOS MBR, GPT and hybrid sectors (not in the manual)

EmuTOS, HDDRIVER and PC-formatted cards also use a DOS **master boot record**: table at
`0x1BE`–`0x1FD` (4 entries of 16 bytes: status `0x00`/`0x80`, type at +4, start LBA at +8 and
size at +12, little-endian), signature `0x55 0xAA` at `0x1FE`. A **GPT** disk has a protective
MBR (type `0xEE`) in sector 0 and `EFI PART` in sector 1. HDDRIVER can also write **hybrid**
sectors holding both an AHDI and a DOS table.

**The DOS table overlaps the AHDI entries** (`0x1C6`–`0x1F5`): a tool that reads sector 0 as AHDI
sees garbage partitions, and one that writes an AHDI sector there destroys the MBR/GPT table.
Detect it before writing: signature `55AA` and every used entry with status `0x00` or `0x80`.

## Inside a partition

```
| boot sector | reserved | FAT #1 | FAT #2 | root directory (fixed size) | data area: clusters 2, 3, … |
```

Logical sectors: FAT n at `reserved + n·spf`, root at `reserved + nfat·spf`, data at that +
root sectors. Everything before the data area is "control sectors".

### Boot sector (logical sector 0, little-endian / Intel)

| Offset | Size | Content |
|---|---|---|
| `0x00` | 2 | branch (if bootable) |
| `0x02` | 6 | OEM / filler |
| `0x08` | 3 | 24-bit serial number (media change detection) |
| `0x0B` | 2 | bytes per logical sector (512, 1024, 2048…) |
| `0x0D` | 1 | sectors per cluster (usually 2) |
| `0x0E` | 2 | reserved sectors (usually 1) |
| `0x10` | 1 | number of FATs (2) |
| `0x11` | 2 | root directory entries |
| `0x13` | 2 | total logical sectors (16-bit) |
| `0x15` | 1 | media descriptor (ignored by the Atari BIOS) |
| `0x16` | 2 | sectors per FAT |
| `0x18` / `0x1A` / `0x1C` | 2 each | sectors per track, sides, hidden sectors (floppies) |

Word checksum `$1234` over the sector = bootable (floppies). FAT32 is recognisable by a 16-bit
sectors-per-FAT of 0 and `FAT32` at `0x52`; TOS cannot use it (EmuTOS and HDDRIVER still give it
a drive letter: the BIOS then fails to read its boot sector).

### FAT

- 12-bit (≤ 4096 clusters, floppies: two entries in three bytes) or 16-bit (little-endian).
- Values: `0` free, `$FF7`/`$FFF7` bad cluster, `$FFF`/`$FFFF` end of chain. Clusters start at 2.
- **Microsoft's specification allows any of `$FFF8`–`$FFFF` (`$FF8`–`$FFF`) as end of chain.**
  TOS writes `$FFFF`; a tool that only accepts `$FFFF` reports every chain ending in `$FFF8` as a
  bad FAT entry and truncates it on "repair" (seen with the original program, in Hatari).
  Normalise the end values when the FAT is loaded.
- Two copies; a repair tool compares them and lets the user choose one when they differ.

### Directory entries (32 bytes, little-endian)

| Offset | Size | Content |
|---|---|---|
| `0x00` | 8 + 3 | name and extension, space padded, no dot; `$E5` first byte = deleted |
| `0x0B` | 1 | attribute: `0x01` RO, `0x02` hidden, `0x04` system, `0x08` volume, `0x10` directory, `0x20` archive |
| `0x0C` | 10 | "reserved" for TOS; VFAT systems store creation time, access date, high cluster there |
| `0x16` / `0x18` | 2 / 2 | time / date |
| `0x1A` | 2 | first cluster |
| `0x1C` | 4 | size |

- Deleting a file sets the `$E5` mark and **clears its FAT chain**; the data stays until reused.
  Recovery guesses consecutive free clusters, unless a copy of the FAT taken before the deletion
  exists (a "mirror" saved at boot by an AUTO program).
- The root directory has a fixed size; subdirectories are files with their own FAT chain, start
  with `.` and `..`, and grow one cluster at a time (directory fragmentation).

### VFAT long names on Atari media

Windows, Linux, macOS and MiNT store a long name as entries with attribute **`$0F`** (RO + hidden
+ system + volume) **just before** the 8.3 entry: ordinal byte (`$40` on the first, last part),
UTF-16 characters at `0x01`, `0x0E`, `0x1C`, checksum of the 8.3 name at `0x0D`
(`sum = ((sum & 1) << 7) + (sum >> 1) + c` over the 11 bytes), first cluster 0.

Pitfalls for an Atari tool that predates VFAT (all seen in Hatari with the original program):

- the volume bit is set: "keep one volume label, delete the others" deletes the long names;
- sorting a directory (folders first) separates a long name from its 8.3 entry;
- a check of the attribute byte / reserved bytes calls them bad entries, and "repair" deletes them;
- a loop "while the entries are folders" stops at the first long name.

TOS deletes only the 8.3 entry (`$E5`) and leaves the long name: these **orphans** are the only
long-name entries a checker should remove (Windows' chkdsk does the same).

## FAT32 and partition ids through XHDI

`XHInqDev2` (XHDI ≥ 1.10, opcode 12, called in supervisor mode) returns the partition id of a
BIOS drive: `F32` for an Atari FAT32 partition, or `\0`, `'D'`, DOS type for an MBR partition
(FAT32 types `$0B`, `$0C`, `$1B`, `$1C`). Check the XHDI magic `$27011992` before the entry point
(cookie `XHDI`) and the version (`XHGetVersion` ≥ `$0110`). The XHDI parameters are 16-bit words
on the stack: from GCC with 32-bit `int`, call it through a small assembly stub.

## Testing disk tools in Hatari

- Build images with `mkfs.fat` and mtools (`-i image@@offset`, `MTOOLS_SKIP_CHECK=1`); an AHDI
  root sector is a few lines of Python (`struct.pack('>B3sII', ...)` at `0x1C6`).
  `tools/mkacsi.py` builds an MBR image.
- EmuTOS mounts AHDI and MBR ACSI images by itself (`--acsi 0=image`), no driver needed.
  HDDRIVER: boot it from a bootable root sector, or run `HDDRIVER.PRG` from the AUTO folder of a
  floppy (TOS 1.62 needs `--machine ste`).
- **Differential test**: run the original program and the modified one on two copies of the same
  image with the same keys and clicks, then compare the images byte for byte, run `fsck.fat -n`
  on the partition and compare per-file hashes.
- **Read error**: move a cluster to the end of the partition and truncate the image there:
  Hatari's ACSI disk then fails the read (BIOS error -2).
- Use `--fast-forward on`; a long operation (optimisation) interrupted by the end of the test
  leaves a disk that `fsck` finds consistent but with corrupted file contents: wait long enough.

## Porting old disk code from Lattice C to GCC

- **`short` against `unsigned short`**: Lattice C compared them on 16 bits; GCC promotes both to
  `int`. A cluster `$FFFF` read into a `short` is -1, never equal to an `unsigned short` 65535:
  the end of chain is never found and the program walks the FAT until it crashes. GCC does not
  warn; a clang AST scan finds every such comparison (cast to `(short)` for a 16-bit comparison).
- Lattice's `fopen(name, "ra")` (text mode) removed the CR of CR LF lines; libcmini and MiNTLib
  do not (a CR glyph appears in the text viewer).
- Cluster numbers kept in `short` limit partitions to 32765 data clusters: refuse bigger ones.
