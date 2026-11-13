# 10 — AGT (Atari Game Tools): using the library

AGT is a C++/68000 framework by dml (Doug Little) for prototyping **STE** games quickly:
hardware-scrolled playfields, sprites with generated drawing code, entities, IKBD input,
sound and music, an asset pipeline on the host.

- Source: **https://bitbucket.org/d_m_l/agtools** (wiki: `https://bitbucket.org/d_m_l/agtools/wiki/Home`).
- **AGT is not included in this repository** and must not be added to it: fetch it from
  the source above (or have the user attach it). No licence file was found for AGT
  itself in the analysed snapshot (only for bundled third-party code such as ZX0), so
  nothing of it is copied here; this page only describes how to use it.
- Analysed snapshot: archive `d_m_l-agtools-a155d4194a91` (commit `a155d4194a91`).
  Other revisions may differ.

## Status of this page

| Point | State |
|---|---|
| Layout, build system, API | read from the sources |
| Cross toolchain built from `vinriviere/cross-mint-ubuntu` (Ubuntu 24.04 host) | **verified** (2026-11) |
| `agtcut` asset cutting of `examples/sprtest` (prebuilt Linux x86_64 tools) | **verified** |
| `examples/hiworld` built and run | **verified in Hatari** (STE, TOS 1.62): text and the 20 pseudo-random values match a host recomputation |
| `examples/sprtest` built and run from a floppy image | **verified in Hatari** (STE, TOS 1.62, 1 MB): assets load, hardware claimed, help screen, the four sprite types drawn |
| Other examples, demos, STF / Mega STE / Falcon | not tried |
| Real machine | not tried |

Everything below marked *(hypothesis)* comes from reading the code and has not been checked
by a build or a run.

## What is in the tree

| Folder | Content |
|---|---|
| `agtsys/` | the engine: C++ (`system`, `shifter`, `playfield`, `arena`, `tileset`, `worldmap`, `spritesheet`, `slabsheet`, `entity`, `input`, `ealloc`, `compress`, `fileio`, `sound/`) |
| `agtsys/m68k/` | assembly (rmac syntax): `sys.s` (machine claim), `ikbd.s` (input), `sound.s`, `qmem.s`, `ste/` (display, playfield, sprite and blitter routines) |
| `agtsys/libcxx/` | minimal C runtime (`zeroboot.s`, `zerolibc.cpp`) used when `LINK_MINIMAL=yes` |
| `3rdparty/m68k/` | depackers (LZ77, LZSA, ZX0, ARJ m4/m7, NRV2e), Jaguar pad reading, Hatari NatFeats, ultraDev |
| `bin/<host>/<arch>/` | prebuilt host tools: `rmac`, `agtcut`, `pcs2agi`, `packwrap`, `lz77`, `lzsa`, `zx0` (Linux x86_64 and aarch64, macOS, Windows) |
| `tools/` | sources of the host tools (C++), rebuildable with a host GCC |
| `examples/` | `hiworld` (compiler test), `sprtest`, `map8x8`, `map8x8x2layer`, `map16x16x2layer`, `parallax`, `bganim`, `layeranim`, `giantsprites` |
| `demos/` | larger samples: horizontal shmup, isometric scroll, top-down shooter (+ co-op), boss fight |
| `tutorials/tutor1` | the Shifter interface (double buffer, hardware scroll); comments mention `tutor0` and `tutor4+`, absent from this snapshot |
| `data/` | shared palettes (`colmap.ccs`), music (`.bmu`), sounds (`.wav`) |
| `scripts/` | `pack.sh` (asset packing), `copyassets.sh`, `post_image.sh` (empty stub), `post_ultra.sh` |

## Toolchain

AGT does **not** use vasm. It needs:

1. **`m68k-atari-mint-gcc`** (default: GCC 4.6.4, Vincent Rivière's build, installed in
   `/opt/cross-mint`, on the `PATH`). Other choices in `makedefs`: `USE_COMPILER=browncc`
   (ELF GCC + brownout), `mikrocc`, and `GCC_VERSION` 6.2 … 12.1.
   MiNTlib headers are needed even with `LINK_MINIMAL=yes` (`<mint/sysbind.h>`, `<stdio.h>`).
2. **rmac** (the assembler for all `.s` files, Madmac syntax, not Devpac/vasm): the prebuilt
   one in `bin/` is used. `agtcut` also calls rmac to generate sprite code (EMX).
3. GNU Make and bash (`config.sh` uses bash syntax).

On Ubuntu the usual route is Vincent Rivière's PPA (`ppa:vriviere/ppa`, packages
`cross-mint-essential` or `gcc-m68k-atari-mint` + `binutils-m68k-atari-mint` +
`mintlib-m68k-atari-mint`). The packages install into `/usr` (not `/opt/cross-mint`).

**Restricted network.** In a Claude workspace with an allowlist, it was observed (2026-11) that
`ppa.launchpadcontent.net`, `launchpadlibrarian.net`, `api.launchpad.net`,
`tho-otto.de` and `vincent.riviere.free.fr` are refused, while `launchpad.net` and GitHub
answer. Three ways out: allow the two Launchpad hosts in the environment's network settings,
attach the `.deb` files to the conversation, or build them from GitHub as below. Running the
prebuilt binaries of `bin/` and building external code need the user's explicit agreement.

### Building the `.deb` files from GitHub (verified, ≈ 16 min on 4 cores)

`https://github.com/vinriviere/cross-mint-ubuntu` holds the Debian source packages that feed
the PPA (upstream tarballs + MiNT patches + `debian/`). **`scripts/get-cross-mint.sh` does
everything below**, keeps the five `.deb` files in `.tools/cross-mint/debs/` and ends by
compiling and linking a small C program with MiNTlib:

```sh
sh scripts/get-cross-mint.sh               # build from GitHub (≈ 16 min), then install
sh scripts/get-cross-mint.sh /path/to/debs # next session: install the kept .deb files only (seconds)
```

What the script does by hand (GCC and MiNTlib depend on each other, so a temporary C-only
GCC, "stage 1", is built first):

```sh
apt-get install -y devscripts debhelper fakeroot texinfo bison flex libfl-dev gettext \
    autoconf bzip2 xz-utils libgmp-dev libmpfr-dev libmpc-dev g++ make rsync
git clone --depth 1 https://github.com/vinriviere/cross-mint-ubuntu cmu
(cd cmu/binutils-m68k-atari-mint && dpkg-buildpackage -b -us -uc -j4)
dpkg -i cmu/binutils-m68k-atari-mint_*.deb
(cd cmu/mintbin-m68k-atari-mint && dpkg-buildpackage -b -us -uc -d)

# stage 1: C only, no headers, private prefix
TOP=$PWD; S=$TOP/stage1; mkdir -p $S/src $S/build && cd $S/src
tar xf ../../cmu/gcc-m68k-atari-mint/gcc-4.6.4.tar.xz && cd gcc-4.6.4
xzcat ../../../cmu/gcc-m68k-atari-mint/gcc-4.6.4-mint-*.patch.xz | patch -p1
cd $S/build && ../src/gcc-4.6.4/configure --prefix=$S/install --target=m68k-atari-mint \
    --disable-nls --enable-languages=c --without-headers --disable-libssp \
    --disable-threads --disable-shared
make -j4 all-gcc all-target-libgcc && make install-gcc install-target-libgcc
# stage 1 must see the MiNT binutils and (later) the MiNTlib headers:
mkdir -p $S/install/m68k-atari-mint/bin
for t in as ld ar nm ranlib objcopy objdump strip; do
  ln -sf /usr/bin/m68k-atari-mint-$t $S/install/m68k-atari-mint/bin/$t; done
ln -sfn /usr/m68k-atari-mint/include $S/install/m68k-atari-mint/include
ln -sfn /usr/m68k-atari-mint/lib     $S/install/m68k-atari-mint/lib
cd $TOP

(cd cmu/mintlib-m68k-atari-mint && PATH=$S/install/bin:$PATH dpkg-buildpackage -b -us -uc -d -j4)
dpkg -i cmu/mintlib-*.deb cmu/mintbin-*.deb
(cd cmu/pml-m68k-atari-mint && PATH=$S/install/bin:$PATH dpkg-buildpackage -b -us -uc -d -j4)
dpkg -i cmu/pml-*.deb
(cd cmu/gcc-m68k-atari-mint && dpkg-buildpackage -b -us -uc -j4)    # the real C/C++ compiler
dpkg -i cmu/gcc-m68k-atari-mint_*.deb
m68k-atari-mint-g++ --version     # GCC 4.6.4 (MiNT 20251014)
```

Failures met on the way: without the `bin/` links, stage 1 calls the host `as`
(`unrecognized option '-m68000'`); without the `include` link, PML stops on `stdio.h`.
Keep the five `.deb` files: in a later session `dpkg -i *.deb` is enough.

## Building

Verified recipe with the Debian packages above (Ubuntu 24.04 host):

```sh
ln -sfn /long/path/to/agtools /tmp/agt     # SHORT path: rmac crashes on long -I paths
export AGTROOT=/tmp/agt                    # must be exported (assets_com.sh bug, see below)
MK="make -j4 TOOLCHAIN_INSTALL=/usr AR=/path/to/playbook/tools/mint-ar"
cd $AGTROOT/examples/hiworld && $MK        # build/hiworld.prg, build/mchdet.prg -> disk1/, disk2/
cd $AGTROOT/examples/sprtest && bash assets_com.sh && $MK   # assets (≈ 40 s), then disk1/
```

- `TOOLCHAIN_INSTALL=/usr`: `makedefs.mintgcc` expects `/opt/cross-mint`, the packages
  install into `/usr`.
- `AR=…/tools/mint-ar` (in this repository): on a host with `/usr/lib/bfd-plugins/` (LLVM gold, GCC LTO plugins), the MiNT
  `ar`/`nm` see **no symbols** in the a.out objects written by rmac; the archive index of
  `aglib_ste.a` then lacks `_SYS_Claim`, `_qmemclr`, `_bSTE`… and the link fails with
  "undefined reference" (also to `___mulsi3`, a consequence). Forcing `a.out-zero-big` fixes it.
  `m68k-atari-mint-nm --target=a.out-zero-big x.o` shows the symbols.
- rmac (`bin/Linux/x86_64/rmac`) segfaults when an include path is long (≈ 140 characters
  crashed, a short absolute path works): keep `AGTROOT` short.
- `copyassets.sh` uses `rsync` (install it).

- Each project `Makefile` sets `PROJECT`, `BUILD_CFG` (`debug` / `testing` / `release`),
  `AGLIB=$(AGLIB_STE)`, the project sources and assets, then includes
  `$(AGTROOT)/makedefs` and `$(AGTROOT)/makerules`.
- The library (`build/aglib_ste.a`) is rebuilt **inside each project** from the AGT sources.
- Output: `build/<name>.prg` (linked as `.tos`, renamed by a `%.prg: %.tos` rule), copied to
  `disk1/auto/` with the assets.
  `make images` calls `scripts/post_image.sh`, which is an empty stub: use `tools/mkst.py`
  from this repository to make a floppy image.
- Useful `Makefile` switches: `USE_HATARI_NATFEATS=yes` (console output to Hatari),
  `USE_HATARI_DEBUGGING=yes` (symbol file `.sym` for the Hatari debugger),
  `USE_DEBUG_CONSOLE=native|udev`, `POST_REMOTE=ultradev|hxcusb`,
  `USE_UPX_PACKER=yes` (release builds only). Engine flags (`-DAGT_CONFIG_…`,
  `-DTIMING_RASTERS`) are listed on the wiki page "Compiletime Flags".
- `LINK_MINIMAL=yes` (default) links AGT's own startup code instead of MiNTlib; the stack is
  `STACKSIZE=16384` (the comment asks for ≈ 12 KB headroom for the ARJ m7 depacker).
- `BUILD_CFG=release` uses `-Ofast -fomit-frame-pointer`; `debug` uses `-g -Os`.

## Program structure

From `tutorials/tutor1` and `examples/map8x8` (order of the calls, simplified):

```cpp
machine     machinestate;      // claim / restore of the machine
shifter_ste shift;             // display service (STE)
S_SUPER_SSP(AGT_CONFIG_STACK);
AGT_MAIN;                      // defines the real entry point

int AGT_EntryPoint()
{
    machinestate.configure();              // detection: bSTF, bSTE, bMegaSTE, bTT, bFalcon030
    // ... load assets HERE, TOS is still in charge (load_cct, load_ccm, sprite sheets, music)
    machinestate.save();
    shift.configure(); shift.save();
    machinestate.claim();                  // vectors and MFP taken over
    AGT_InstallInputService();             // AGT keyboard / joystick / mouse handler
    shift.set_fieldmode(false); shift.init();
    // palette: shift.setcolour(buffer, field, index, rgb) for both buffers
    EntitySetup(EntityType_MAX_);
    // world: arena_t world(shift, w, h); world.setmap(&map); world.settiles(&tiles,&tiles);
    // loop:
    //   shift.wait_vbl();
    //   EntityTickAll(); EntityInteractVisible(...); EntityExecuteAllLinks(); EntityExecuteAllRemoves();
    //   world.select_buffer(n); world.setpos(x, y); world.bgrestore(); world.hybrid_fill(false);
    //   world.get_context(dc, 0, w, h); EntityDrawVisible(&dc); world.activate_buffer();
    shift.restore();
    machinestate.restore();
    return 0;
}

entitydef_t entity_dictionary[] = { /* one entry per entity type */ };   // required, even empty
```

- Playfields are C++ templates: `playfield_template<tilesize, max_scroll, VScrollMode_…,
  HScrollMode_…, RestoreMode_…, UpdateMode_…, PlayfieldHardware(PFH_STE|PFH_Blitter),
  PlayfieldAttributes(PFA_…), guardx, guardy, maptype>`, grouped in an
  `arena_template<buffers, singleframe, dualfield, playfield_t>` (double buffering).
- Input after `AGT_InstallInputService()`: `key_states[]`, `AGT_debouncedKeyPressed(scancode)`,
  `AGT_popKey()`, `joy0`/`joy1` and their event rings, mouse clicks. Scancodes, not
  characters (AZERTY: see pitfall 11 of `CLAUDE.md`).
- Sound: `AGT_SoundOpen()` / `AGT_SoundClose()`; music `AGT_MusicLoad("x.bmu")`,
  `AGT_MusicStart(looping)`, `AGT_MusicStop()`.
- Fixed-size types: `s8/u8/s16/u16/s32/u32`; direct register access with `reg16(FFFF8240)`.

## Asset pipeline (host side)

Each example has an `assets_com.sh`, run by `make assets`; it calls `agtcut` from
`bin/<host>`:

| Mode `-cm` | Produces | Use |
|---|---|---|
| `tiles` | `.cct` (tile library) + `.ccm` (map) | playfields; `-ts 8/16`, `-layer` for 2-layer maps |
| `imspr` | `.sps` | sprites drawn by a generic routine (with mask; `-nogm` for STF) |
| `emspr` | `.ems` | sprites with generated code (less memory) |
| `emxspr` | `.emx` | generated code, most optimised (`-emxopt`, slow to cut; uses rmac) |
| `emhspr` | `.emh` | generated-code variant used by `sprtest` (works, but missing from `agtcut -h`) |
| `slabs` / `slabrestore` | `.sls` / `.slr` | large blocks drawn and restored without masking |

- Common options: `-s source.png`, `-o out`, `-p palette` (`.pi1`, `.ccs`, `.png`),
  `-keyrgb ff:00:ff` (transparent colour), `-crn 224` (renormalise RGB stretched to 255),
  `-bp 4`, cutting by grid (`-sxs -sys -sc`), by crosshair (`-ackeyrgb`) or by a guide file
  (`-sg x.sgd`). The full guide is `tools/agtcut/usage.txt` in the AGT tree; it documents
  v0.41 while the prebuilt binary is v0.475b: `agtcut -h` is the reference.
- `assets_com.sh` tests `"${AGTROOT}+x" = "x"`, which is never true: when `AGTROOT` is
  unset it stays empty (instead of `../..`) and the script fails on `/config.sh`.
  Always `export AGTROOT`.
- Packing: `scripts/pack.sh <file> <mode>` with `wrap`, `lz77` (fastest), `lzs1`,
  `lzs2`/`lzsa` (best balance), `zx0`, `pk2e`/`arj4`/`arj7` (Windows only).
  The unpacker for a mode is only linked in if the project defines it:
  `-DAGT_CONFIG_PACKER_LZSA` (or `_LZ77`, `_ZX0`, `_ARJ4`, `_ARJ7`, or `_ANY`) in
  `COMPILERDEFS`; otherwise `compress.cpp` prints a warning at load time.

## Using it with this playbook

Verified with `examples/sprtest`:

```sh
D=$AGTROOT/examples/sprtest/disk1
python3 tools/mkst.py out/sprtest.st SPRTEST $D/auto/sprtest.prg:AUTO/SPRTEST.PRG \
    $D/bg.ccm:BG.CCM $D/bg.cct:BG.CCT $D/1ems.ems:1EMS.EMS $D/2emx.emx:2EMX.EMX \
    $D/3emh.emh:3EMH.EMH $D/4slab.slr:4SLAB.SLR $D/4slab.sls:4SLAB.SLS
python3 tools/hatari_run.py --disk out/sprtest.st --tos tos/TOS162.IMG --machine ste --mem 1024 \
    --out out/sprtest --key space@45 --key 1@52 --key 2@53 --key 3@54 --key 4@55 40 58 64
```

- Loading from the emulated floppy is slow: "ready... (press key)" appeared between 32 s and
  40 s; a key sent at 22 s was lost. Take a screenshot before sending the key.
- Simple programs that load nothing (`hiworld`) can be started with `--prg`.
- STE first (TOS 1.62), then Mega STE (2.06) and Falcon (4.04): AGT targets the STE.
- `USE_HATARI_NATFEATS=yes` sends `printf` output to Hatari's console; with
  `USE_HATARI_DEBUGGING=yes` load the `.sym` file in the debugger (`symbols prog.sym`).
- Measure at 50 Hz with the real TOS (rule 7); `-DTIMING_RASTERS` shows the time per frame
  as background colour bands.

## Points to watch (found while reading the code)

1. **STE only in this snapshot.** `makedefs` lists `agtsys/m68k/stf/*.s` for `aglib_stf.a`
   but that folder does not exist: an STF build cannot link *(hypothesis: not tried)*.
   `tutor1` refuses anything other than STE / Mega STE / Falcon.
2. **`bSTE` is also true on a Mega STE** (test on the upper word of `_MCH` = 1). Test
   `bMegaSTE` first when the two must be told apart.
3. **Jaguar pads**: `AGT_SampleJoyPads` (`3rdparty/m68k/ste/joypad.s`) reads `$FF9202`
   without testing the machine. It is not called by the examples; on an STF or a Mega STE
   this read gives a bus error (pitfall 7 of `CLAUDE.md`). Call it only if `bSTE && !bMegaSTE`.
4. **After `machinestate.claim()` TOS is no longer in charge**: `$118` (IKBD), Timer A/B,
   HBL, VBL are replaced and the MFP interrupt enables cleared; `Crawcin()` no longer works
   until AGT's input service is installed. The examples load every file **before** `claim()`
   — do the same *(hypothesis: disk access after the claim not tried)*.
5. Always provide `entity_dictionary[]`, even empty: the link needs it.
6. A tutorial buffer declared as a global array may end up in TT-RAM on a TT/Falcon with
   fast RAM (warning in `tutor1`): screen memory must be ST-RAM (`Mxalloc(…, 0)`).
7. The Linux prebuilt binaries may lack shared libraries (`config.sh` warns about it);
   in that case rebuild the tools from `tools/` with the host GCC. On Ubuntu 24.04 x86_64
   all seven (`rmac`, `agtcut`, `pcs2agi`, `packwrap`, `lz77`, `lzsa`, `zx0`) ran as is.
8. The executables are linked with PRG flags `$7` (fastload + load and malloc in TT-RAM)
   (seen with `tools/prg_info.py` on `hiworld.prg`); screen buffers must still be ST-RAM.
9. **Slow start-up with big uncompressed assets: the CRC check (optional).**
   `spritesheet::load`, `slabsheet::load` and `tileset::load` compute a CRC over the **whole**
   uncompressed asset file (`gen_crc`: FNV-style, one 32-bit multiplication per 16-bit word,
   in C) and halt the program on a mismatch. With five 480–700 KB EMX sprite files this was
   almost all of the loading time. The check only detects a corrupted file; it is **optional**.
   AGT already has the flags `AGT_CONFIG_NO_WRAPCRC` / `AGT_CONFIG_NO_UNWRAPCRC` (used by
   `examples/parallax/Makefile`), honoured by `load_asset` for packed files, but the three
   loaders above ignored `AGT_CONFIG_NO_UNWRAPCRC` for plain files. Remedy: wrap their
   `if (!packed_flag) { …gen_crc… }` block in `#if !defined(AGT_CONFIG_NO_UNWRAPCRC)` (6 added
   lines, default behaviour unchanged) and add `-DAGT_CONFIG_NO_UNWRAPCRC` to the project's
   compiler flags. Keep it on while developing the asset pipeline (it catches truncated copies),
   switch it off for the release build.
   Measured in Hatari 2.4.1 (STE 4 MB, TOS 1.62, GEMDOS drive, `--fast-forward`, VBL counter,
   boot included): program ready after **63.6 s** of emulated time with the check, **9.8 s**
   without. Confirmed on a real STE by the user (start-up "very fast"; no timing recorded).
   Packing the files (`pack.sh … lz77`) is the other route but adds decompression time, and
   the packed file's own CRC is then checked at read.
   The AGT sources were read for this (`agtsys/spritesheet.cpp`, `compress.cpp`); the effect
   of the patch on other loaders (`worldmap`, `pcs`) was not examined.
