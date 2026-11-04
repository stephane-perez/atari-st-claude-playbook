# 06 — Catalogue of pitfalls met

Each entry: symptom → cause → remedy. Grouped by area.

## Tools and environment

| Symptom | Cause | Remedy |
|---|---|---|
| "Hatari not found / not installable" | `apt-get update` never run | `apt-get update` then reinstall |
| `curl`/`wget` refused | allowlisted network | attach the file to the conversation, or a script run on the user's side |
| Private GitHub repository unreachable | no authentication | provide a zip; the user pushes |
| Files and tools gone | temporary workspace recycled | keep everything in the repository; `setup-dev.sh`; state file |
| Unicorn crashes or behaves like a 68020 | CPU model not set | `ctl_set_cpu_model(UC_CPU_M68K_M68000)` **before** `mem_map` |
| Capstone accepts 68020 in 68000 mode | addressing modes not filtered | cross-check with a second disassembler |
| Pillow: `getdata` warning | deprecated API | use `histogram()` |
| Home-made Hatari script never ends | Hatari crashed at start-up | run it under `timeout` |
| `./script.sh`: permission denied in a fresh clone | committed without the executable bit | `git update-index --chmod=+x script.sh` |
| `git push` of a tag refused in a cloud session | the session's git proxy does not push tags | give the user the `git tag … && git push origin …` command |
| No ROM in the session | ROMs are not in git | EmuTOS (`docs/04`), stated as such in the report |

## Emulation with Unicorn

| Symptom | Cause | Remedy |
|---|---|---|
| `UC_ERR_EXCEPTION` on an `rte` of a routine called by `bsr` | `move.w sr,-(a7)` ... `rte` idiom (restores SR, returns) not executed as a 68000 does | stop on each `rte`, pop SR then PC by hand (`tools/ym_emu.py`) |
| Stack writes at `$FFFFFFxx` after setting A7 | A7 written in user mode (USP), then SR set to supervisor: A7 is the SSP (0) | write SR first, then A7 |
| Accesses to `$FFFF8800` not seen as the YM | absolute short `$8800.w` is sign-extended to 32 bits | map `$FFFF0000-$FFFFFFFF` too, compare on the low 24 bits |
| Emulated player and Hatari disagree only when a sound ends | the player writes nothing when silent: frames without writes | one entry per VBL, "no write" included (`docs/04`) |

## Assembly

| Symptom | Cause | Remedy |
|---|---|---|
| Rebuilt binary differs from the original | vasm optimisations | `-no-opt` |
| `bra.s` out-of-range error after adding code | short branch | `bra.w` |
| "Address error" crash after changing a text | odd length, word at odd address | `even` after any text |
| Short hex > `$7FFF` assembled wrongly | sign extension | `$ffff8240.w` |
| Different relocation table | order/type of references | compare with `prg_info --relocs` |
| Duplicate label / unknown macro | macro defined after use | define macros first |
| Different header flags | `-tos-flags` forgotten | copy the original's flags |
| Test after `move.l x,aN` takes the wrong branch | `movea` does not set the condition codes | go through a data register (`move.l x,d0 / move.l d0,aN`) |
| `divu` gives garbage | `move.w #n,dX` leaves the high word: `divu` divides the 32-bit register | `moveq`/`move.l` before `divu` |
| Local labels "disappear" after inserting a global label | a global label opens a new scope for `.local` labels | use `name equ *` for a return label inside a routine |
| Patch script "worked" but nothing changed | Python `str.replace` silently finds nothing | `assert old in s` before every replacement |

## Emulation and measurement

| Symptom | Cause | Remedy |
|---|---|---|
| Odd "60 Hz" frame rate | US EmuTOS (60 Hz) | measure with a real 50 Hz TOS |
| Hatari refuses TOS 1.62 | "ST" machine | use `--machine ste` |
| "TOS104.IMG" image does not boot like a ROM | it is a RAM-loaded TOS (256-byte relocator) | use the real 192 KB ROM (`60 2E 01 04 00 FC 00 30`) |
| ROM 1.62: size 262,145 | one byte too many | truncate to 262,144 |
| Test OK in Hatari, KO on machine | Hatari more permissive | test on machine; write "verified in the emulator only" |
| Test "passes" while the screen is the GEM desktop | criterion too weak (≥ 2 colours) | criterion on specific content (dark pixels at top, nothing below) |
| Click in headless Hatari has no effect | window focus | `xdotool` after waiting for boot; keys rather than mouse |
| `hatari-event keyrelease` error | the command does not exist | `keydown` / `keyup`, or `keypress` |
| Joystick keys ignored in Hatari | Shift held down | do not hold Shift while driving a joystick |
| RESET OK in Hatari, machine frozen on hardware | program's own `resvector` routine | do not install it; test RESET on the machine |
| Palette rebuilt from a screenshot slightly wrong | 8-bit screenshot components vs 3/4-bit ST colours | convert with `round(c*7/255)`, check on known colours |
| `zip2st` fails | `mtools` missing | `apt-get install mtools` (or `tools/mkst.py`) |
| Key "1" sent through the fifo is not Esc | fifo takes scancodes | Esc = `0x01` |
| Joystick does not move with fifo key events | fifo events bypass joystick emulation | X11 keys with `xdotool` on an Xvfb window (`tools/hatari-joysticks.cfg`) |
| Breakpoints gone after `--memstate` | restoring a state clears them | set them afterwards through the fifo |
| Keys land at the wrong moment | two Hatari instances at once, keys sent at real times | one trial at a time |
| `pkill -f hatari…` kills the script itself | the shell's command line matches | kill by PID |
| Breakpoint stops the emulation | no `:trace` | `:trace :quiet :file cmds.dbg` |
| Falcon: program behaves differently from the machine | MMU enabled by TOS 4 ignored | `--mmu on` |
| Falcon: raster colours wrong in Hatari | mid-screen palette changes not shown | judge on the machine |
| Delivered floppy image modified | Hatari writes back into the image | test on a copy |
| Disk-write bug invisible in Hatari | the GEMDOS hard-disk emulation uses no BIOS buffers and no driver | boot from a floppy image; fake resident simulating the driver |
| Parallel-port joysticks all "pressed" in Hatari | no joystick emulated on the parallel port: lines read 0 | normal; configure Joystick 4/5 |
| PSG register value one step late in Hatari | Hatari returns the value as of the register select | select and read twice |

## Hardware

| Symptom | Cause | Remedy |
|---|---|---|
| Bus error on STF/Mega STE | read of `$FF9200/$FF9202` | test the machine first (`_MCH` cookie) |
| Bus error on STE | ROM read at `$FC0000` | the STE ROM is at `$E00000` |
| No `_MCH` cookie | TOS < 1.06 | absence means "ST" |
| "Can't allocate memory" on 520 ST, fine with 1 MB | GEMDOS margin used up (desktop start, launcher keeping memory, program grown) | `--trace gemdos`; start from AUTO; launcher `Mshrink` before `Pexec` (docs/05) |
| Game refuses to start on Falcon from AUTO ("colour display") | boot video mode kept | launcher switches to ST low (`Setscreen` rez 0) |
| Mega STE treated as an STE (bus error on `$FF9202`) | `_MCH` high word compared only (`$00010010`) | compare the whole value |
| Jaguar pad buttons dead on a real STE, fine in Hatari | `$FF9202` read before `$FF9200` | read `$FF9200` right after the select |
| Parallel-port joysticks dead on a real machine, fine in Hatari | bit 7 of PSG register 7 left at 1 | port B as input before each read |
| Second IKBD joystick ignored | handler reads only the byte named by the header | `joyvec` gets 3 bytes: header, joy 0, joy 1 |
| Registers lost after a `trap` | GEMDOS/BIOS/XBIOS destroy d0–d2/a0–a2 | keep values in d3–d7/a3–a6 |
| Program overwritten on TOS 1.04 | supervisor stack in the bss after `Supexec`, GEMDOS writes below the user stack | do not reuse that area; EmuTOS hides the bug |
| Invalid fixed address under TOS 2.06 | TOS 2.06 uses $5840 more bytes | `Malloc`/`Mshrink` |
| Overscan intro fails on Mega STE | 16 MHz + cache | 8 MHz, cache off: `$FF8E21 = 0` |
| Overscan on Falcon | not supported | do not target the Falcon |
| Blitter pause: bit 7 reads 0 | shared mode | line counter `$FF8A38` |
| Raster colours change mid-line, a flickering line | an MFP handler (keyboard ACIA) running at mask 6 delays Timer B | `move.w #$2500,sr` first in the ACIA handler (AEI mode); measure with `HBL`/`LineCycles` |
| Raster colours late on STE only | blitter burst during the raster interrupt | do not start the blitter 1–2 lines before Timer B; pause it in the raster handler |
| First key lost after a long drawing | ACIA overrun by an IKBD packet | drain the ACIA until silence, skip packets by length |
| STE pad buttons read `$FFFF` | `$FF9202` read before `$FF9200` | buttons first |
| `rte` jumps anywhere on Falcon | hand-built exception frame without format word | test `_longframe`, push a format word |
| Reset reruns the program | `resvalid`/`resvector` set by the program | clear `$426` |
| Music and game too fast on Falcon VGA | not 50 Hz | use an RGB monitor; document it |
| False fire on parallel-port joystick | BUSY line floating | pull-up on BUSY |
| No mouse back at the desktop | IKBD left disabled | send `$08` again |
| Wrong keys on a French keyboard | AZERTY | compare scancodes |
| "Not enough memory" on STE 512 KB, fine on STF 512 KB | TOS 1.62 keeps 68 bytes more low memory than 1.04 | measure the basepage per TOS; keep a margin |
| Crash when a stack/copy reaches the program's basepage | GEMDOS still uses it | keep the 256 bytes of the basepage out of any reserved area |
| Settings cannot be saved with a hard-disk driver | driver's GEMDOS buffers inside memory the program overwrites | check/move the BCBs (`$4B2`/`$4B6`), docs/05 |
| Menu moves by itself | mouse on port 0 seen as a joystick | menus read port 1 and keys only |
| Two keys held at once not seen | TOS reports presses only | own `ikbdsys` with a key-state table |
| PSG, parallel port, extended joystick ports: OK under Hatari only | emulator tolerances | test on a machine |

## Files and formats

| Symptom | Cause | Remedy |
|---|---|---|
| "Floppy image" that is not one | packed PRG (Pack-Ice, Atomik) | `prg_info.py` |
| Game floppy shows an empty directory or a bogus BPB | track loader, no files | `tools/stx.py --dump`, boot sector, file table, `--trace fdc` (docs/03 §2b) |
| Depacked picture garbled although the depacker is verified | the game transforms the data again (bit transposition) | find the routine that uses the data, compare with a Hatari screenshot |
| Pack-Ice file decoded as garbage or error | 2.3x and 2.40 differ; `Ice!` vs `ICE!` header, some depackers treat both as 2.40 | `unice.py --variant 2.3/2.4` |
| Rebuilt level colours wrong, pictures right | tile-set palette stored as linear 0..15 values, not in the STE order | compare index -> colour with a Hatari screenshot |
| Label of a `movem.l d16(pc)` table 2 bytes off | Capstone prints the target from the register mask | `fix_capstone()` in `m68k_recdis.py` |
| Data table of a labels file disassembled as code | every name taken as a code entry | prefix data names `tbl_`, `var_`, `data_`, `str_` |
| Recursive disassembly finds "code" in data | pointer scan on a table of values | reject candidates starting with `ori` (`$00xx`), check by eye |
| File table of a loader full of zeros | filled at run time from another sector | trace the FDC reads in Hatari |
| A TOS ROM file of 262,145 bytes | one extra trailing byte | keep the first 256 KB (check the header: `$602E`, version, base) |
| mtools: hidden sectors warning | Atari partition | `MTOOLS_SKIP_CHECK=1` |
| `mtools` does not copy as is | text vs binary | `mcopy -bspm` |
| Text file unreadable on the Atari | UTF-8 accents | plain ASCII for `TO_TEST.TXT`, or `tools/txt2st.py` |
| Picture uses too much memory once embedded | uncompressed IFF ILBM (32,000-byte BODY) | `tools/packiff.py` (ByteRun1), if the decoder reads it |
| Volume name refused by `mkst.py` | 8.3 check on the label | the label is built without going through `name83` (fixed) |

## Method and communication

| Mistake | Consequence | Rule |
|---|---|---|
| Announcing a cause not demonstrated | the user loses time | say "I don't see the cause" |
| Concluding after a single attempt | tool wrongly ruled out | two attempts and a diagnosis of the error |
| Presenting an emulator result as certain on hardware | disappointing hardware trial | state the verification environment |
| Delivering an executable without a version number | confusion between trials | 0.0.1, 0.0.2… |
| Modifying before having an identical source | impossible to know what changed | `cmp` first |
| Extending a game from 3 to 4 players, the new slot misbehaves | functions written for a computer-only slot (never reset, never blinked) | re-check every touched function for the new slot |
| Calling a routine of a compiled program corrupts registers | it modifies d0-d7 without saving them | save around the call |
| Fixing what you cannot reproduce | the fix may target the wrong cause | reproduce in Hatari first; if it does not reproduce, say so and ask for exact steps |
| Guessing the cause of a hardware-only fault | trials wasted | diagnostic variants, then measurement |
| Checksums computed without the original input | they may be wrong | label them "to re-check" and re-check as soon as the original is available |
