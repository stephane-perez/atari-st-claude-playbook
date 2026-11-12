# 07 — Case studies: what was done, what worked

Summaries **without code or original bytes**. Each case gives the technique used and the
lesson. The projects mentioned are the repository author's; the original programs remain the
property of their authors and publishers.

## Puzzle game (ChuChu Rocket) — complete disassembly

- Goal: understand and document an entire game.
- Techniques: PRG header (flags `6`: fastload + TT-RAM), recursive disassembly with **96.4%**
  code coverage, source where every address is a label, identical reassembly, naming through a
  rename file, resource extraction with PNG round trip.
- Lessons: the "byte for byte" criterion; the `METHODOLOGY`, `CODE_MAP`, `GAME_LOGIC` documents
  help resume work in another session.

## Fighting game (IK+ Reforged)

- Goal: fixes and new features for a 1988 fighting game: STE / Mega STE / Falcon support, a
  third simultaneous player, STE extras (DMA sound, blitter drawing, Jaguar pads), a new
  loader with an intro page, Esc back to that page during the game.
- Techniques:
  - memory image of the game extracted from the user's own program file; every patch checks
    the input MD5 and the original bytes; outputs checked by MD5 (`make check`);
  - hooks (`jsr`/`jmp` + `nop`) to small modules in proven free memory (dead boot code, a
    skipped disk check, an area filled with a pattern and read back after long games);
  - STE module installed by the loader at run time, only on STE / Mega STE with 1 MB;
  - blitter routines checked byte for byte against the originals (build option);
  - Hatari: command fifo, saved states, fast forward, conditional breakpoints with `HBL` /
    `LineCycles` and `history`.
- Lessons:
  - the STE crash came from the game reading the TOS 1.x ROM at `$FC0000` as randomness;
  - a flickering black line on STE was the keyboard ACIA handler delaying the raster
    interrupt (12% of frames); found by a histogram of palette-write times and `history`,
    after two diagnostic builds (no blitter, no DMA sound) had cleared the obvious suspects;
    fixed by lowering the mask to 5 in the keyboard handler, plus a wider blitter guard;
  - a bug reported on the machine that does not reproduce in Hatari: fix the plausible
    cause, say clearly it was not reproduced, and ask for the exact steps;
  - Falcon: 16 MHz with caches and MMU off was enough; a hand-built `rte` frame needed the
    68030 format word;
  - a "where we are" section in `CLAUDE.md` (published version, open items, session limits)
    lets a new session resume without the history.

## Racing game (Super Sprint) — 4th human player by patching a compiled program

- Goal: make the fourth car, always driven by the computer, playable by a human; install on a
  hard disk; new controls (parallel-port joystick adapter, STE/Falcon joypads).
- Techniques (`docs/03`, section 10b): study listing only, no full reassembly; patch script
  checking the MD5 and the original bytes; new code appended to the TEXT with a `bra.w` entry
  table; BSS enlarged by 4 KB; hooks through the compiled program's jump table (`jsr n(a5)`);
  title screen redrawn by the user and stored as a pixel difference; version number from the
  git tag drawn on the title screen; reproducible output checked by MD5.
- Memory: about 18 KB to spare on a 520 ST started from AUTO, short of memory from the
  desktop; an intro in AUTO that kept low memory for another program made the game fail
  ("Can't allocate memory") until it released it (`docs/05`).
- Lessons: the computer-only car was never handled like the others (upgrades not reset,
  score never blinking, never updated by a `(frame mod 6)/2` round-robin): every function
  touched had to be re-checked for it. The original RESET routine froze the real machine but
  not Hatari. Validated on STF, STE, Mega STE, Falcon030 (RGB and VGA) and Falcon CT60;
  512 KB verified in Hatari only.

## Arcade game (Bubble Bobble) — up to 8 players

- Techniques: analysis of the input routines, modifications added behind `ifd`, keeping the
  no-option build identical (87 modifications, the no-option build still byte-identical).
- From 4 to 8 players without rewriting the game: the game only knows players 1 and 2, so
  the extra players' state is **swapped** into players 1/2's records around each call of the
  per-player routines (pairs 1↔3/2↔4, 1↔5/2↔6…), once per frame to keep the cost down.
- Inputs: STE extended ports (Jaguar pads), parallel-port adapter, two players on the
  keyboard (own `ikbdsys`), computer players.
- **Two memory modes** from one executable: a loader detects the RAM. In 512 KB the game is
  copied below its fixed data area as the original was, and only the code up to a marker
  label is copied; features placed after the marker (start menu, title cycle, computer-player
  extras…) exist from 1 MB only, where the game runs in a block taken with `Malloc`.
- Every byte counted in 512 KB: new 1 MB features are reached through **one shared hook**
  (`bsr shared` = 4 bytes in the 512 KB part); the 1 MB dispatcher recognises the caller by
  its **return address** on the stack and jumps to the right routine.
- Robustness work driven by real machines: residents hooking vectors inside the game's area
  (XBRA unhooking), hard-disk driver buffers in that area (BCB relocation), STE 512 KB with
  TOS 1.62 (68 bytes less room than TOS 1.04).
- Lessons:
  - the STE's extended joystick ports (`$FF9200/02`) cause a bus error on STF and Mega STE;
    test the machine first;
  - "it fits in 512 KB" must be checked under **every TOS** concerned;
  - Hatari with snapshots + fast forward + command FIFO turns a 5-minute manual check into an
    unattended run with screenshots (docs/04);
  - one ticket per reported defect, a branch per fix, the user decides what goes into which
    numbered version; a state section in `CLAUDE.md` lets a new session resume (docs/09).

## Joystick tester (JOYTEST) — original program, public

- Goal: show live every joystick an ST can read (ports 0/1, 4-player parallel adapters, STE/
  Falcon extended ports with a Jaguar pad), first to debug IK+ Reforged on real machines. Public
  repository: `stephane-perez/joystick-tester` (MIT).
- Techniques: IKBD event mode + `joyvec`; PSG/MFP reads of the parallel port; `_MCH` test
  before touching `$FF9200/02`; one source, two languages (`-DENGLISH`); MD5 of both programs
  checked by `make check` and by a GitHub Actions workflow that also publishes a release for
  every `v*` tag.
- Method: **temporary diagnostic display**. When Hatari and the real machine disagreed, the
  program showed the raw values (8 parallel lines; for the Jaguar pad, every select row read
  three different ways). The author ran it on the machine and reported what the screen showed;
  the conclusion went into the notes, then the diagnostic display was removed.
- Findings (hardware details in `docs/05`): bit 7 of PSG register 7 (the cause of a dead
  third joystick in a game); the 3-byte `joyvec` buffer; on a real STE, reading `$FF9202`
  hides the buttons in the next `$FF9200` read.
- Lessons: in both cases the faulty code worked in Hatari; only the real machine showed the
  problem. Raw values on screen beat guessing.

## Action game on a track-loader floppy (1992) — structure and assets

- Goal: understand a commercial game delivered as a Pasti (`.STX`) image and extract its
  assets for study (kept in a private repository, `docs/08`).
- Techniques: `stx.py` (geometry, Copylock key sector described, not circumvented), boot
  sector and second stage read by hand, file table found in a sector filled at run time,
  Hatari `--trace fdc` to map the loads (preload with 1 MB, on demand with 512 KB);
  Pack-Ice 2.3x depacker checked against the game's own routine in Unicorn; pictures
  bit-transposed by the game, undone and checked pixel by pixel against a Hatari screenshot;
  levels rebuilt from map + tile set and compared with an in-game screenshot; music players
  run in Unicorn, wrapped as SNDH and recorded in Hatari with a frame-by-frame YM check;
  recursive disassembly with a pointer scan (34 % of the program classified as code).
- Lessons: read the formats in the code that uses them (load routine, renderer) rather than
  guessing from the bytes; check colours against the emulator (two palette encodings in one
  game); a home-made emulation (Unicorn) is only trusted once it matches Hatari; re-test a
  tool after every change, even a "small" one (a comparison rewrite fell from 100 % to 0.2 %
  before the alignment was fixed).

## STE tech demo with music streamed from the hard disk — non blocking ACSI DMA

- Goal: a 50 fps scrolling demo with sprites and a multi-minute stereo sample played from the
  hard disk, without losing frames when the disk is accessed. Real machine: Mega STE, UltraSatan,
  HDDRIVER.
- Techniques: sound DMA ring buffer; hand-built ICD READ(10) / ACSI READ(6) commands on the
  ACSI DMA chip; file located through a `hdv_rw` hook and PUN_INFO instead of a FAT parser;
  probe with automatic fallback to `Fread`; Hatari bench with an emulated ACSI disk and
  counters read through the control socket (`docs/11`).
- Lessons: a version with `Fread` of adaptive size did not remove the lost frames; only the real machine showed the problem and later the fix (the user watched a CPU
  meter, colour bars by raster line). Hatari validated the protocol and the data, never the
  timing. Fragmentation of the file silently disabled the fast path until the disk was
  defragmented, hence the reason codes. Packaging the code as a reusable library
  (`examples/acsi-stream`) was requested after the result was confirmed.

## Same action game — hard-disk adaptation for any driver (2026)

- Goal: the published hard-disk adaptation of the game (2011, its own loader system) crashed
  with the user's driver on real STE and Mega STE; make it work with any driver.
- Techniques: the old loader system read and its LZ format re-implemented; a 186-byte
  "preload everything in RAM" patch (4 MB machines); then a new launcher written in vasm on
  the author's newer library (original driver in low RAM, real TOS, RAM swaps): game
  sector-read routine redirected to the library, exit/state-save keys hooked at the end of
  the game's IKBD interrupt, YM muted during loads, reset made a cold boot. Numbered
  builds 0.0.1, 0.0.2.
- Results: verified on a real STE 4 MB with HDDriver 12.53 (game, loads, save, restore, exit,
  reset); Hatari STE/Mega STE 1-4 MB.
- Lessons: the crash and the reset bug never showed in Hatari; a driver's behaviour can only
  be judged on the machine. Details and the WHDLoad-like design: `docs/12`.
