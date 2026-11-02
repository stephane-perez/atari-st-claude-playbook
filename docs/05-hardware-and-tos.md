# 05 — Hardware and TOS versions

## Machines / TOS correspondence used here

| Machine | TOS | Note |
|---|---|---|
| STF | 1.04 (Rainbow TOS) | 192 KB ROM at `$FC0000` |
| STF (old) | 1.00 | 192 KB ROM at `$FC0000`; less RAM used than 1.04 (see the memory budget) |
| STE | 1.62 | 256 KB ROM at `$E00000` |
| Mega STE | 2.06 | cache and 8/16 MHz |
| Falcon | 4.04 | 68030 processor, no classic overscan |

ROMs are for you to supply (copyright) and to place in `tos/`.

## Machine detection

- `_MCH` cookie: **absent before TOS 1.06**, which must be read as "ST". Always code the
  "no cookie jar" case. Values:

  | `_MCH` | Machine |
  |---|---|
  | `$00000000` | ST, Mega ST |
  | `$00010000` | STE |
  | `$00010010` | Mega STE |
  | `$00020000` | TT |
  | `$00030000` | Falcon |

  The Mega STE has the STE's high word: **compare the whole value**, not the high word only,
  when testing for STE-only hardware (extended joystick ports). JOYTEST tests `$00010000`
  and `$00030000` exactly; in Hatari 2.4.1 with EmuTOS the Mega STE is correctly excluded.
- `_longframe` (`$59E`) is non-zero on a 68010 or later (exception frames carry a
  format word).
- Read the cookie jar in supervisor mode (pointer at `$5A0`).
- To know whether you are on an STE: test for the presence of STE registers with a protected
  access (temporary bus-error handler) rather than a hard-coded address.

## Memory map and ROM

- TOS 1.x ROM at `$FC0000`, STE at `$E00000`: code reading the ROM as a randomness source at
  `$FC0000` causes a bus error on STE.
- Hardware registers: `$FF8000–$FFFFFF`. Write/read in supervisor mode.
- Register access in short-address mode: `$ffff8240.w`.

## Frequently used registers

| Address | Role |
|---|---|
| `$FF8240–$FF825E` | palette (STE: 4 bits per component, low bit shifted) |
| `$FF8201/03` | video base (high/mid), `$FF820D` low (STE) |
| `$FF820A` | sync (50/60 Hz), `$FF8260` resolution |
| `$FF8800/02` | PSG YM2149 |
| `$FF8A00–` | blitter (STE, Mega STE) |
| `$FF8E21` | Mega STE cache control |
| `$FF9200/02` | STE extended joystick ports (bus error on STF/Mega STE) |
| `$FFFA01` | MFP GPIP (bit 0: parallel port BUSY) |
| `$FFFC00/02` | keyboard ACIA (IKBD) |

## Memory and TOS

- TOS 1.04: supervisor stack left in the bss after `Supexec`; GEMDOS writes below the user
  stack: a program reusing this area may be overwritten on real TOS, whereas EmuTOS hides it.
- TOS 2.06 uses $5840 more bytes than 1.04 → any fixed address assumed free may be taken.
- Reserve your memory with `Malloc`/`Mshrink` rather than assuming addresses.

### Low memory taken by TOS (measured)

Basepage address of the first program started from the `AUTO` folder of a floppy, 512 KB,
Hatari 2.4.1, French TOS:

| TOS | Basepage |
|---|---|
| 1.04 (STF) | `$A956` |
| 1.62 (STE) | `$A99A` (68 bytes higher) |

A program that must fit below a fixed address (an old game that keeps its data at fixed
addresses, for instance) has **less room on an STE** than on an STF. Measure with a tiny probe
program on every TOS you support. The **basepage itself (256 bytes) stays in use by GEMDOS**
(DTA, process data): never let a stack or a copy reach it.

### GEMDOS buffers (BCB lists)

- GEMDOS keeps its sector buffers in two linked lists whose heads are at `$4B2` (FAT) and
  `$4B6` (directories and data). A buffer control block (BCB, 20 bytes): `+0` next, `+4`
  drive (-1 = invalid), `+6` type, `+8` record, `+10` dirty, `+12` DMD pointer, `+16` buffer
  pointer.
- **Hard-disk drivers add buffers in their own memory** (bigger sectors). Where they land
  depends on the driver's memory use: with HD Driver in "minimal memory" mode (58 KB) they
  were below a game's fixed area, with its normal setup (97 KB) they were inside it. A program
  that overwrites low memory and still wants to write a file must check both lists.
- A program that never returns to the desktop can **move** such buffers instead of refusing:
  copy the BCB if it lies in the area (update the previous link), point it to a new buffer
  taken with `Malloc` outside the area, mark it invalid (`+4` = -1) so GEMDOS rereads the
  sector; skip it if it is dirty. Done just before overwriting the area, interrupts off.

### Resident programs and vectors

- Residents and drivers hook vectors (traps, `etv_*`, `hdv_*`, `Kbdvbase` table). If their
  code lies in memory you overwrite, the first call crashes (Line-F, 11 bombs).
- Follow each vector's **XBRA** chain (`'XBRA'`, 4-byte id, previous vector, at -12/-8/-4
  before the code): a hook in your area can be unhooked; without XBRA it cannot — refuse to
  run, or refuse the feature that needs it (disk writes through a hooked `hdv_rw`…).
- `phystop` (`$42E`) = end of RAM; `Kbdvbase` (XBIOS 34) gives the IKBD vector table.

## GEMDOS memory budget (512 KB)

A program receives the largest free block; it gives back what it does not need with
`Mshrink(basepage, size)` (TEXT + DATA + BSS + $100 basepage + its stack), then asks for its
buffers with `Malloc`. On a 520 ST the margin is small, and it depends on **how the program is
started**. Measured with a game asking for about 420 KB in all (basepages as in the table
above, plus TOS 1.00):

| Start | Basepage | Margin |
|---|---|---|
| AUTO folder, TOS 1.00 | `$A204` | ≈ 20 KB |
| AUTO folder, TOS 1.04 | `$A956` | ≈ 18 KB |
| AUTO folder, TOS 1.62 | `$A99A` | ≈ 18 KB |
| GEM desktop (TOS 1.04) | `$12788` | ≈ 14 KB **short** |

- The desktop (AES, accessories, buffers) takes about 32 KB more than an AUTO start; the
  original game was already 400 bytes short from the desktop. Promise "512 KB from AUTO" only.
- Every byte added to the TEXT or the BSS comes out of the margin: re-test 512 KB at each
  version that makes the program bigger.
- To see the budget: `--trace gemdos` in Hatari lists `Pexec`, `Mshrink`, `Malloc` with their
  sizes and return addresses (`docs/04`).

### A launcher in AUTO (intro, menu) that starts the program

- Before `Pexec`, the launcher must `Mshrink` itself down to what it really keeps (resident
  code), otherwise the started program finds no memory. A real case: an intro kept the low
  memory up to `$10100` for one of its programs (IK+, loaded at a fixed address); another game
  then started at `$10104` and failed with "Can't allocate memory". Fix: keep that reserve only
  for the program that needs it.
- Set the current drive and path (`Dsetdrv`, `Dsetpath`) to the program's folder: many games
  open their data files by relative name.
- **Falcon**: started from AUTO, the video mode is the boot mode (`Getrez` = 2 on VGA or in an
  80-column mode); a game that demands a colour screen refuses to start ("Must have a Colour
  Display"). The launcher must switch to ST low resolution first (`Setscreen`, rez 0).

## MFP 68901 and interrupt latency

- All MFP sources reach the 68000 at level 6. While any MFP handler runs, the 68000 mask is
  6: **no other MFP interrupt is taken until the handler returns**, whatever the MFP
  priorities, unless the handler lowers the mask.
- Read the vector register `$FFFA17`: bit 3 = 0 is *automatic end of interrupt* (AEI, e.g.
  `$40`); bit 3 = 1 is software EOI (`$48`, TOS default), where the handler must clear its
  in-service bit. In AEI mode, a handler that does `move.w #$2500,sr` as its **first**
  instruction lets other MFP sources (Timer B…) interrupt it, while the VBL (level 4) stays
  masked.
- Real case: a game's keyboard handler (ACIA, ~300 cycles) delayed the Timer B raster
  interrupt, so the bottom palette change landed in the middle of the next line (a flickering
  black line, 12% of frames on STE). Lowering the mask to 5 at the start of the keyboard
  handler fixed it on every machine.
- Measure with `HBL` / `LineCycles` and `history` (docs/04) before changing anything.

## IKBD and keyboard ACIA

- The ACIA holds **one byte**. An IKBD packet (header `$F6`–`$FF` then 1–7 bytes; joystick
  interrogation answer = `$FD` + 2 bytes) arriving while interrupts are off overruns it: only
  part of the packet survives, and its missing bytes are then taken from the next keys.
- Reading the keyboard directly (interrupts off): after any long drawing, drain the ACIA
  until silence (~40–75 ms) before waiting for a key; skip packets by their length table;
  ignore releases (bit 7).
- TOS `joyvec` receives a **3-byte** buffer: header, joystick 0, joystick 1.
- The TOS only reports key presses. To know which keys are **held** (two players on one
  keyboard), replace `ikbdsys` (`Kbdvbase + 32`, TOS 1.0 to 4.04): read the ACIA yourself,
  keep a table of key states, skip the IKBD packets (`$F6`–`$FF` headers) and keep the
  joystick packets (`$FE`/`$FF` + 1 byte).
- In joystick mode the IKBD reports the **mouse on port 0 as a joystick**: menus that react to
  "player 2" move when the mouse moves. Read port 1 only (plus keys) in menus.
- Falcon TOS 4.04: `Crawio` makes GEMDOS check the current drive ("insert disk" alert without
  a floppy): read the keyboard through the BIOS instead.

## Blitter (STE, Mega STE)

- Shared mode: the blitter gives the bus back after 64 accesses (~256 cycles); an interrupt
  arriving during a burst waits.
- With raster interrupts: never start (or restart) the blitter when Timer B is 1 or 2 lines
  from its interrupt (`$FFFA21` ≤ 2), and pause it (bit 7 of `$FF8A3C` = 0) at the start of the
  raster handler. One line of margin was not enough when the keyboard handler ran in between.
- After a pause, bit 7 reads 0: test the end of a job on the line counter (`$FF8A38` = 0).
- Check a blitter rewrite byte for byte: a build option that runs the original routine, then
  the new one, and compares screen and buffers.

## Program that takes over the whole machine

- Read the program image into a `Malloc` block that may be anywhere, then copy it into place
  with a small routine moved out of the area being overwritten (copy the tail and modules
  last).
- Exception frames built by hand (`move.l #addr,-(a7) / move.w #$2300,-(a7) / rte`) need an
  extra format word on 68010+ (test `_longframe`), otherwise `rte` jumps anywhere (Falcon).
- Reset: if the program sets `resvalid`/`resvector` (`$426`/`$42A`), reset reruns it instead
  of rebooting; clear `$426` to get a normal reset.
- Free memory for resident code: prove it by measurement (docs/04), not only by
  disassembly.

## Falcon030 running ST software

- 16 MHz, caches and MMU off are enough for many ST games; leave the blitter and the
  Microwire alone (the DMA sound exists, the Microwire does not).
- VGA monitor: not 50 Hz, so anything paced by the VBL (music, game speed) runs too fast.
- Accelerator boards (CT60, 68060): out of scope; they can switch back to 68030 mode.

## Mega STE speed

The software does not need to touch `$FF8E21` to run at the speed chosen by the user (TOS and
the control panel set 8/16 MHz and cache); only timing-critical code (overscan) must force
8 MHz without cache.

## Alignment

Word or long-word access at an odd address: **address error** (bombs) on a 68000. `even` after
every variable-length byte table. On a 68030 (Falcon) it is tolerated, which hides the bug.

## Frequencies and frame rates

- 50 Hz (Europe, PAL); 60 Hz (US, NTSC): set according to the target machine's real TOS.
- Overscan: requires precise frequency/resolution switching; depends on the machine
  (STF/STE/Mega STE 8 MHz without cache). Not on Falcon.

## System calls

GEMDOS (`trap #1`), BIOS (`trap #13`) and XBIOS (`trap #14`) take their arguments on the
stack, function number last, and **destroy d0–d2 and a0–a2**: save what you need in them
before the call (or keep it in d3–d7/a3–a6).

## Joysticks

Everything below comes from JOYTEST (`stephane-perez/joystick-tester`); "real machine"
means checked by the author on a real STF/STE, the rest is Hatari only.

### ST ports 0 and 1 (IKBD)

- IKBD command `$14` = joystick event mode: a packet `$FE` (joystick 0) or `$FF` (joystick 1)
  is sent at every change. Send `$08` (relative mouse) on exit, otherwise the desktop has no
  mouse.
- Catch the packets with the TOS `joyvec` vector: offset 24 of the table returned by
  `Kbdvbase` (XBIOS 34). The handler is called with a0 pointing to a **3-byte buffer**: header
  (`$FE`/`$FF`), joystick 0, joystick 1. Read both joystick bytes, not only the one named by
  the header. Restore the original vector on exit.
- Joystick byte: bits 0–3 = up, down, left, right (1 = pressed), bit 7 = fire.

### Parallel-port adapters (4 players: Gauntlet II, Leatherneck…)

- Data lines D0–D7 = PSG register 15 (port B). **Bit 7 of PSG register 7 must be 0** (port B
  as input) before reading, interrupts masked; otherwise the real machine reads back the output
  latch, not the joysticks. Hatari ignores this bit (always reads the joysticks).
- BUSY = MFP GPIP bit 0 (`$FFFA01`); STROBE = PSG register 14 bit 5, set back to 1 before
  reading. All lines are active low.
- Wiring checked on a real machine (Gauntlet II / Leatherneck type adapter), identical to
  Hatari's: joystick 3 = D4–D7 (up, down, left, right) + BUSY (fire); joystick 4 = D0–D3 +
  STROBE.
- Save PSG registers 7 and 14 and put them back on exit.
- On some machines the BUSY line floats and gives false fire presses: a ~4.7 kΩ pull-up on
  BUSY fixes it.
- Showing the 8 raw lines on screen is the quickest way to recognise an unknown adapter's
  wiring.

### STE / Falcon extended ports A and B (Jaguar pad)

- Only on STE and Falcon (`_MCH` exactly `$00010000` or `$00030000`); bus error elsewhere.
- Write the select mask to `$FF9202`, read the buttons in `$FF9200` and the directions in
  `$FF9202`. Both ports are selected together: `$FFEE`, `$FFDD`, `$FFBB`, `$FF77` = rows 0 to
  3; write `$FFFF` to deselect. Everything is active low.
- Row 0: directions in `$FF9202` bits 8–11 (port A) / 12–15 (port B); in `$FF9200`, Pause =
  bit 0 and A = bit 1 (port A), bits 2 and 3 for port B. Rows 1, 2, 3: B, C, Option in bit 1
  (port A) / bit 3 (port B); keypad in `$FF9202` bits 8–15.
- **Real STE: a read of `$FF9202` hides the buttons in the next read of `$FF9200`** (it reads
  `$FFFF`); a new select clears it. So: select, read `$FF9200` at once, then read `$FF9202`
  (or select again). Found with a diagnostic screen showing three ways of reading each row
  (at once, after a wait of about 64 cycles, after a `$FF9202` read): on the real STE, the first
  two showed the five buttons, the third stayed at `$FFFF`. Hatari does not reproduce it.
