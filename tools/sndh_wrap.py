#!/usr/bin/env python3
"""sndh_wrap.py: wraps a raw music player (position-independent code + data,
with known entry points) as an SNDH file, without modifying the player.

usage: sndh_wrap.py PLAYER.BIN OUT.SNDH --init OFF --play OFF [--exit OFF]
                    --subtunes N [--zero-based] [--title T] [--composer C]
                    [--ripper R] [--year Y] [--timer TC50]
  --init/--play/--exit   offsets of the player's entry points (exit optional:
                         without it, exit only silences the 3 YM volumes)
  --zero-based           the player's init expects 0..n-1 in d0 (SNDH gives 1..n):
                         a subq.w #1,d0 is put before the jump
  --timer                SNDH replay tag, TC50 (VBL 50 Hz) by default

Layout: +0 bra init wrapper, +4 bra exit, +8 bra play, "SNDH" tags ... "HDNS",
the wrapper, then the player bytes unchanged (checked at the end).
Find the entry points by reading the player and the program that calls it
(docs/03: what it calls with jsr, what d0 holds). Check the result with
tools/ym_emu.py, then in Hatari with tools/sndh_record.py.
"""
import argparse
import struct
import sys


def bra(src, dst):
    d = dst - (src + 2)
    if not -32768 <= d <= 32767:
        raise ValueError("branch too far")
    return struct.pack(">Hh", 0x6000, d)


def tags(a):
    t = b"SNDH"
    for key, val in (("TITL", a.title), ("COMM", a.composer), ("RIPP", a.ripper)):
        if val:
            t += key.encode() + val.encode("ascii") + b"\0"
    if a.year:
        t += b"YEAR" + a.year.encode("ascii") + b"\0"
    t += b"##%02d" % a.subtunes
    t += a.timer.encode("ascii")
    t += b"HDNS"
    if len(t) % 2:
        t += b"\0"
    return t


def wrap(player, a):
    t = tags(a)
    init_w = 12 + len(t)
    # init wrapper: [subq.w #1,d0] bra player+init ; exit wrapper if no exit offset
    wrap_code = b""
    if a.zero_based:
        wrap_code += struct.pack(">H", 0x5340)                  # subq.w #1,d0
    exit_w = None
    pending = []          # branches resolved once the player position is known
    wrap_code += b"\0\0\0\0"                                    # bra.w to init, patched
    pending.append((init_w + len(wrap_code) - 4, a.init))
    if a.exit is None:
        exit_w = init_w + len(wrap_code)
        # lea $ffff8800.w,a0 ; move.l #$08000000,(a0) ; move.l #$09000000,(a0) ;
        # move.l #$0a000000,(a0) ; rts   (register then value, as movep-free writes)
        wrap_code += bytes.fromhex("41f88800" "20bc08000000" "20bc09000000" "20bc0a000000" "4e75")
    if len(wrap_code) % 2:
        wrap_code += b"\x4e\x71"
    player_at = init_w + len(wrap_code)
    head = bra(0, init_w) + bra(4, exit_w if exit_w is not None else player_at + a.exit) + bra(8, player_at + a.play)
    code = bytearray(head + t + wrap_code)
    for at, off in pending:
        code[at:at + 4] = bra(at, player_at + off)
    out = bytes(code) + player
    assert out[player_at:] == player and player_at % 2 == 0
    return out, player_at


def main():
    num = lambda x: int(x, 0)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("player")
    ap.add_argument("out")
    ap.add_argument("--init", type=num, required=True)
    ap.add_argument("--play", type=num, required=True)
    ap.add_argument("--exit", type=num)
    ap.add_argument("--subtunes", type=int, required=True)
    ap.add_argument("--zero-based", action="store_true")
    ap.add_argument("--title", default="")
    ap.add_argument("--composer", default="")
    ap.add_argument("--ripper", default="")
    ap.add_argument("--year", default="")
    ap.add_argument("--timer", default="TC50")
    a = ap.parse_args()
    player = open(a.player, "rb").read()
    out, at = wrap(player, a)
    open(a.out, "wb").write(out)
    print("%s: %d sub-tunes, player unchanged at +$%x, %d bytes" % (a.out, a.subtunes, at, len(out)))


if __name__ == "__main__":
    main()
