#!/usr/bin/env python3
"""ym_emu.py: runs a music player (SNDH file or raw player) in Unicorn as a
68000 and records the YM2149 registers after each 50 Hz play call.

usage:
  ym_emu.py TUNE.SNDH [--sub N] [--frames F] [--out REGS] [--tos TOS.IMG]
  ym_emu.py PLAYER.BIN --init OFF --play OFF [--d0 N] ...      (raw player)
  SNDH: init at +0 with d0 = sub-tune (1..n), play at +8 (SNDH convention).
  Raw player: offsets of its entry points; --d0 = value passed to init.
  --frames  number of play calls (default: until 3 s of silence, max 30 min)
  --out     FRAMES x 14 bytes: registers 0..13 after each call (register 13 =
            $FF when not written during that frame, as in YM files)
  --tos     fill $0..$3F as on a real ST running this TOS (first ROM bytes,
            vectors pointing into the ROM): some players read there through a
            null pointer; default zeros

Emulated machine: the code at $40000, supervisor mode (SR then A7 set, in this
order: A7 is the SSP), 50 Hz in $FF820A, YM at $FF8800/$FF8802 and through
$FFFF88xx (absolute short addresses are sign-extended), reading $FF8800
returns the selected register. rte is executed as on a 68000 (pop SR, then
PC): Unicorn raises an exception on the move.w sr,-(a7) ... rte idiom.
Accesses outside the player, its stack and the I/O used are reported: a player
that is not self-contained shows up there.
Verified (Nov 2026): identical, frame by frame, to the YM writes traced in
Hatari 2.4.1 (tools/sndh_record.py) on a game's 9 tunes and 32 effects, and on
examples/sndh/beep.s.
"""
import argparse
import struct
import sys

from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_READ, UC_HOOK_CODE
from unicorn.m68k_const import (UC_CPU_M68K_M68000, UC_M68K_REG_A7, UC_M68K_REG_D0,
                                UC_M68K_REG_SR, UC_M68K_REG_PC)

BASE, RET, SP = 0x40000, 0x1000, 0x30000


def tos_lowmem(tos_path):
    """$0..$3F as seen on a real ST running this TOS: $0-$7 = the first 8 ROM bytes,
    $8-$3F = exception vectors; TOS points them into its ROM (here: the ROM base,
    so only the high word is exact)."""
    rom = open(tos_path, "rb").read()
    base = struct.unpack(">I", rom[8:12])[0]           # os_base: $FC0000 / $E00000
    return rom[:8] + struct.pack(">I", base) * 14


def is_sndh(data):
    return data[12:16] == b"SNDH"


def sndh_subtunes(data):
    i = data.find(b"##", 12, 0x200)
    return int(data[i + 2:i + 4]) if i > 0 and data[i + 2:i + 4].isdigit() else 1


class Player:
    def __init__(self, code, lowmem=None):
        self.code = code
        uc = self.uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        uc.ctl_set_cpu_model(UC_CPU_M68K_M68000)      # before mem_map (docs/06)
        uc.mem_map(0, 0x100000)
        uc.mem_map(0xFF0000, 0x10000)                 # I/O page, 24-bit address
        uc.mem_map(0xFFFF0000, 0x10000)               # same page through $xxxx.w
        uc.mem_write(BASE, code)
        if lowmem:
            uc.mem_write(0, lowmem)
        uc.mem_write(RET, b"\x4e\x71")
        for io in (0xFF820A, 0xFFFF820A):
            uc.mem_write(io, b"\x02")                 # 50 Hz
        self.sel = 0
        self.regs = [0] * 16
        self.r13 = False
        self.wrote = False
        self.outside = set()
        self.rte_at = None
        uc.hook_add(UC_HOOK_MEM_WRITE, self._w)
        uc.hook_add(UC_HOOK_MEM_READ, self._r)
        for off in range(0, len(code) - 1, 2):
            if code[off:off + 2] == b"\x4e\x73":
                uc.hook_add(UC_HOOK_CODE, self._rte, begin=BASE + off, end=BASE + off)

    def _rte(self, uc, address, size, user):
        if uc.mem_read(address, 2) == b"\x4e\x73":
            self.rte_at = address
            uc.emu_stop()                             # executed by call()

    def _ym(self, addr, size, value):
        for i in range(size):
            a = addr + i
            b = (value >> (8 * (size - 1 - i))) & 0xFF
            if (a & ~0xFC) == 0xFF8800:               # select (mirrored every 4 bytes)
                self.sel = b & 0x0F
            elif (a & ~0xFC) == 0xFF8802:
                self.regs[self.sel] = b
                self.wrote = True
                if self.sel == 13:
                    self.r13 = True

    def _w(self, uc, access, addr, size, value, user):
        addr &= 0xFFFFFF
        if 0xFF8800 <= addr < 0xFF8900:
            self._ym(addr, size, value)
        elif not (BASE <= addr < BASE + len(self.code) or SP - 0x2000 <= addr < SP):
            self.outside.add(("W", addr))

    def _r(self, uc, access, addr, size, value, user):
        full = addr
        addr &= 0xFFFFFF
        if 0xFF8800 <= addr < 0xFF8900 and (addr & 3) == 0:
            uc.mem_write(full, bytes([self.regs[self.sel]]))
        if addr >= 0xFF0000:
            if not (0xFF8800 <= addr < 0xFF8900 or addr == 0xFF820A):
                self.outside.add(("R", addr))
        elif not (BASE <= addr < BASE + len(self.code) or SP - 0x2000 <= addr < SP or addr == RET):
            self.outside.add(("R", addr))

    def call(self, off, d0=0):
        uc = self.uc
        uc.reg_write(UC_M68K_REG_SR, 0x2300)          # supervisor first: A7 = SSP
        uc.mem_write(SP - 4, struct.pack(">I", RET))
        uc.reg_write(UC_M68K_REG_A7, SP - 4)
        uc.reg_write(UC_M68K_REG_D0, d0)
        start = BASE + off
        for _ in range(100000):
            self.rte_at = None
            uc.emu_start(start, RET, count=5_000_000)
            if self.rte_at is None:
                if uc.reg_read(UC_M68K_REG_PC) != RET:
                    raise RuntimeError("player stopped at $%x" % uc.reg_read(UC_M68K_REG_PC))
                return
            sp = uc.reg_read(UC_M68K_REG_A7)          # 68000 rte: pop SR, then PC
            sr, pc = struct.unpack(">HI", uc.mem_read(sp, 6))
            uc.reg_write(UC_M68K_REG_A7, sp + 6)
            uc.reg_write(UC_M68K_REG_SR, sr)
            start = pc
        raise RuntimeError("too many rte")

    def frame(self, play):
        """one play call: registers (bytes) if the player wrote to the YM, else None"""
        self.wrote = self.r13 = False
        self.call(play)
        if not self.wrote:
            return None
        r = self.regs[:14]
        r[13] = r[13] if self.r13 else 0xFF
        return bytes(r)


def run(code, init, play, d0, frames=None, lowmem=None, silence=150, limit=90000):
    """init then play; returns (list of frames: bytes or None, player).
    Without frames: stops after `silence` frames with all volumes at 0 (or no write)."""
    p = Player(code, lowmem)
    p.call(init, d0)
    out, quiet, last = [], 0, None
    n = frames or limit
    for _ in range(n):
        f = p.frame(play)
        out.append(f)
        if f is not None:
            last = f
        loud = last is not None and any(v & 0x1F for v in last[8:11])
        quiet = 0 if loud else quiet + 1
        if frames is None and quiet >= silence and len(out) > silence:
            out = out[:len(out) - silence]
            break
    return out, p


def entry_points(data, a):
    if a.init is not None:
        return a.init, a.play, a.d0
    if not is_sndh(data):
        sys.exit("not an SNDH file: give --init and --play")
    return 0, 8, a.sub


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tune")
    ap.add_argument("--sub", type=int, default=1, help="SNDH sub-tune (1..n)")
    ap.add_argument("--init", type=lambda x: int(x, 0))
    ap.add_argument("--play", type=lambda x: int(x, 0))
    ap.add_argument("--d0", type=int, default=0)
    ap.add_argument("--frames", type=int)
    ap.add_argument("--out")
    ap.add_argument("--tos")
    a = ap.parse_args()
    data = open(a.tune, "rb").read()
    init, play, d0 = entry_points(data, a)
    frames, p = run(data, init, play, d0, a.frames, tos_lowmem(a.tos) if a.tos else None)
    if a.out:
        blob = bytearray()
        last = bytes(13) + b"\xff"
        for f in frames:
            last = f if f is not None else last[:13] + b"\xff"
            blob += last
        open(a.out, "wb").write(blob)
    writes = sum(1 for f in frames if f is not None)
    print("%s: %d frames (%.1f s), %d with YM writes, outside accesses: %s"
          % (a.tune, len(frames), len(frames) / 50, writes,
             ", ".join("%s $%x" % x for x in sorted(p.outside)[:8]) or "none"))


if __name__ == "__main__":
    main()
