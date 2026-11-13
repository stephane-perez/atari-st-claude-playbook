# 12 — Floppy games from hard disk: gamex, HAGA, HAG2 and a WHDLoad-like design

How floppy-only games are made to run from a hard disk on the ST, what was learnt by taking
apart Peter Putnik's systems (gamex, HAGA, HAG2), and what a WHDLoad-like system for the
Atari ST should take from them. Later project: write such a system; this page is its input.

Sources: Peter Putnik's pages (`https://atari.8bitchip.info/doinadapts.html`,
`https://atari.8bitchip.info/fromhd2.php`), seven of his adaptations supplied by the user
(gamex 2011, HAGA 2012-2023, HAG2 2021-2022), and one adaptation carried out here (a 1992
action game with its own floppy loader, ported from gamex to HAGA; see `docs/07`).

**Nothing of Peter's files is in this repository** (`docs/08`): no `HAGA`, `HAG2`, `.FIC`, no
launcher, no disassembly. This page gives the architecture, the calling conventions met and
the results. His files are for private use; ask him before distributing anything derived.
The hard-disk driver used for the tests (HDDriver 12.53) is the user's personal copy, not
redistributable, not in the repository.

## Status of this page

| Point | State |
|---|---|
| Game categories, history of the systems | Peter's pages (quoted, not checked) |
| gamex internals (files, LZ format, services, memory) | read in the code + Hatari 2.4.1 |
| gamex crash with HDDriver 12.53 on STE and Mega STE | reported by the user on real machines; **not reproduced in Hatari**; cause = hypothesis |
| gamex "RAM mode" workaround | Hatari (STE 1.62, Mega STE 2.06, 1/2/4 MB) + **real STE 4 MB, HDDriver 12.53** |
| HAGA calling conventions (12-entry version) | read in a launcher + a launcher written here, **real STE 4 MB, HDDriver 12.53**: game, loads, exit, state save and restore, reset |
| HAG2 structure and launcher sequence | read in the code only (not run here) |
| WHDLoad-like design (last section) | proposal, nothing implemented |

## 1. The problem

Peter's figures (about 1,700 games examined):

| Category | Share | Disk access | What the adaptation must do |
|---|---|---|---|
| TOS games, started from AUTO | ~50 % | GEMDOS (`Fopen`/`Fread`) | keep 25-40 KB of TOS work area; fix paths (`A:\…`), disk-swap detection, TOS-version problems |
| TOS games using GEM/AES | ~15 % | GEMDOS | keep 80-100 KB of TOS (whole TOS) |
| DFC games (direct floppy controller) | ~1/3 | own WD1772 code, or XBIOS 8 | find the loader, replace it by hard-disk reads; remove the protection; the game uses all RAM, TOS included |

Common needs, whatever the category:

- no floppy drive needed any more (many users have none, or a Gotek);
- **any hard-disk driver** (HDDriver, ICD, AHDI, PP…): the hardest point in practice;
- every ST, every TOS (1.00 to 4.04), 1 MB minimum (the extra RAM holds the system and a copy
  of the machine state);
- extras: **exit to the desktop** and **state save** at any time, by key (`*` and `/` of the
  numeric pad in all of Peter's adaptations), trainer options (lives, energy).

Data are kept as:

- a **flat sector image** of the floppy: `.ST` (sectors in order, 720 / 800 KB, up to 4 MB in
  FAT12, more in FAT16), made from a `.STX` with `tools/stx.py --dump` once the protection is
  dealt with;
- or a **game-specific sector file** (only the logical sectors the loader reads, in its
  order: e.g. 1212 sectors for the action game of `docs/07`);
- or plain **files** in a folder (oldest adaptations).

## 2. gamex (2009-2011): TOS in high RAM, driver re-installed

Files of a gamex adaptation: `START.TOS` (launcher), `D15R_xx.FIC` (common library;
`5H`/`5F` variants, looked up in the game folder then in `C:\GAMEX\`), the data (sector file
or folder), `.PCH` (game corrections), `GXUTnnn.PRG` (utility).

- `START.TOS` is a 230-byte self-extracting stub followed by an LZ stream. The `.FIC` uses the
  same LZ with a 32-byte header. Format: control byte `c`; `0` = end; `1..127` = `c` literal
  bytes; bit 7 set: `n = c & $3f`, bit 6 clear = copy `n+3` bytes from `out - byte`, bit 6
  set = copy `n+4` bytes from `out - word`. (A packer/depacker for this format was written for
  the study; it is generic code, not Peter's.)
- The launcher **cuts TOS down to 512 KB** (`phystop` forced to `$80000`, memory list adjusted,
  signature written at `$80000`), depacks the library at `$c0100`.
- The library holds a jump table of services (file read/write, init…) and an **embedded
  mini-system**: its own GEMDOS (`trap #1`), BIOS (`trap #13`) and VBL (keeps `_hz_200`
  going). The hard-disk driver is **re-installed** by gamex (boot code of the root sector
  called again) under a hooked `Malloc` that always returns a fixed address above 512 KB.
- In the game, the game's disk routine is redirected to a small stub in low RAM that calls the
  file-read service with (offset, length, destination, file name). The service masks **all**
  MFP interrupts, swaps `$8`-`$7ff` (vectors + TOS system variables) back, and does
  `Fopen`/`Fseek`/`Fread`/`Fclose` through the mini-GEMDOS, which calls the driver through
  `hdv_rw`. **The `Fread` result is not checked**: the game is told "OK" whatever happens.

Driver compatibility. Peter: adaptations made before January 2012 work only with his drivers,
AHDI and the HDDriver of that time ("most of drivers was not really good for" running in high
RAM). Observed:

- User, real STE and Mega STE, HDDriver 12.53: the gamex adaptation crashes after the title
  screen (HDDriver boot screen again, then 4 bombs); with Peter's driver it works.
- Hatari 2.4.1 with the same driver and disk: **no crash** (all reads succeed).
- Measured in Hatari, at library init (TOS alive, `phystop` already forced to `$80000`): an
  HDDriver 12.53 `Fread` **succeeds into `$40000` and returns `-2` into `$90000` or
  `$200000`**: the driver refuses a buffer above `phystop`.
- Hypothesis (not proven): on the real machine a read fails along such a path; the failure is
  not checked, the game runs on wrong data → illegal instruction.

Workaround verified on the real machine ("RAM mode", 186 bytes in a free area of the library,
original bytes checked before patching): on a 4 MB machine (MMU memory configuration
`$FFFF8001 & $0f = $0a`, since `phystop` is already false), read the **whole** sector file at
library init in 16 KB chunks through a low bounce buffer (`$40000`), copy it to `$200000`,
and serve every later read from RAM; enabled only if the full read succeeded. Result: no
driver call during the game; real STE 4 MB + HDDriver 12.53 OK. Limit: 4 MB only (no free
620 KB block in 2 MB for that game); state saves still go to disk.

## 3. HAGA (2012-): original driver in low RAM, real TOS, RAM swaps

Peter's description: "my version of the WHDLoad concept for the Atari ST - using original hard
disk driver in low RAM, so swapping RAM areas when disk access is needed. To lower count of
those swaps read ahead cache is used", with the common functions in a DLL-like file `HAGA`
"placed at top of ST RAM". README of an adaptation: "should work with any decent hard disk
driver, ICD Pro for instance … Min RAM is 1MB".

Layout of an adaptation: `RUNME.TOS` (game-specific launcher, same self-extracting stub as
gamex), `HAGA` (or `C:\GAMEX\HAGA`), `FILES\` (data: sector file or folder, optional
`D15H5.FIC`), optional `.PCH`/`.BMP` (picture, cover), `.HST` files (variants of a game file
per TOS version: the first letter of the name changes, e.g. `F…` for TOS ≥ 2, `L…` for 1.x).

### Library ABI

- Entry `n` is at `HAGA + (word at HAGA + 2n)`. Two generations met: 12 entries (11,242 bytes,
  used in a platform game with its own loader, and in the adaptation done here) and 16 entries
  (a 2023 adaptation of a vertical platform game; also HAG2). **The numbering differs between
  generations**: always take the call sequence from a launcher that ships with the same
  `HAGA` file.
- Entries of the 12-entry version, as used by its launchers (verified by running):

| Entry | Use | Conventions seen |
|---|---|---|
| 0 | detection | `a0` = 8-byte parameter block (copied from an existing launcher, meaning partly unknown); returns `a0` = info block (`+3` CPU, `+7` ST RAM in 512 KB units); the launcher then writes two longs at `+$32` / `+$36` of it (copied, meaning unknown) |
| 1 | detection screen (machine, TOS, RAM, options) | launcher reads the option keys afterwards |
| 3 | Mega STE settings (speed, cache) | |
| 11 | load `D15H5.FIC` (GEMDOS in RAM) if present | no-op when absent |
| 2 | machine set-up before the game | |
| 4 | file service | `a0` → block of 7 longs: `+0` destination, `+4` byte offset, `+8` length, `+$c` flag word (0 = read, `'Wr'` = write, `'cR'`), `+$e` file name (e.g. the sector file); runs with interrupts masked |
| 6 | exit to desktop / state save | caller pushes `d0-d7/a0-a6`; `d0` = `$37` exit, `0` save; `a0` = work area ≥ `$62` bytes with the caller's `SR` at `+$50`; `a2` = resume address. HAGA pops the registers, restores `SR`, jumps to `a2` |

- The launcher copies `HAGA` to the top of ST RAM (`$f8000` with 1 MB, `$1f8000` with 2 MB,
  `$3f8000` with 4 MB), keeps a **snapshot of low RAM** (from `$8` up to the launcher) in a save
  area and a few HAGA variables, then `Dsetpath("FILES")`, entries 11, data load, entry 2,
  flushes the ACIA, and takes the machine over (screen, `SR`, stacks, MFP, palette) to start
  the game.
- File service: unlike gamex, HAGA has **no own GEMDOS and no `Malloc` hook**. Around each call
  it puts the original low RAM back (TOS work area + the driver where the driver installed
  itself), calls the **real TOS GEMDOS** (so the real driver, wherever it is), then swaps the
  game's low RAM back in. A read whose destination is in the swapped area goes to HAGA's copy
  (seen in Hatari: a table loaded at `$113e8`). Hatari `--trace gemdos` shows these
  `Fopen`/`Fseek`/`Fread` calls coming from the HAGA copy at the top of RAM.
- State save: writes `GSnn.TOS`, a self-contained program that restores the game when started
  from the desktop (525,108 bytes in Hatari for a 4 MB STE: the low 512 KB plus a header).

### Porting a DFC game to HAGA (done here, verified on a real STE 4 MB)

1. Find the game's sector-read routine (parameters: first sector, count, destination). It
   becomes a jump to a stub in a free low area (`$200` here) that builds the 7-long block
   (`sector × 512`, `count × 512`, file name) and calls entry 4, then returns "OK" as the
   original routine did.
2. Apply the game patches of the earlier adaptation (protection, RAM probe, stack addresses,
   trainer options) from your own launcher, after checking the original bytes.
3. Exit/save keys: hook the **end of the game's IKBD interrupt** (the received byte is in a
   register there). Compare **break codes** (`$e6` = `*` released, `$e5` = `/` released) so
   the call happens once, then call entry 6 as above, resuming at the hook's `rte`.
4. Music: during entry 4 the interrupts are masked and the TOS low RAM is in place, so the game's
   music player cannot run; the YM keeps its last note ("stuck note"). Save and zero the
   volumes (YM registers 8-10) around the call, restore them after.
5. Reset: clear `memvalid` (`$420`), `memval2` (`$43a`), `memval3` (`$51a`) and `resvalid`
   (`$426`) just before jumping into the game. Without it, a reset during the game gave
   2 bombs on the real STE (the game's stack overwrites system variables TOS believes
   valid); with it, a reset is a cold boot. Hatari never showed the problem. (The user notes
   the same crash on reset in one of Peter's HAGA adaptations.)
6. HDDriver: with another HAGA game the user had to limit HDDriver's memory (Esc at boot) to
   avoid display faults: the driver lives in low RAM that the game also wants.

Results: Hatari 2.4.1 with HDDriver 12.53 on an ACSI image (STE 1.62 1 and 4 MB, Mega STE
2.06 2 and 4 MB): game runs, loads go through the real driver, no exception. **Real STE 4 MB +
HDDriver 12.53 (user)**: game, loads, mute, `/` save, restore by starting `GS00.TOS`, `*` exit,
reset → all OK. Not tried on a real machine: 1 MB, Mega STE, Falcon/TT, other drivers.

## 4. HAGE and HAG2: TOS in RAM over a floppy image

- **HAGE** (2018): the whole TOS (GEMDOS + AES) disassembled from 1.04 and run from RAM, for GEM
  games; files served from an `.ST` floppy image.
- **HAG2** (2021-): only the GEMDOS of TOS 1.04 in RAM, for AUTO-folder games, files served from
  `.ST` images. Peter: adapting with HAGE/HAG2 is "easier and faster in most cases".

Read in two HAG2 adaptations (an RPG and a strategy game, both using GEMDOS for their files):

- `RUNME.TOS` is **generic** (3.5 KB, identical code in both games, only names differ); `HAG2`
  (12,394 bytes) is the same file in both; `FILES\B.ST` / `FILES\D.ST` are real floppy images
  (737,280 / 819,200 bytes); `FILES\T14GG.FIC` (~64 KB) is the GEMDOS in RAM ("GOS").
- Same 16-entry table as the 2023 HAGA. Launcher sequence: 0, 1, 3 (detection, screen, Mega
  STE), `Dsetpath("FILES")`, **13** (mount the image: name in `a4`, image size in `a0`; the
  size is compared with the free RAM, apparently to keep the image in RAM when it fits), 2,
  flush ACIA, **10** ("Starting GOS": opens `T14GG.FIC` from `FILES\` then `C:\GAMEX\`, reads
  65,300 bytes, starts the game on it), 6 for the `*` / `/` keys. Entry 4 (raw read) is not
  called.
- So for a GEMDOS game the adaptation is mostly: make the image, write five names in the
  generic launcher. Game code is patched only for the TOS-version problems and the keys (the
  TOS in RAM can catch the keys itself when the game reads the keyboard through TOS).

Choice by game type:

| Game | Best fit | Why |
|---|---|---|
| GEMDOS game from AUTO | HAG2-like (GEMDOS in RAM + `.ST` image) | almost no game patch, TOS-version independent |
| GEM/AES game | HAGE-like (whole TOS in RAM) | needs AES |
| DFC game (own loader) | HAGA entry 4 on a sector file | the game never calls GEMDOS; a GEMDOS in RAM would cost ~64 KB for nothing |

## 5. Testing such systems in Hatari

- The GEMDOS hard-disk emulation of Hatari is not enough: gamex refuses it, and it bypasses
  the driver anyway. Use an **ACSI image with a real driver**: boot from the image (its root
  sector holds the driver's boot code), put a small `AUTO\*.PRG` that does `Mshrink`, then
  `Dsetpath` + `Pexec` of the `.TOS` launcher (AUTO runs only `.PRG`). `mtools` with
  `-i image@@offset` writes into the partition.
- `--trace gemdos` shows each `Fopen`/`Fseek`/`Fread` with its PC: proves the reads come from the
  library and go through the real TOS.
- `--trace psg_write` shows the YM writes (mute around loads).
- Warm reset during the game: the Hatari control socket (`hatari_run.py`, shortcut
  `warmreset`). Hatari did not reproduce the real-machine reset crash: the reset fix was
  validated on the machine only.
- One Hatari at a time on a given ACSI image (lock).
- Driver memory, read failures and timings differ on the real machine: the gamex crash was
  never reproduced in Hatari. **A loader is only "working" after a real-machine trial**, with
  the driver the user really has.

## 6. Towards a WHDLoad for the Atari ST (proposal)

WHDLoad on the Amiga (from its public documentation; to be re-read before designing): a
generic loader plus, per game, a small **slave** (header with version, flags, base memory
size, exit key, the game's loader code and patch lists), services offered by the loader
(`resload_DiskLoad`, `resload_LoadFile`, `resload_SaveFile`, `resload_Patch`, quit…), data
preloaded in RAM when possible so the OS is not needed during the game, and an OS swap
otherwise. HAGA is the same idea, with the library at the top of ST RAM and the per-game code
inside each launcher.

### Principles drawn from the work above

1. **Keep the original driver and the real TOS**; do not re-install the driver elsewhere and
   do not fake `phystop` while it runs (gamex). This is what makes HAGA driver-independent.
2. **Preload when the RAM allows** (whole image or sector file in RAM at start, as the gamex
   RAM mode): no driver call during the game, music keeps playing, no timing risk. Fall back
   to a HAGA-style swap per access (with read-ahead) on 1 MB machines.
3. **Check every read** and stop visibly on failure (message + error code), never hand bad
   data to the game.
4. During a swap: mask interrupts, mute the YM (registers 8-10), restore exactly what was
   saved (vectors, MFP registers, system variables, video base, palette), flush the ACIA.
5. Clear `memvalid`/`memval2`/`memval3`/`resvalid` before starting the game (reset = cold boot).
6. Exit and save keys hooked at the game's keyboard interrupt (break codes); if the game uses
   TOS for the keyboard, catch them in the TOS layer instead.
7. **Versioned ABI**: magic + version + entry count at the head of the library, documented
   entry conventions, never renumber entries (the HAGA generations differ: avoid that).
8. Per-game part = a small **slave** assembled with vasm: header (name, version number shown
   on screen, rule 8 of `CLAUDE.md`), RAM needs, data file names, a **patch list with the original
   bytes checked** before each change, the hooks (read routine, keyboard, exit), the start
   address. A generic launcher reads it (as HAG2's generic `RUNME`).
9. Services: raw read from a sector image (offset, length, destination, disk number), file
   read/write in the game folder, state save/restore, exit, machine info (`_MCH` cookie,
   RAM, TOS version), patch helpers.
10. GEMDOS games: a GEMDOS layer in RAM over an `.ST` image. Peter's comes from a disassembled
    TOS 1.04 (Atari copyright, not reusable). Candidate: the GEMDOS of **EmuTOS** (GPL), to
    evaluate for game compatibility (hypothesis: older games may rely on TOS 1.04 details).
11. Memory budget to measure per machine: library + save area for the low RAM + read-ahead
    buffer + (optional) image cache, against the game's own needs; test 1 MB first.
12. Test matrix: Hatari STF 1.04 / STE 1.62 / Mega STE 2.06 / Falcon 4.04, 1-4 MB, with the
    real driver on an ACSI image; then real machines with several drivers (HDDriver, ICD,
    AHDI, PP), IDE/SCSI/SD adapters, and with the driver's memory as the user normally sets it.

### Open questions

- TT and Falcon: caches, TT-RAM, the driver's own use of TT-RAM; not studied.
- Which driver behaviours matter (buffer above `phystop`, use of interrupts, DMA vs CPU on
  IDE): to measure driver by driver, on real machines.
- Read-ahead size vs swap cost: to measure (each swap copies the low RAM in both directions).
- Legal: Peter's files and ABI are his work; a new system must be an independent
  implementation, and games' data still come from the user's own copies (`docs/08`).
