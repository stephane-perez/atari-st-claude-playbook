# 11 — Streaming audio from the hard disk without stalling the frame (ACSI DMA)

Code: `examples/acsi-stream/` (`dmaraw.h`, `dmastream.h`, `wav2sgn.py`, `example.cpp`, MIT like the
rest of the repository). Test tools: `tools/mkacsi.py`, `tools/acsi_bench.py`.

## Problem

An STE program plays a long sample (music, 8-bit stereo, 25 kHz = about 50 KB/s) in a loop with
the sound DMA, and refills the ring buffer from a file. With `Fread` the CPU is blocked while the
disk driver moves the data. On the author's machine (Mega STE, UltraSatan on the ACSI port,
HDDRIVER) every refill overran the VBL: the frame was lost at each disk access (observed on the
CPU-time meter of the demo; no precise per-call timing was recorded).

Remedy: send the read command to the drive by hand and let the **ACSI DMA chip** copy the
sectors into RAM while the CPU keeps working; look at the result one frame later.

## Status of the information (read this first)

| Point | Status |
|---|---|
| Whole chain (probe → ICD READ(10) → DMA → poll) on Mega STE + UltraSatan + HDDRIVER | **Verified on a real machine** by the user (DMA mode reported active, the "streaming" band of the CPU meter only a few raster lines, music continuous). One machine, one adapter, one driver. |
| Classic ACSI READ(6) path | Verified **in Hatari only** (and only by the probe/ring check). Not seen on a real drive. |
| Protocol and data correctness (ring content == file, seam of the loop) | Verified in Hatari 2.4.1, TOS 1.62, HDDRIVER, ICD and ACSI6. |
| Timing gain | **Not measurable in Hatari**: its ACSI disk answers instantly. Only the real machine tells. |
| Meaning of each `$FF8606` bit | Bits 1, 3, 4, 7, 8 as in the DMA description of the Atari Compendium (see Sources). The mode `$0A` used for the last command byte (bit 7 clear) is **not explained by the sources read**: it works, the reason is not established. |
| ICD escape byte `$1F`, PUN_INFO layout | Taken from the working code and from the ICD/XHDI conventions; **not re-checked against a written specification in the session** that produced this page. |

## Registers (hardware, ST/STE)

| Address | Use |
|---|---|
| `$FF8604` (word) | data: command bytes, sector count, status byte |
| `$FF8606` (word, write) | mode: bit 1 = A0, bit 3 = HDC (else FDC), bit 4 = select the sector count register, bit 7 = DRQ from the HDC (else the FDC), bit 8 = write (memory → device); clear = read |
| `$FF8609/0B/0D` | DMA address, high/mid/low bytes (load low, mid, high) |
| MFP GPIP `$FFFA01` bit 5 | HDC interrupt line, **low = command finished** |
| `$43E` (flock) | non-zero: TOS leaves the DMA/floppy alone (VBL floppy check) |

Mode values used: `$198` then `$098` (toggle the direction bit to reset the DMA status, then
select the sector count register, read direction), `$088` (command register, A0 = 0, first
byte), `$08A` (A0 = 1, following bytes), `$00A` (last byte; the command starts and the DMA
runs), `$08A` + read (status byte), `$080` (idle). The DMA stops by itself when the sector
count reaches zero.

## Sequence (see `dmraw_start`, `dmraw_poll`)

1. DMA address (low, mid, high), `$198`, `$098`, sector count, `$088`.
2. Command bytes, each written with the next mode in **one long write** to `$FF8604`
   (data word then mode word), waiting for GPIP bit 5 low after each byte (the drive takes the
   byte; typical wait is short, a time-out protects against a dead drive).
3. Last byte with mode `$00A`: the drive executes, the DMA transfers. **Return to the program.**
4. Next frame: if GPIP bit 5 is high the command is still running (do nothing); if low, select
   `$8A`, read the status byte (0 = good), then `$080`.

Two command formats:

- **ICD READ(10)** (`$1F | id<<5`, then the 10-byte SCSI command): any LBA, needed above the
  first 1 GB, accepted by the UltraSatan. The code tries it first.
- **ACSI READ(6)** (`$08 | id<<5`, 21-bit LBA): first 1 GB only.

## Finding the file without reading the FAT

The program never parses the FAT. While a normal `Fread` runs, `hdv_rw` (`$476`, the BIOS
`Rwabs` vector) is hooked; the hook copies the stack of the first call whose buffer is the
program's buffer: drive, logical sector, count. Then:

- physical sector = `partition_start[dev]` (PUN_INFO, `$516`, long at +18 + 4·dev) +
  logical sector × (logical sector size / 512); the logical size comes from BIOS `Getbpb`;
- the ACSI id is in the `pun[dev]` byte (low 3 bits); bits 7 and 4 mark "not a hard disk /
  IDE" and are refused (the method is ACSI only);
- the file must be contiguous: the probe repeats the capture at 4 positions and requires the
  logical sector to advance exactly like the file offset.

Then a sector is read **with the new code** and compared with what `Fread` returned. Any failed
check sets a reason code (`g_dmastream.rawstate`) and the program uses plain `Fread` (adaptive
chunk size). So the fast path can never make the program worse than the standard one, only
fail to speed it up.

## Design of the streamer (`dmastream.h`)

- sound DMA in repeat mode on a ring buffer sized from the free RAM; position read back each
  frame gives the number of bytes played, hence the free part to refill;
- one ACSI command in flight at a time; in steady state 8 or 4 sectors (about 2–4 KB, one
  command every ~2 frames at 50 KB/s); prefill 32 sectors. Small commands are a design choice
  to keep the ring tidy; the drive LED therefore blinks often. Larger, less frequent commands are
  possible (parameter `dmastream_rawnext`) but have **not** been implemented or measured;
- when the free part wraps the end of the ring, a bounce buffer is read then copied;
- the data chunk of the WAV loops with no gap (the last partial sector, < 512 bytes, is skipped,
  < 6 ms);
- samples: 8-bit WAV is unsigned, the STE DMA wants signed. `wav2sgn.py` flips the bytes once
  on the PC so that the program does no conversion (about 3.5 % of the CPU saved on the demo).

## Rules the user of the library must respect

- supervisor mode (DMA, MFP, `$476`, `$516`);
- no GEMDOS/BIOS access to the **same disk** while a command is in flight: it corrupts the bus.
  Load everything first, or call `dmastream_pause()`; `dmastream_start` sets `flock`;
- the audio file must be contiguous (defragmented / copied to an empty volume);
- allocate your own buffers **before** `dmastream_start`: the ring takes the free RAM minus 20 KB;
- one STE sound DMA user at a time.

## Pitfalls met (also in `docs/06`)

| Symptom | Cause | Remedy |
|---|---|---|
| Counters in RAM overwritten, test results absurd | the ring grew until it covered the counters' address | cap the ring in the bench (`-DDMASTREAM_RING_MAX=…`) |
| TOS in Hatari does not see the FAT16 partition | TOS's GEMDOS FAT driver wants 1 KB clusters | `mkfs.fat -s 2` (`tools/mkacsi.py`) |
| Ring analysis says "unexplained" blocks | silence at the start of the file matched an earlier 64-byte window; `wr` moves during the dump | compare by segments, freeze the program before dumping |
| Fast path silently unused | file fragmented (`rawstate` −4) | copy the file to an empty partition |
| Music pitch +0.13 % | 25 000 Hz file played at the STE's 25 033 Hz | accepted; resample on the PC if it matters |

## Hatari bench

`tools/mkacsi.py disk.img --add MUSIC.SGN` builds an MBR + FAT16 (1 KB clusters) image;
`tools/acsi_bench.py` starts Hatari headless with `--acsi 0=disk.img`, `--fast-forward`
(emulated time stays valid), reads counters in RAM through the control socket, and prints VBLs
per frame. TOS 1.62 has no driver for such a disk: put a hard-disk driver in `AUTO` on a boot
floppy (HDDRIVER was used; it is not redistributable and is not in this repository). With
`--gemdos-drive` the program itself can live on a host directory seen as `P:`.
*State the limit every time*: the bench validates protocol and data, not the drive's speed.
`mkacsi.py` was run and its image checked (contiguous file); `acsi_bench.py` was derived from the
script that produced the results above, but **this generalised version was only checked for
syntax and `--help`**, not re-run end to end.

## Not done / open

- IDE drives (Falcon) and direct SCSI: not supported (fallback `Fread`).
- Other adapters/drivers than UltraSatan + HDDRIVER; the internal ACSI port of a Mega STE with a
  real ACSI drive; the READ(6) path on real hardware.
- Whether larger commands reduce the LED blinking and the CPU cost: not tried.
- Why mode `$0A` (bit 7 clear) is right for the last byte.

## Sources

- Atari Compendium, DMA chip description (mode register bits, sector count register, `flock`,
  address load order) — `dma.txt` as mirrored on discmaster.textfiles.com.
- Atari-Wiki, ACSI page: 6-byte command block layout and the command sequence outline (it gives
  no register addresses or bit values).
- Hatari documentation/source for the ACSI emulation (behaviour observed with 2.4.1).
- The method of reading a file by raw DMA commands was worked out by studying how a third-party
  audio player streams from disk (observed behaviour only; no code or bytes of it are in this
  repository, see `docs/08`).
