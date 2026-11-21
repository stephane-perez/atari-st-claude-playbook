# 14 — ST Synclock Demosystem (stsys 1.0, Evil / DHS)

"Dead Hackers Society Synclock Demosystem v1.0" (September 10, 2011), by Evil / DHS: a
68000 assembler framework to write a multi-part demo for ST / STE (Falcon for plain ST-LOW
parts only) with fullscreens, syncscrollers, Spectrum 512 pictures and several music players.

- **Not in this repository.** The owner keeps the archive `stsys10.zip` in their private
  `atari-common-tools` repository; its `install.sh` unpacks it to `/opt/stsys10`.
- **Licence: none found.** No licence file, and no licence or copyright statement in
  `readme.txt` or in the sources (the only "Copyright" string is UPX's, inside the packed
  `main.tos`). Without a licence, the default is "all rights reserved": use it for your own
  work, do not republish it, quote no code from it (rule 5). The archive also bundles
  third-party code and data, each with its own author: Lance's 50 kHz Protracker player,
  Pack-Ice depacker (Axe / Delight), LZ77 depacker and 68000 floating-point library
  (ray / tscc), Wizzcat's volume table (Delta Force), and music files by various composers.
- **State.** Read from the sources; `main.s` assembles with the playbook's vasm 2.0f
  (`-Ftos -tos-flags=1`, no error, no warning; optimisations checked with `-showopt`).
  Nothing was run in Hatari or on hardware.

## What it offers

| Effect template (folder) | Machines | Notes |
|---|---|---|
| ST-LOW 320 × 200, double buffer (`stlow.dbl`) | ST, STE, Falcon | 1-VBL effects |
| ST-LOW 320 × 200, triple buffer (`stlow.tri`) | ST, STE, Falcon | effects longer than one VBL; uses `sys/c2p.s` |
| Fullscreen 400 × 273, 230-byte lines (`fullscr.st`) | ST, STE | ≈ 408 usable pixels, the 8 rightmost are garbage on real machines |
| Fullscreen 400 × 273, 224-byte lines (`fullscr.ste`) | STE | picture shifted ≈ 8 pixels right |
| Syncscroll 320 × 265 (`syncscrl`) | ST, STE | 7-line syncscroller `sys/sscrl.s` |
| Syncscroll 400 × 265 in fullscreen (`syncscrl.fs`) | ST, STE | |
| Spectrum 512 / 4096 picture 320 × 199 (`spec512`) | ST, STE | `.spu` picture |

| Music player (`main.s` switch) | Machines | Constraint |
|---|---|---|
| SNDH (`music_sndh`) | ST, STE, Falcon | a tune with timer effects needs `music_sndh_fx=1`, which disables the system's Timer A: ST-LOW parts only |
| YM3 (`music_ym`) | ST, STE, Falcon | file must be unpacked |
| DMA sample sequence (`music_dma`) | STE, Falcon | needs `sys/loader.s` |
| YM 8-bit digi sequence (`music_ymdigi8`) | ST, STE | 8-bit mono 15 650 Hz on the HBL: keep the VBL short; needs `sys/loader.s` |
| Protracker MOD, Lance 50 kHz (`music_mod`) | STE | ≈ 1/3 of the CPU, VBL driven, no CIA timing |

## How it works

`main.s` is the only file to edit for the overall demo; each part lives in its own folder.

- **Switches** at the top of `main.s` (`equ 0/1`): music player, `ste_demo`,
  `falcon_compat`, `show_infos`, `sincos`, sizes `bufsize` (generic BSS), `codesize`
  (buffer for generated code, 100 KB by default), `screensize` (64 KB per screen), and one
  switch per demo part.
- **Start-up** (`sys/init.s`): `Mshrink`, `Malloc` of two screens (aligned on 256 bytes),
  supervisor mode, machine detection by the `_MCH` cookie (plus CT60) into `computer_type`
  (`"ST  "`, `"STe "`, `"MSTe"`, `"TT  "`, `"F030"`, `"F060"`), save of video / palette /
  vectors / MFP, Mega STE set to 8 MHz without cache, keyclick off, mouse off, then each
  part's `_init` (from `initlist`) and the music init.
- **Sequencer** (`sys/vbl.s`): `partlist` is a table of 6 longs per entry,
  `vbls, timer_a_delay, timer_a_div, vbl_routine, timer_a_routine, main_routine`. Each VBL
  decrements `vbls`, moves to the next entry at 0, reloads Timer A (data / prescaler)
  for the synclock part, calls `vbl_routine`, then the music player. A part is usually two
  entries: a short one running `<part>_runtime_init` (preparation while the previous screen
  still shows), then the effect. The list ends with two `-1` entries (black palette, `exit`).
- **Main loop** (`sys/mainloop.s`): waits for the VBL flag and calls `main_routine`; the
  work that does not need exact timing goes there.
- **Timer A** (`sys/timers.s`): calls `timer_a_routine`. The synclock parts start it with
  `do_hardsync_top_border` (opens the top border, then synchronises on the video counter
  `$FFFF8209` with the `lsr.l d1,d1` trick) and run code generated into `codebuf` (one
  block per scanline: left border, right border, stabiliser, special block for the lower
  border lines 227-228).
- **Helpers** (`sys/common.s`): macros `run_once`, `remove_top_border`,
  `do_hardsync_top_border`, `do_hardsync`, `do_syncscroll`; routines `code_copy`,
  `clear_screens`, `black_pal`, `white_pal`, `syncfix`, `rastertime`, `print`, `waitkey`.
  `sys/fade.s` (`fade`, `component_fade`), `sys/loader.s` (file loader), optional
  `sys/ice.s`, `sys/lz77_000.s`, `sys/mth68000.s`.
- **Exit**: Space (scancode `$39`) at any time, or the end of `partlist`; `sys/exit.s`
  restores everything saved at start-up.

### Adding a part

1. Copy a template folder (closest effect type), rename its labels (`<part>_init`,
   `_runtime_init`, `_vbl`, `_ta`, `_main`).
2. In `main.s`: a switch, an `include` under "User demopart includes", a `jsr <part>_init`
   in `initlist`, two entries in `partlist` (Timer A values `97,4` for the fullscreen and
   syncscroll templates, `190,4` for Spectrum 512, `0,0` for ST-LOW parts).
3. Pictures: the fullscreen and syncscroll templates include a `bmpconv.s` that converts an
   8-bit indexed BMP into 4-bitplane data (`.4pl`).

## Build and test with the playbook

```sh
cp -r /opt/stsys10 work && cd work          # never edit /opt/stsys10 in place
vasmm68k_mot -Ftos -tos-flags=1 -quiet main.s -o DEMO.TOS
python3 tools/mkst.py out/demo.st DEMO work/DEMO.TOS:AUTO/DEMO.PRG work/music/<file>:<FILE>
python3 tools/hatari_run.py --disk out/demo.st --tos tos/TOS162.IMG --machine ste --mem 1024 \
    --borders on --out out/demo 20 30
```

- The authors build with vasm's default optimisations (`readme.txt`). Measured on the example:
  vasm optimises 176 instructions (`-showopt`; the `-no-opt` build is 296 bytes longer), and
  none of them falls inside a cycle-counted block: in the `_ta` routines only the `jsr` placed
  after the timed code are turned into `bsr`. Both builds should therefore time the same.
- In your own synclock code, **every `dcb.w n,$4e71` count assumes the exact instructions
  written**: an optimised `jsr`→`bsr`, `move.l #x,Dn`→`moveq` or `add`→`addq` inside a timed
  block changes its length in cycles. Check with `-showopt`, or keep those blocks free of
  optimisable forms.
- `--borders on` is required to see the fullscreen and syncscroll parts in the screenshots.

## Points to watch

1. **`ste_demo` is 1 in the shipped `main.s`**: the demo prints "Needs STe hardware" and quits
   on an ST. For an ST demo set it to 0 and disable `fullscr_ste` and `music_mod`/`music_dma`.
2. **Memory**: the example with every part enabled assembles to TEXT 30 KB + DATA 321 KB +
   BSS 367 KB, plus two 64 KB screens from `Malloc`: about 850 KB, so **1 MB minimum**.
   Disable unused parts and lower `codesize`/`bufsize` for a 520 ST (test with TOS 1.00 / 1.04,
   playbook rule on 512 KB).
3. **Synclock = exact cycles**: fullscreen and syncscroll code is counted in NOPs for an 8 MHz
   68000. Hatari is more tolerant than a real ST (rule 2): the 230-byte template's own comment
   says the 8 rightmost pixels are garbage "on real machines". Test on hardware; STE and
   STF wake-up states can differ.
4. **Falcon**: only with `falcon_compat=1` and ST-LOW parts; synclock parts do not work on
   Falcon or TT by nature; the TT is refused at start-up (no 50 Hz screen).
5. **Interrupt budget**: the SNDH player with timer effects takes Timer A; the YM digi player
   runs on the HBL. An ACIA (keyboard) interrupt during a synclock block shifts it: the
   system kills the mouse at start for that reason (pitfall 13 of `CLAUDE.md`).
6. The shipped `main.tos` is **UPX-packed** (its header does not show a packer signature in
   the first 4 KB; `strings` shows UPX): rebuild from source rather than studying it.
