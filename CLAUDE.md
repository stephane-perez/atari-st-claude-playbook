# CLAUDE.md — Programming and reverse engineering for the Atari ST with Claude

Working memo for Claude (claude.ai, Claude Code) and for any human taking over this kind of
project: **writing 68000 code, disassembling Atari ST/STE/Mega STE/Falcon binaries, modifying
programs, testing in an emulator, then on real hardware.**

This file is short and normative. Details are in `docs/` (index at the bottom).
Everything written here was met in real work; the pitfalls are not theoretical.

## Mandatory rules

1. **No claim without the bytes or the trace that back it.** A hypothesis is labelled as such.
   A result is "verified" only if a tool confirmed it (byte-by-byte comparison, run in Hatari,
   test on a real machine).
2. **State clearly what is verified in the emulator only.** Hatari is more permissive than the
   real machine (ports, PSG registers, caches). Never write "it works on STE" when only Hatari
   has seen it.
3. **Say frankly when you do not know, or when the cause of a bug is unknown.** "I don't see
   the cause, here is what has been ruled out" beats an invented explanation.
4. **Never conclude "unavailable / impossible" after a single attempt.** Real case: Hatari
   declared "not installable" because `apt-get update` had not been run (docs/09).
5. **Nothing copyrighted in the repository**: no TOS ROM, no game, no commercial program, no
   disassembly of one, no excerpt of original bytes. See `docs/08`.
6. **Reassemble identically before modifying.** A reconstructed source is only touched once it
   gives back the original binary byte for byte (`-no-opt`). Modifications then sit behind
   assembly options (`ifd`), the "no option" build staying identical.
7. **Measure before optimising**, with the real TOS and at the real frequency (50 Hz). A US
   EmuTOS runs at 60 Hz and skews every frame-rate measurement (docs/04).
8. **Number delivered executables** (0.0.1, 0.0.2, …) and show the number on screen or in the
   name, to keep track between trials on a real machine.
9. **Test with the real assembler and the real emulator**, not only with a home-made test
   bench. A simulator written by Claude (CPU, coprocessor…) is for finding bugs before a
   hardware trial, never for guaranteeing the result.
10. **Do not name new projects in `docs/07`.** Case studies added from now on describe the
    game or program by its genre and technique only (e.g. "Platform game"), never by its
    title or the project's name. Existing entries are kept as they are.

## Setup (≈ 5 minutes)

A conversation's workspace is **temporary**: tools, ROMs, games and working files disappear
when it is recycled. At every new session:

```sh
sh scripts/setup-dev.sh [vasm.tar.gz]   # apt-get update + Hatari, Xvfb, xdotool, mtools, Python (Capstone, Unicorn), vasm
cp /path/to/your/ROMs/*.img tos/        # TOS ROMs supplied by the user (never in git)
sh scripts/smoke-test.sh                # proves the chain: vasm -> Hatari -> TOS 1.04/1.62/2.06/4.04
```

- If the workspace network is restricted (allowlist: package repositories, GitHub), the user
  attaches `vasm.tar.gz` to the conversation; `get-vasm.sh` builds it.
- Expected ROMs: **1.04 → STF**, **1.62 → STE**, **2.06 → Mega STE**, **4.04 → Falcon**.
- No ROM available: EmuTOS 1.3 in Hatari (`docs/04`), never the US image for timing, and
  report "verified with EmuTOS".
- `make` builds the example, `make check` verifies reproducibility.

## Toolbox

| Need | Tool | Detail |
|---|---|---|
| Assemble | `vasmm68k_mot` | `-Ftos -tos-flags=1 -no-opt -nosym` (docs/02) |
| Inspect a PRG | `tools/prg_info.py` | header, relocations, packer signatures |
| Disassemble / emulate the CPU | Capstone, Unicorn | `tools/emu_snippets.py` (tested templates) |
| Test without a screen | `tools/hatari_run.py` | Xvfb + xdotool, screenshots, keys (docs/04) |
| Simulate joysticks | `tools/hatari-joysticks.cfg` | all 6 joysticks on the keyboard, `--down`/`--up` (docs/04) |
| Floppy image | `tools/mkst.py` | dependency-free FAT12 720/820 KB, reproducible |
| GEMDOS calls, memory | `--extra "--trace gemdos"` | `Pexec`/`Mshrink`/`Malloc` in `<out>/hatari.log` (docs/04, docs/05) |
| Texts for the Atari | `tools/txt2st.py` | UTF-8 → ST character set, CR LF, 78 columns |
| IFF pictures | `tools/packiff.py` | ByteRun1 repacking (memory saving) |
| Pack / unpack a PRG | `upx` (`upx-ucl`) | `atari/tos` format; only with the user's agreement (docs/03) |
| Files on SD card / DOS partition | `mtools` | `mcopy -bspm`, `MTOOLS_SKIP_CHECK=1` |

## Typical workflows

- **Write a program**: `.s` source → vasm → Hatari (STF 512 KB first, the most constraining) →
  STE/Mega STE/Falcon → real machine (docs/04, docs/05).
- **Understand a binary**: `prg_info` → unpacking → recursive disassembly → identical
  reassemblable source → shift test → naming → modifications (docs/03).
- **Patch**: prefer rebuilding from an identical source over writing byte patches. If a byte
  patch is unavoidable: check the MD5 and the original bytes before writing. For a large
  compiled program: code appended to the TEXT + enlarged BSS (docs/03, section 10b).
- **512 KB**: every version that makes a program bigger is re-tested on a 520 ST (TOS 1.00 and
  1.04), started from AUTO, with `--trace gemdos` (docs/05).
- **Deliver**: a zip containing the folder ready to copy to the Atari + a `README.TXT`/`TO_TEST.TXT`
  in **plain ASCII without accents** (readable on the Atari) saying exactly what to check.

## Pitfalls to know before starting (the 15 costliest)

1. `apt-get update` before installing anything.
2. vasm optimises by default: without `-no-opt` the binary no longer resembles the original.
3. US EmuTOS = 60 Hz; real French TOS = 50 Hz.
4. Hatari refuses TOS 1.62 in ST mode; TOS 2.06 is accepted in ST mode.
5. A file named "TOS104.IMG" may be a RAM-loaded TOS (256-byte relocator), not a ROM.
6. TOS 2.06 uses more RAM than 1.04: any code assuming a fixed address may break.
7. Reading `$FF9202` (extended joystick ports) on STF or Mega STE: bus error. Compare the
   whole `_MCH` value (Mega STE = `$00010010`). On a real STE, read `$FF9200` before `$FF9202`.
8. A ROM read as a randomness source at `$FC0000` causes a bus error on STE (TOS at `$E00000`).
9. TOS 1.04 leaves the supervisor stack in the bss and GEMDOS writes below the user stack: EmuTOS does not show it.
10. A 16-bit value at an odd address crashes a 68000: `even` after any variable-length text.
11. AZERTY keyboard: compare key codes, not characters.
12. Received "floppy images" are sometimes just packed PRGs: always open the header.
13. An MFP handler runs at mask 6: a slow keyboard (ACIA) handler delays raster interrupts;
    lower the mask to 5 at its start (AEI mode), and measure with `HBL`/`LineCycles`.
14. Hatari fifo key events are scancodes (Esc = `0x01`) and bypass the joystick emulation.
15. Restoring a Hatari saved state clears the breakpoints: set them afterwards.

Full catalogue: `docs/06-pitfalls.md`.

## Documentation index

| File | Content |
|---|---|
| `docs/01-environment.md` | Install and reproduce the environment, network, files to supply |
| `docs/02-vasm-assembler.md` | vasm options, syntax, `-no-opt`, Devpac mode, pitfalls |
| `docs/03-reverse-engineering.md` | Complete method: unpacking → identical source → modification |
| `docs/04-testing-hatari.md` | Headless test bench, measurements, debugger, real machine |
| `docs/05-hardware-and-tos.md` | Machines, TOS versions, memory, cookies, specifics |
| `docs/06-pitfalls.md` | Catalogue of pitfalls met |
| `docs/07-case-studies.md` | Projects carried out and lessons from each |
| `docs/08-law-and-publication.md` | What to publish, what not to publish |
| `docs/09-working-with-claude.md` | Way of collaborating, sessions, resuming, request templates |
