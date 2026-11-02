# 04 — Testing: headless Hatari, measurements, real machine

## Test bench

```sh
python3 tools/hatari_run.py --prg build/HELLO.TOS --tos "tos/TOS v1.04 (1989)(Atari Corp)(Mega ST)(FR)[Rainbow TOS].img" \
    --machine st --mem 512 --monitor rgb --out out/stf 20
python3 tools/hatari_run.py --disk build/hello.st --tos "tos/TOS v1.62 (1990)(Atari Corp)(STE)(FR)[STE TOS, Rev 2].img" \
    --machine ste --key space@10 --out out/ste 15 25
```

`scripts/smoke-test.sh` runs the full matrix:

| Machine | TOS | Hatari mode | Memory | Monitor |
|---|---|---|---|---|
| STF | 1.04 | `st` | 512 KB | rgb |
| STE | 1.62 | `ste` | 1024 KB | rgb |
| Mega STE | 2.06 | `megaste` | 4096 KB | rgb |
| Falcon | 4.04 | `falcon` | 4096 KB | vga |

The automatic criterion: in the screenshot, the first 60 rows contain ≥ 200 dark pixels (the
text) and rows 120–400 contain ≤ 50 (the screen is not a GEM desktop). Each screenshot should
also be looked at by eye the first time.

ROMs are searched in `tos/` by name pattern (1.04, 1.62, 2.06, 4.04 in the file name, e.g.
`TOS v1.04 (1989)(…)[Rainbow TOS].img`); `hatari_run.py` takes an explicit path via `--tos`.

## How `hatari_run.py` works

1. Starts `Xvfb :99` (virtual screen), `SDL_AUDIODRIVER=dummy`.
2. Launches `hatari` with `--control-socket`.
3. Waits for TOS to boot (`--boot-timeout`); screenshot times are the positional arguments, in
   seconds (`15 25` by default), and `--out` is a **folder**.
4. Sends keys with `xdotool` (`--key KEY@SECONDS`).
5. Requests a screenshot through the socket (`hatari-shortcut screenshot`).
6. Shuts down cleanly.

Variant without socket: `--cmd-fifo` to send debugger commands.

If you write your own launcher script, run it under `timeout` (e.g. `timeout 60 ./run.sh …`):
Hatari can crash at start-up (seen once, Hatari 2.4.1, not reproduced on the next run) and a
loop waiting for screenshots then never ends. `hatari_run.py` stops by itself
(`--boot-timeout`).

## Simulating joysticks

Hatari can emulate every joystick on the keyboard (`nJoystickMode = 2` in its configuration).
`tools/hatari-joysticks.cfg` gives each one its own keys (up, down, left, right, fire):

| Hatari joystick | Port | Keys |
|---|---|---|
| 0 | ST port 0 (mouse port) | `w s a d` + `q` |
| 1 | ST port 1 | `i k j l` + `u` |
| 2 | STE/Falcon extended port A (Jaguar pad, fire = button A) | `t g f h` + `r` |
| 3 | STE/Falcon extended port B | arrows + `Return` |
| 4 | parallel-port adapter, joystick 3 (D4–D7 + BUSY) | `1 2 3 4` + `5` |
| 5 | parallel-port adapter, joystick 4 (D0–D3 + STROBE) | `6 7 8 9` + `0` |

```sh
tools/hatari_run.py --prg JOYTEST.TOS --tos tos/etos512uk.img --machine ste \
    --extra "--configfile tools/hatari-joysticks.cfg" \
    --down h@20 --down r@20 --up h@26 --up r@26 --out out/j 22 28
```

- The keys must go through the X server (`xdotool`): keys sent through the control socket or
  the command FIFO (`hatari-event keydown …`) reach the IKBD as keyboard keys and **bypass
  the joystick emulation**.
- The keys given to joysticks no longer reach the ST as keyboard keys: when the program
  also needs them (menus, navigation), use a second configuration without joysticks (see
  "Practical details" below).
- `--down`/`--up` hold a key between two times (a direction "held" when the screenshot is
  taken); `--key` is a short tap.
- Verified (Hatari 2.4.1, EmuTOS 1.3, Nov 2026) with JOYTEST: all six joysticks above react.
- With no joystick emulated on the parallel port, Hatari reads the 8 data lines as 0, i.e.
  "everything pressed" (lines are active low): a program decoding them shows incoherent
  directions. That is normal.

## Without TOS ROMs: EmuTOS

When the user's ROMs are not available (fresh cloud session), EmuTOS (free, GPL) boots in
Hatari on every machine:

```sh
curl -sSL -o emutos.zip https://sourceforge.net/projects/emutos/files/emutos/1.3/emutos-512k-1.3.zip/download
unzip -q emutos.zip -d tos/       # tos/emutos-512k-1.3/etos512uk.img, etos512fr.img, …
```

- The 512 KB images work for ST, STE, Mega STE, TT and Falcon (one image per keyboard
  language). Downloaded from a Claude Code cloud session in Nov 2026.
- EmuTOS sets the `_MCH` cookie for the emulated machine: with JOYTEST, the STE and Falcon
  were detected as having extended joystick ports, the STF and Mega STE were not (Hatari 2.4.1).
- A program started with `--auto` is on screen about 8 s after start-up on STE (JOYTEST;
  about 12 s with a real TOS 1.04 on STF).
- Avoid the US image (`etos512us.img`) for anything time-related: it runs at 60 Hz (see
  above). Use it neither for frame-rate measurements nor as a proof of behaviour on a real TOS
  (pitfall: EmuTOS hides some real-TOS bugs, `docs/06`). Always write "verified in Hatari with
  EmuTOS", not "with TOS".

## Debugger: `--parse` scripts

Hatari reads a file of debugger commands at start-up (`--parse script.ini`). Useful for:

- a breakpoint on the VBL, counting frames and deducing the throughput;
- `:trace` to follow execution;
- dumping memory to a file (`savebin` / `dump`) at a given frame and comparing it.

To find a routine by name, assemble **without** `-nosym` and read the symbol table, or use
the `-L` listing.

### Debugger recipes (Hatari 2.4.1)

- **Breakpoint that does not stop the emulation**:
  `b pc = $1934 :trace :quiet :file hit.dbg` runs the commands of `hit.dbg` at every hit and
  carries on. Without `:trace`, the emulation stops at the first hit.
- **Conditions**: `b pc = $1934 && HBL = 253 && LineCycles > 80 :trace …`. Symbolic
  expressions such as `TEXT+$114` are not accepted: compute the absolute address.
- **Beam position**: `e HBL` and `e LineCycles` (line counted from the top of the frame, cycle
  within the 512-cycle line on a 50 Hz ST). The displayed line is roughly `HBL - 63`.
- **What happened just before**: `history on` once, then `history 40` in the hit file prints
  the last 40 instructions, including any interrupt handler that ran in between. This is how
  a delayed raster interrupt was traced to the keyboard handler (case study IK+, docs/07).
- **Stack at interrupt entry**: `m a7 8` shows the stacked SR and return address (who was
  interrupted, and at which mask level).
- **Who writes where**: `b ($ADR).w ! ($ADR).w` stops when the value changes.
- **Prove a memory area is free**: fill it with a pattern at start-up (`loadbin` at the first
  breakpoint on the entry point), play for several minutes on every machine, then read it
  back (`savebin`) and compare. Disassembly alone only proves that nothing *visible* uses it.

### Driving Hatari through the command fifo

`--cmd-fifo FILE` accepts one command per line, at any time:

- `hatari-shortcut screenshot`, `hatari-shortcut savemem`, `hatari-shortcut quit`,
  `hatari-shortcut warmreset`;
- `hatari-event keydown 0x01` / `hatari-event keyup 0x01`: ST scancodes (`0x01` = Esc; a bare
  `1` would be the scancode of the digit 1 key). These events bypass the joystick
  emulation: to move a joystick, send X11 keys with `xdotool` to a real (Xvfb) window
  (**Hatari ignores the joystick keys while Shift is held**). There is **no
  `hatari-event keyrelease`** (Hatari only logs an error); `keypress` = down then up;
- `hatari-option --fast-forward yes`: fast forward (AltGr + X). Emulated time (VBLs, cycles)
  does not change, so measurements stay valid;
- `hatari-debug <command>`: any debugger command while running, e.g.
  `hatari-debug m $11f2 9` (read) or `hatari-debug w $11f2 $09 $50` (write, to force a game
  state); the output goes to Hatari's log.

A small driver reading a file of `seconds command` lines makes scenarios reproducible.

Pitfalls:

- keys and commands are sent at fixed **real** times: two Hatari instances running at once
  slow each other down and the keys land too early; run trials one after the other;
- stop Hatari by PID (`kill $(pgrep -x hatari)`), never with `pkill -f pattern`: the shell
  running the command line also matches the pattern and kills itself.

### Saved machine state

Reach the interesting moment once in real time, save, then start every trial from there:

- save: `hatari-path memsave /path/f.sav` then `hatari-shortcut savemem`;
- restore: `--memstate /path/f.sav`, usually with fast forward;
- **restoring clears the breakpoints** (`--parse` breakpoints are lost): set them afterwards
  through the fifo;
- the state contains the program: one state per build.

Example: a 1 min 40 s scenario replayed in 22 s.

## Measuring a frame rate

- Count VBLs (memory counter or breakpoint) over N seconds of emulated time.
- **Real French TOS runs at 50 Hz; US EmuTOS at 60 Hz** (VBL = 133,000 cycles versus
  160,000): frame-rate measurements made with a US EmuTOS are wrong for a European audience.
  Measure with the real TOS.
- One frame per VBL = 50 fps; if the code does not fit in the frame, the rate drops to 25 fps,
  16.7 fps… (multiples of the frame).

## Following GEMDOS calls: `--trace gemdos`

`--extra "--trace gemdos"` makes Hatari print every GEMDOS call with its arguments and the
calling address (in `<out>/hatari.log` with `hatari_run.py`):

```
GEMDOS 0x4B Pexec(0, "A:\GAME\GAME.PRG", [0]"", 0x0) at PC 0xAC5E
GEMDOS 0x4A Mshrink(0xACEC, 0x1A37C) at PC 0xB07A
GEMDOS 0x48 Malloc(0x4BBF0) at PC 0x105F6
```

The quickest way to settle a "not enough memory" or "file not found" problem: which program
was started, where its basepage is, how much it keeps and asks for, which file it opens with
which path. Run it with `--mem 512` and each TOS (1.00 and 1.04 do not leave the same memory
free, see `docs/05`).

## Measuring raster timing

When colours flicker on one machine and not another, measure *when* the palette is written
rather than guessing:

1. breakpoint on the instruction just after the first palette write of the suspect raster
   routine, with `e HBL` and `e LineCycles` in the hit file;
2. a few thousand frames on each machine (same build, same scenario);
3. histogram of `(HBL, LineCycles)`.

On a 50 Hz ST, display ends near cycle 376 of the line; a write between ~376 and the end of
the line is invisible (border), a write in the next line's first ~300 cycles shows as a
broken line. Real case (IK+): STF, every write in the border; STE, 12% of writes in the middle
of the next line → `history` showed the keyboard ACIA handler every time (docs/05, MFP).

Frame rate of a game whose frame is "one step": count screen swaps (breakpoint on the swap
routine) per state of the game, not VBLs.

## Hatari is more permissive than the real machine

Observed cases:

- bit 7 of PSG register 7 (YM2149);
- access to the parallel port;
- extended joystick ports `$FF9200/$FF9202` (bus error on real STF/Mega STE);
- Mega STE cache (software must explicitly switch it off to run "pure" 8 MHz: `$FF8E21 = 0`);
- the **reset vector**: a program that installs its own `resvector` routine froze the real
  machine on RESET, while Hatari (even with the real TOS) rebooted normally. A RESET test is a
  real-machine test.
- PSG registers: Hatari returns the value as it was when the register was **selected**
  (`$FF8800`); read twice (select, read, select again, read) to get the current value;
- on a real STE, a read of `$FF9202` makes the **next** read of `$FF9200` return `$FFFF`
  (buttons lost) until the next select; Hatari does not do it (details: `docs/05`);
- Falcon in Hatari: `$FF9200` reads `$BFFF` with nothing pressed (bit 14 low), `$FFFF` on STE;
  the button bits (0–3) are not affected. Cause not known, not checked on a real Falcon;
- interrupts delayed by blitter bus cycles: Hatari does not reproduce every case;
- Falcon: Hatari does not show mid-screen palette changes, so raster colours look wrong there.

A test that passes in Hatari **does not prove** it works on a machine; write
"verified in Hatari 2.4.1 with TOS x.xx", not "works on Mega STE".

## Hatari boot constraints

- Hatari **refuses TOS 1.62 in ST mode** (it demands an STE); TOS 2.06 is accepted in ST mode.
- Real TOS 1.04: 196,608-byte ROM starting with `60 2E 01 04 00 FC 00 30`.
- The supplied TOS 1.62 file is 262,145 bytes (one byte too many; ignored or truncated).
- TOS 2.06 uses $5840 bytes more RAM than 1.04.
- Falcon with TOS 4.04: `--mmu on`. TOS 4 enables the MMU (root table at `$700`); without
  `--mmu on`, Hatari ignores it and programs that overwrite low memory behave differently.

## Floppy images

- Geometry: 720 KB = 80 tracks × 2 sides × 9 sectors, 2 sectors/cluster, 112 root entries,
  media `$F9`. "820 KB" variant: 82 tracks × 10 sectors.
- Create: `tools/mkst.py` (dependency-free), or `mtools`: `mcopy -i disk.st -bspm …`.
- "Hidden sectors" warning on Atari partitions: `MTOOLS_SKIP_CHECK=1`.
- `AUTO` folder: the `.PRG` files in it start by themselves at boot.
- Check: `fsck.fat -n disk.st`, `mdir -i disk.st ::`.
- From a folder, with the tool shipped with Hatari: `(cd folder && zip -qr ../d.zip .)` then
  `zip2st d.zip d.st` (it needs `mtools`). `mkst.py` does the same without dependencies.
- `--fastfdc yes` speeds up floppy loading in Hatari (not the program itself).

## Screenshots and colours

Hatari's screenshots have 4-bit components scaled to 8 bits (multiples of 17), whereas an
ST colour has 3 bits per component. Never rebuild a palette from a screenshot without checking
the conversion on known colours: a reconstructed title screen once had a slightly wrong
palette for that reason. Convert with `round(c * 7 / 255)` for an ST target and compare with
the values actually written to `$FF8240` (debugger: `m $ff8240`).

## Real machine

The emulator does not replace the machine. Proven protocol:

1. Deliver a **zip** whose folder is copied as is to the Atari's SD card / DOS partition
   (without rebuilding a path).
2. Attach `TO_TEST.TXT`: **plain ASCII text without accents**, readable with the Atari
   desktop's viewer, saying: version to test, what to launch, what to observe, which keys to
   press, which result to expect. Texts distributed with a program (README in French…) may
   keep their accents if converted to the ST character set: `tools/txt2st.py` (CP437 subset,
   CR LF, 78 columns).
3. Number the executables (0.0.1, 0.0.2…) and display the version on screen.
4. Ask the user to report: machine model, TOS version, result per point of the list.
5. Do **not** conclude on a cause until the hardware trial has provided data; write
   "I don't see the cause" if that is the case.
6. **Diagnostic variants** when a fault shows only on the machine: build (outside the
   repository) variants that each remove one suspect, e.g. "STE without blitter" and "STE
   without DMA sound", with the variant name on screen. If the fault survives in all of them,
   the suspects are cleared and the search moves on (IK+: the cause was the keyboard
   interrupt, found afterwards by measurement).
7. Number the trials (trial 7, 8, 9…) in the zip name and in `TO_TEST.TXT`, and ask what
   changed compared with the previous one.

### Real-machine details learned

- Overscan intros on Mega STE: processor at 8 MHz, cache off (`$FF8E21 = 0`).
- Falcon: no overscan.
- Blitter in shared mode: after a pause, bit 7 reads 0; use the line counter `$FF8A38`.
- IKBD mouse: re-enable it (command `$08`) on exit, otherwise the desktop has no mouse.
- AZERTY keyboard: compare **scancodes**.

## Automation learned on a long project (Bubble Bobble, 8 players)

These techniques made hundreds of headless runs practical. All verified with Hatari 2.4.1.

Complements to the fifo, saved-state and debugger sections above:

- **Key scripts**: one line per second (`12 tap space`, `15 down Left`, `16 up Left`,
  `20 cmd hatari-debug ...`) and one screenshot per second make every run reviewable
  afterwards.
- **Fast forward after the keys**: send the keys first (fixed wall-clock times), then switch
  to fast forward: 300 emulated seconds in about 1 min 45.
- **End a long run from the debugger**: `b VBL = N :once :file quit.cmd`, the file containing
  `quit`.
- **Conditions on memory**: `b pc = $DC7B6 && ($D0272).l > $7C8 :trace`; the log says how many
  times it matched, a cheap way to know whether a routine is reached with a given state.
- `b pc = ($8).l` stops on a bus error.
- **Periodic dumps**: a `--parse` file of `b VBL = N :once :quiet :file dump.cmd` lines, each
  `dump.cmd` containing `savebin out/xN.bin $ADR LEN`; analyse the files with Python. Dump at
  a well-defined point of the frame (end of the main loop): data read mid-frame may be
  half-updated.

### Measuring how much memory is really used ("pattern" method)

The pattern method above (`loadbin` a pattern, play, `savebin` and compare) also gives the
real depth of a stack: the lowest modified byte. Two lessons:

- run it under **each TOS version** concerned;
- if writing the pattern **crashes** the system, the area was in use (in one case: the
  process basepage, still used by GEMDOS — see docs/05).

### Simulating the user's machine

- **Fake resident**: a 100-byte program in `AUTO` that keeps memory with `Ptermres` and does
  what the user's drivers do (hooks a vector with or without XBRA, links a GEMDOS buffer in
  a given place…). It reproduces "works here, fails on my Mega STE with HD Driver" cases that
  Hatari's GEMDOS hard-disk emulation cannot show (it uses no BIOS buffers, no driver).
- **Basepage probe**: a program in `AUTO` that prints its own basepage address
  (`4(sp)`) tells how much low memory each TOS keeps (see docs/05).
- **Floppy boot vs GEMDOS drive**: to exercise the real BIOS/GEMDOS path (buffers, writes),
  boot from a floppy image; the emulated GEMDOS drive bypasses them.

### Practical details

- Send keys with `keydown`/`keyup` and ~0.15 s between them; a bare `keypress` can be too short.
- Joystick emulation on the keyboard and keyboard navigation conflict: keep two Hatari
  configuration files (joysticks on keys / arrows as keyboard).
- The Help key could not be injected reliably with xdotool (`Help`, `Prior`): reach the same
  function another way in tests.
- Parallel runs are possible if each Hatari has its own Xvfb display and no keys depend on
  wall-clock timing (computer-only games); otherwise run trials one after the other.
- **Hatari writes back into floppy images** (a program saving its settings…): test on a
  copy, never on the image you deliver.
- Review dozens of screenshots at once: paste reduced copies into one grid image with Pillow.
- Count frames rather than seconds: the VBL counter (`e VBL` / `b VBL = N`) is exact even
  in fast forward.
