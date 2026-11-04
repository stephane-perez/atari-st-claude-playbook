# 03 — Reverse engineering an Atari binary: the method

Method proven on several programs (puzzle game, arcade game, boot loader, compilation intros,
copy utility). Guiding principle: **only modify what has first been rebuilt identically.**

> For legal reasons (see `docs/08`), the repository contains no disassembly of commercial
> programs. The method can be replayed on your own files.

## Overview

1. Inspect the header and detect a packer.
2. Unpack.
3. Disassemble recursively (not linearly).
4. Emit a source where every address is a label.
5. Reassemble: the result must be **byte-for-byte identical** (`-no-opt`).
6. Shift test: prove the source does not depend on addresses.
7. Compare execution in Hatari (original / rebuilt).
8. Extract resources (images, sounds) with a round trip.
9. Name and comment through a rename file, re-checking identity at every pass.
10. Externalise settings; modifications behind `ifd`.
11. Measure (Hatari breakpoints), prove equivalence of optimisations.

## 1. Inspect

```sh
python3 tools/prg_info.py FILE
```

Check: magic word `$601A`? text/data/bss/symbol sizes, flags, number of relocations, packer
signatures (`ICE!`, `ATM5`…). Real cases:

- a file presented as a "floppy image" was a packed PRG;
- a file `TOS104.IMG` was a RAM-loaded TOS (256-byte relocator), not a ROM;
- a "raw memory image" (no `$601A` header) needs heuristics to tell addresses from constants,
  for lack of a relocation table.

## 2. Unpack

- **Pack-Ice**: the stub's depacker is short; transcribe it faithfully into Python.
  `tools/unice.py` handles 2.3x (`Ice!`) and 2.40 (`ICE!`). They differ (bit buffer of a
  long word vs a byte, distance tables, picture pass), and a lower-case header does not prove
  the version: the 47 `Ice!` files of one game all fail when decoded as 2.40 (some
  depackers, such as unice68 according to its source, accept both headers with the 2.40
  algorithm). Verification:
  - 2.3x: byte for byte against the game's own depacker run in Unicorn (47 files);
  - both: `tools/unice_fuzz.py`, differential fuzzing against a 68000 routine run in
    Unicorn (the game's for 2.3x, the published PACK-ICE 2.40 source re-typed and assembled
    with vasm for 2.40), with VALID random streams covering every path: several thousand
    cases, 0 difference; 6 deliberate mutations detected. No real `ICE!` file was available:
    confirm on one when you have it.
  - Curiosity of the published 2.40 routine: `move.w #$0F9F,d7` overwrites the bit buffer
    just before reading the picture-pass block count, so that count always starts with the
    bits `001111` (at least 15,361 blocks, 122 KB). `unice.py` reproduces it as is.
  A game may transform the data again after depacking (one kept its pictures
  bit-transposed): look at the result (round trip to PNG) before concluding.
- **Atomik (ATM5)**: rather than transcribing, emulate the stub with Unicorn and hook the
  final copy, then take the unpacked image.
- Always **verify**: expected size (given in the packed header), and that the result looks like
  a PRG or coherent code (disassembly without noise).
- Keep the entry point: after unpacking, the decompressed code often starts with a jump or a
  routine that must be found.
- **UPX**: it knows the `atari/tos` format. `upx -d` unpacks; `upx --best PROG.PRG` packs (an
  intro of 196 KB went down to 76 KB, about 39 %). Packing saves floppy space, not memory: the
  program is unpacked in place, at its full size. Pack only once the user has agreed (on one
  project the author chose to leave the game uncompressed and keep UPX for the intro).

## 2b. Floppies without files (track loaders)

Many games have no usable directory: an executable boot sector (word checksum `$1234`)
loads a second stage that drives the WD1772 directly and reads files from its own table.
Method that worked (`.STX` image of a 1992 game):

1. `tools/stx.py IMAGE.stx` : geometry, sector order, **protection marks** (a sector with a
   CRC error and a timing record = key sector, for example Copylock ST). Describe them,
   never circumvent them (`docs/08`).
2. `tools/stx.py IMAGE.stx --dump flat.st`, then disassemble the boot sector from `$1E`
   (bra `$601E`): it says which logical sectors it reads and in which order (cylinder,
   side, sector), which is also the addressing of the file table.
3. Find the file table (often a sector read by the second stage; it may be **filled at run
   time**: empty in the loader's source, present elsewhere on the disk).
4. **Confirm with Hatari**, which reads `.STX` directly: `--extra "--trace fdc"`, keep the
   `type II read sector` lines (track, side, sector, DMA address, pc) and map them to the
   table. This shows the real loading order and the memory configuration effects (one game
   preloaded all its files with 1 MB, loaded them on demand with 512 KB).
5. Entropy per track gives a quick map: packed data near 7.7 bits/byte, formatted but unused
   tracks are a repeated pattern (`$6DB6`, `$E5`).

## 3. Recursive disassembly

`tools/m68k_recdis.py IMAGE LOAD_ADDR OUT.lst [--entry A] [--labels FILE] [--pointer-scan]`
does it for a raw memory image (an unpacked program, a loader, an SNDH): labels for every
target, a names file (`ADDRESS NAME comment`) applied at each run, vectors found from
`move.l #x,$70.w` and `lea x,aN` + `move.l aN,$70(a0)` (with `a0` known to be 0), `jsr (aN)`
after `lea`. `--pointer-scan` tries the long words of the data areas that point into the
image as code (function tables, object handlers), keeping them only if they decode as 68000
code up to `rts/rte/bra/jmp` and do not start with `ori` (`$00xx`, almost always data). On a
70 KB compiled-like game program: 14 % of the bytes as code by flow alone, 34 % with the
pointer scan. A study listing, not a reassemblable source.

A linear disassembly mixes code and data. **Recursive** disassembly follows the flow: entry
point → targets of `bra/bsr/jsr/jmp/Bcc/DBcc` → following instructions until `rts/rte/bra/jmp`.
Additions that bring coverage above 96%:

- relocated `jsr`/`jmp` (targets read from the relocation table);
- jump tables (`jmp 2(pc,d0.w)` + successive `bra`, or word/long tables);
- relocated pointers to code, tried "on trial": disassemble at that address and keep it if the
  result is coherent (no illegal instruction, flow closes up).

Relocations are a major asset: every relocated long word is an address. What is not relocated
(in a normal PRG) is not an address of the program.

### Capstone pitfalls

- shift sizes (`lsl`, `asr`…) sometimes mis-decoded: cross-check;
- 68020 addressing modes are accepted even in 68000 mode: filter them;
- the "base displacement" classification may not match the 68000;
- `movec` rejected (68010+ code);
- a second disassembler (such as `rg-dis`) is used to cross-check doubtful cases.

### Unicorn pitfalls

Set the CPU model **before** `mem_map`:
`uc.ctl_set_cpu_model(UC_CPU_M68K_M68000)`. See `tools/emu_snippets.py` (tested).

## 4. Emit a source where every address is a label

Every byte of the binary is either an instruction or data, and every reference target carries
a label (`L_00001234`). Operands containing a relocated address are written **with the label**,
not the value. Unclassified zones are `dc.b`/`dc.w`/`dc.l`. Everything is explicit (`.w`, `.s`, `.l`).

## 5. Reassemble identically

```sh
vasmm68k_mot -Ftos -tos-flags=<original's flags> -no-opt -nosym -o rebuilt.prg source.s
cmp original.prg rebuilt.prg
```

If `cmp` reports a difference, the cause is almost always:

- a vasm optimisation (forgetting `-no-opt`);
- a different implicit size (short `bra` instead of long);
- a different relocation table (relocation order; check with `prg_info --relocs`);
- a different header flag (`-tos-flags`).

Byte identity is the **stopping criterion** of this step: without it, all later work rests on
sand.

## 6. Shift test

Insert padding (`ds.b 2`) before each function, one at a time, and check the program still
works. If a test fails, a numeric constant that was actually an address (or a hard-coded offset,
or a computed jump) was not converted to a label. This test is what distinguishes a real source
from a "dump that reassembles".

## 7. Compare execution

Run the original and the rebuilt in Hatari with the same key sequence and compare screenshots,
and if needed memory states (`:dump`). See `docs/04`.

## 8. Resources

Extract images, sounds, maps with a round trip: `binary → PNG` then `PNG → binary` must give
exactly the same bytes. A resource format is only "understood" once the round trip is exact.

- **Pictures**: `tools/pi1png.py` (PI1 <-> indexed PNG; the first word and the exact palette
  words are kept in PNG text chunks). Check the colours against a Hatari screenshot: in one
  game the full-screen pictures used the STE nibble order (bit 3 = least significant) while
  the tile-set palettes were stored as linear 0..15 values and converted by the game. Compare
  index -> colour maps on known colours, never by eye.
- **Maps**: render the whole level from the tile set and compare a region with a screenshot
  taken in the game (find the scroll offset by search); in one game 95.4 % of the play field
  pixels were identical, the rest being sprites.
- **Music (YM2149)**: many players are position-independent code + data with a few entry
  points (init with the tune number in `d0`, play once per VBL, effect, stop). Read them in
  the player and in the program's calls, then:
  1. `tools/ym_emu.py PLAYER.BIN --init 0 --play 4 --d0 N`: runs it in Unicorn, records the
     registers per frame, reports accesses outside the player (a player that is not
     self-contained shows up there; one read low memory through a null pointer, see
     `--tos`);
  2. `tools/sndh_wrap.py`: makes an SNDH with the **unmodified** player (`--zero-based` when
     its init expects 0..n-1);
  3. `tools/sndh_record.py`: plays the SNDH in Hatari with a real TOS, compares the YM writes
     frame by frame with `ym_emu.py` and saves the audio (`docs/04`).
  On one game: 9 tunes and 32 effects, every frame identical between Hatari and Unicorn.

## 9. Name, comment

Never rename by hand in the source: keep a **rename file** (`old_label → new_name`) applied by
script, and **rebuild + compare** at every pass. Naming rules: unique prefix (≈ 22 characters
max for the useful vasm symbols), no collisions with reserved words (registers, directives).

## 10. Externalised settings and modifications

- Constants (speeds, number of lives, texts, paths) go in a settings file, with `CHECK_RANGE`
  macros.
- After any variable-length text: `even`.
- **Modifications** (fixes, new functions) sit behind `ifd OPTION` so that the build without
  option stays identical to the original (verifiable with `cmp`).

## 10b. Patching without a full reassembly (compiled programs)

When the program is large and compiled (C, Pascal…), an identical source of the whole program
is not always worth its cost. Proven alternative (racing game, `docs/07`):

- **A study listing only**: recursive disassembly to a listing used for reading, never
  reassembled. The program itself is modified by a patch script.
- **The patch script** checks the input file's MD5, then for every change the original bytes
  (`(address, original bytes, new bytes)` lists), and refuses to write if anything differs.
- **New code appended to the TEXT segment**: the PRG header gives the TEXT, DATA and BSS
  sizes; the script inserts the assembled code at the end of the TEXT, moves the DATA, shifts
  the relocations that point beyond the insertion and adds those of the new code. A table of
  `bra.w` at the start of the added code gives fixed entry points (`base + 4*n`): adding a
  routine never moves the others.
- **Extra variables in the BSS**: enlarge the BSS in the header (zeroed by the TOS, costs no
  file space); the address is known relative to the program's own base register.
- **Compiled-code conventions**: find the base registers (for example a4 = DATA/BSS base,
  a5 = TEXT base with calls through a jump table `jsr n(a5)`). Hooking a function = changing
  its relocated table entry, without touching the callers. Many routines of compiled code
  **modify d0-d7 without saving them**: save what you need around every call.
- **Extending "N players" to N+1**: look for every loop bound and table sized for N (counts,
  `(frame mod 6)/2` round-robins, colour tables, score positions). A slot that used to be
  driven only by the computer was never reset, displayed or blinked like the others: re-check
  every touched function for it.
- **Images modified by the user**: store only the difference (offsets, mask of changed pixels,
  new planes, palette), produced by a script from the new image and a capture of the original.
  The repository then contains the user's drawing, never the original picture.
- **Version number on screen**: reserve a few bytes in the added data, filled by the build
  (`--version` from the git tag), so that every executable tried on the machine is identified.
- **Reproducibility**: `make check` compares the MD5 of the produced program; publish the MD5
  per version (the output depends on the version shown).

## 11. Measurement and equivalence

- Profiling with Hatari breakpoints: count VBLs (breakpoint on the VBL handler) and cycles
  (see `docs/04`).
- For an optimisation of a routine: **equivalence proof** by Unicorn differential test (old vs
  new routine, same inputs, same outputs, all registers and memory compared), plus **mutation
  tests** (introduce a deliberate error and check the test detects it).
- Never announce a gain without a measurement at 50 Hz with a real TOS (`docs/04`).

## Session checklist

- [ ] `prg_info` read, packer identified
- [ ] Unpacking verified (size, coherence)
- [ ] Code coverage measured (% of bytes classified)
- [ ] Reassembled source = original (`cmp`)
- [ ] Shift test passed
- [ ] Hatari comparison
- [ ] Modifications behind `ifd`, default build unchanged
- [ ] What is only tested in Hatari is written as such
