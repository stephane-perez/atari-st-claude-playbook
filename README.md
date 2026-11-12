# Atari ST + Claude: a field manual

Everything that, over several projects, made it possible with Claude to write 68000 code,
disassemble Atari ST/STE/Mega STE/Falcon binaries and test them: method, tools, pitfalls.
(Version française : [`README_fr.md`](README_fr.md).)

- **`CLAUDE.md`**: rules and short memo (read automatically by Claude Code).
- **`docs/`**: the details (environment, vasm, reverse engineering, Hatari testing, hardware/TOS,
  pitfalls, case studies, law, working with Claude).
- **`tools/`**: `hatari_run.py` (headless Hatari), `hatari-joysticks.cfg` (joysticks on the
  keyboard), `mkst.py` (FAT12 images), `prg_info.py` (PRG inspector), `emu_snippets.py`
  (Capstone/Unicorn), `txt2st.py` (texts in the ST character set), `packiff.py` (IFF ILBM
  repacked with ByteRun1), `stx.py` (Pasti .STX reader), `unice.py` (Pack-Ice 2.3x/2.40
  depacker) and `unice_fuzz.py` (its differential test), `m68k_recdis.py` (recursive
  disassembler), `m68k_mksrc.py` (identical vasm source from a raw image), `pi1png.py` (PI1 <-> PNG), `ym_emu.py`, `sndh_wrap.py`, `sndh_record.py` and
  `sndhplay.s` (music players: emulation, SNDH, recording in Hatari).
- **`scripts/`**: installation, vasm, end-to-end test.
- **`examples/hello`**: minimal original example.
- **`examples/sndh/beep.s`**: a tiny original SNDH tune, test input for the music tools.
- **`examples/acsi-stream/`**: C++ headers to stream a sample from an ACSI hard disk with
  non blocking DMA reads (`docs/11`); `tools/mkacsi.py` and `tools/acsi_bench.py` build and use
  an ACSI disk image in Hatari.

## Getting started

```sh
sh scripts/setup-dev.sh [vasm.tar.gz]
cp /your/ROMs/*.img tos/      # TOS ROMs: supply them yourself, never in git
sh scripts/smoke-test.sh      # STF 1.04, STE 1.62, Mega STE 2.06, Falcon 4.04
make && make check
```

## What is verified, and what is not

Verified (Hatari 2.4.1, vasm 2.0f): reproducible build, valid FAT12 image (`fsck.fat`),
example run under the four TOS versions. **Not verified on a real machine.**

## What is not here

ROMs, games, disassemblies of commercial programs, protection circumventions
(see `docs/08-law-and-publication.md`). Tools from past projects are not included.

License: MIT, except `third_party/` (own licences: vasm is redistributed unmodified,
non-commercial use; see `third_party/README.md`).
