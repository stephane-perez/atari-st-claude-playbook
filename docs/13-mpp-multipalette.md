# 13 — MPP: multi-palette and overscan pictures (ST / STE)

MPP ("Multi Palette Picture") is a picture format and tool set by Zerkman / Sector One
(François Galea): a PC converter `bmp2mpp` that turns a 24-bit BMP into an ST picture whose
palette changes many times per scanline, a reverse converter `mpp2bmp`, and a 68000 viewer
(`MPPVIEW.TTP`) / decoding library (`mppdec.s`) that replays the palette changes with the CPU
or the blitter, optionally in overscan.

- Source: **https://codeberg.org/zerkman/mpp** (the GitHub repository `zerkman/mpp` only says
  "moved"). Licence: WTFPL v2. Not copied into this repository: this page only describes it.
- Analysed revision: `2ba52a4` (2026-05-19, "Updated the documentation"); the last release
  in the `Changelog` is 1.1 (2013-12-10).
- **State:** limits read from the README, the `Mode` table of `bmp2mpp.c` and the plugin
  headers of `mode0.s` … `mode3.s`. `make` (host GCC + vasm 2.0f) builds `bmp2mpp`, `mpp2bmp`
  and `mppview.tos` (warnings only), and the converter was run on a test picture (see
  "Measured"). The viewer was **not** run (Hatari or hardware).

## Answers in short

| | STF (no blitter) | STE |
|---|---|---|
| Largest picture | **416 × 276** (mode 3, overscan) | **416 × 276** (mode 3, overscan) |
| Palette (distinct colours available) | **512** (9-bit ST palette) | **4096** (12-bit), or **29 791** perceived with `--extra` / `--double` (15-bit, two palettes alternated every frame) |
| Most colours on one scanline | **54** (mode 0, 320 × 200); in overscan 48 new + 6 carried from the previous line | **56** (mode 2, blitter, 320 × 200); in overscan same as STF |
| Notes | a 12-bit (STE) MPP is shown on an ST by alternating two 9-bit palettes (simulated extra bit); a 15-bit `--extra` picture is shown with the extra bit ignored | mode 2 needs a blitter, so it also runs on a Mega ST, not on a plain STF |

The total number of colours in one picture is bounded by the palette, not by the
scanlines: in mode 3, 48 new colours × 276 lines ≫ 4096. So a full-screen overscan picture
can in principle use every ST colour (512) on an STF, and every STE colour (4096) on an STE;
how many it really uses depends on the source picture and the converter.

## The four modes

| Mode | Size | Drives the palette with | Colours per scanline | Default palette |
|---|---|---|---|---|
| 0 | 320 × 200 | CPU | 54 (52 stored + 2 black), change positions non-uniform | ST 9-bit |
| 1 | 320 × 200 | CPU | 48 (46 stored + 2 black), uniform positions | ST 9-bit |
| 2 | 320 × 200 | **blitter** (`flag_blitteronly`) | 56 (54 stored + 2 always black) | STE 12-bit |
| 3 | **416 × 276**, overscan, 230-byte lines | CPU | 48 stored + 6 shared with the previous line; 44 on the lines that open the vertical border | ST 9-bit |

- Each palette entry is valid from a fixed x position on the line (`xinc` functions of
  `bmp2mpp.c`): the converter assigns pixels to the 16 colours active at their position,
  hence the optimisation (greedy start, then simulated annealing, `-0` … `-9`).
- The mode 3 BMP must be exactly 416 × 276, the others exactly 320 × 200, uncompressed 24-bit.
- Machine support in `mppdec.s` (`_MCH` cookie): ST, STE, Mega STE (the viewer clears
  `$FFFF8E21` = 8 MHz, cache off); **TT and Falcon are refused**. Blitter detection: a read of
  `$FFFF8A2A` under a bus-error trap.

## Converter (`bmp2mpp`, host C program)

```sh
cc -O3 -o bmp2mpp bmp2mpp.c -lm          # or: make bmp2mpp
./bmp2mpp --mode=3 -9 picture.bmp        # -> picture.mpp, overscan, ST palette
./bmp2mpp --mode=3 --ste -9 picture.bmp  # overscan, STE palette
./bmp2mpp --mode=2 --ste --extra pic.bmp # 320x200 blitter, 15-bit perceived palette
```

| Option | Effect |
|---|---|
| `--mode=0..3` | mode (default 0) |
| `--st` / `--ste` | 9-bit or 12-bit palette (`--ste` is the default only in mode 2) |
| `--extra` | 15-bit palette in one image (STE palette required) |
| `--double` | two 12-bit images alternated (15-bit perceived, file twice as big) |
| `-0` … `-9`, `--optimal` | effort; `--optimal` = branch and bound, for curiosity |
| `--title= --artist= --ripper= --year=`, `--nompph` | `MPPH` metadata block (like SNDH tags) |
| `--raw` | raw palette instead of an MPP file |

`mpp2bmp file.mpp` converts back (C, with `pixbuf.c`).

## Viewer and library (68000)

- `make mppview.tos` assembles with **vasm** (`vasmm68k_mot -quiet -m68000 -Ftos`): the
  playbook's assembler is enough. `mppview.s` includes `mppdec.s` and the four mode plugins.
- `MPPVIEW.TTP file.mpp` shows one picture; without argument (or renamed `.TOS`) it runs a
  slide show of every `.MPP` file in the current folder.
- In your own program (`example.s`): `mpp_init` (machine and blitter detection, in supervisor
  mode), `mpp_decode` (a0 = file in memory, a1 = structure + buffers), then `mpp_setup_img`.
  The caller allocates the screen(s) and unpacked palettes: size depends on the mode and on
  double image / 12-bit-on-ST cases, which need a second palette.
- Display uses Timer A and the VBL; the palette writes are timed in cycles (`LineCycles`
  comments in `mode3.s`). Anything else running under interrupt (music, keyboard) can shift
  them: see pitfall 13 of `CLAUDE.md` before adding code.

## File format (header 12 bytes, big endian)

```
"MPP"            3 bytes
mode             1 byte (0..3)
flags            1 byte: bit0 STE palette (12-bit), bit1 extra bit (15-bit), bit2 double image
reserved         3 bytes (0)
extra_len        4 bytes, even: length of the MPPH block that follows ("MPPH" tags… "HPPM")
palette          bits per entry × number of entries, rounded up to 16 bits
bitmap           ST interleaved bitplanes, width rounded to 16, × height / 2 bytes
[palette, bitmap] second pair when "double image"
```

Bits per palette entry: 9 (ST), 12 (STE), 15 (STE + extra).

## Points to watch

1. The 12-bit and 15-bit palettes are shown by **alternating palettes every frame** (25 Hz
   flicker per half-palette at 50 Hz): fine on a CRT, judge it on the target screen.
2. Mode 2 is refused when no blitter answers (`mpp_decode` returns -1).
3. Mode 3 is overscan with exact cycle timing: Hatari accepts more than a real machine does
   (rule 2). The `Changelog` mentions a fix for "some STe's" (1-pixel palette shift in modes
   0, 1, 3): test on the real STE.
4. Memory: one 416 × 276 screen is 63 480 bytes, plus palettes (48 words × 276 lines,
   twice for 12-bit on ST or 15-bit); `double` doubles everything. Check on a 520 ST.

## Measured (converter only, 2026-11)

Test picture: an original 24-bit gradient (hue across, brightness down), converted with
`-3`, then back with `mpp2bmp`; colours counted on the BMP produced:

| Run | Size | Distinct colours in picture | Max on one line | `.mpp` size | Time |
|---|---|---|---|---|---|
| `--mode=3 --st` | 416 × 276 | 460 (of 512) | 48 | 72 378 B | 0.06 s |
| `--mode=3 --ste` | 416 × 276 | 2013 | 48 | 77 346 B | 0.3 s |
| `--mode=0 --st` | 320 × 200 | 423 | 52 | 43 766 B | 0.03 s |
| `--mode=2 --st` | 320 × 200 | 423 | 52 | 44 216 B | 0.03 s |
| `--mode=2 --ste` | 320 × 200 | 1604 | 54 | 48 266 B | 0.1 s |

These are results for this picture, not maxima: a picture with black areas also uses the
two black entries of modes 0–2. The converter prints one `y=… gain=…` line per scanline:
redirect it. Header seen: `MPP`, mode, flags (1 = STE), then `extra_len` = `$36` (MPPH block).

## Viewing in Hatari (not done)

```sh
make AS=/path/to/vasmm68k_mot             # bmp2mpp, mpp2bmp, mppview.tos
./bmp2mpp --mode=3 -3 test416x276.bmp && ./mpp2bmp test416x276.mpp back.bmp
python3 tools/mkst.py out/mpp.st MPP mppview.tos:MPPVIEW.TOS test416x276.mpp:TEST.MPP
python3 tools/hatari_run.py --disk out/mpp.st --tos tos/TOS104.IMG --machine st --mem 1024 --out out/mpp 25 35
```

Then STE (TOS 1.62) with `--ste`, and mode 2 on STE; compare the screenshot with `back.bmp`.
