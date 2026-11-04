#!/usr/bin/env python3
"""unice_fuzz.py: differential fuzzing of unice.py against a 68000 Pack-Ice
depack routine run in Unicorn.

usage: unice_fuzz.py 2.3|2.4 ROUTINE.bin [CASES [SEED]]

ROUTINE.bin: raw 68000 code of a depack routine, entry at offset 0, called with
a0 = packed data, a1 = destination, returning with rts (position independent).
Supply it yourself: assemble the Pack-Ice source you have (vasm -Fbin -no-opt),
or extract the routine from a program you own (docs/03). Nothing of the kind is
shipped here.

A generator builds VALID random streams covering every token class (literal
runs of each size class including > 268 bytes, every length and distance
class, 2.40 repeats, the picture pass) and computes the expected output; the
generator, unice.py and the 68000 routine must agree, and the routine must not
write outside the destination. Exit status 1 on any difference.
Results obtained (Nov 2026): 2.3x against a 1992 game's routine and 2.40
against the published PACK-ICE 2.40 routine: several thousand cases, 0
difference; 6 deliberate mutations of unice.py all detected.
"""
import os
import random
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unice  # noqa: E402
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN  # noqa: E402
from unicorn.m68k_const import (UC_CPU_M68K_M68000, UC_M68K_REG_A0,  # noqa: E402
                                UC_M68K_REG_A1, UC_M68K_REG_A7)


def picture(out, end, blocks):
    a = end
    for _ in range(blocks):
        planes = [0, 0, 0, 0]
        for _ in range(4):
            a -= 2
            wd = struct.unpack_from(">H", out, a)[0]
            for _ in range(4):
                for k in range(4):
                    planes[k] = ((planes[k] << 1) | (wd >> 15)) & 0xFFFF
                    wd = (wd << 1) & 0xFFFF
        struct.pack_into(">4H", out, a, *planes)


class Gen:
    def __init__(self, variant, rnd):
        self.v = unice.VARIANTS[variant]
        self.var = variant
        self.r = rnd
        self.ev = []

    def bits(self, value, n):
        for i in range(n - 1, -1, -1):
            self.ev.append(("b", (value >> i) & 1))

    def literal_count(self, n):
        """n = run length - 1 (0..)"""
        if n == 0:
            self.bits(0, 1)
            return
        self.bits(1, 1)
        prefix = []
        for nbits, esc, base in unice.DIRECT:
            if esc is None or n - base < esc:
                v = n - base
                assert 0 <= v < (1 << nbits)
                for pb, pv in prefix:
                    self.bits(pv, pb)
                self.bits(v, nbits)
                return
            prefix.append((nbits, esc))
        raise ValueError(n)

    def make(self, ulen, pic):
        r = self.r
        out = bytearray(ulen)
        w = ulen
        stats = set()
        while True:
            # literal run? (forced when nothing written or fewer than 2 bytes left)
            if w == 0:              # a string filled the output: no literal, end
                self.bits(0, 1)
                break
            lit = w == ulen or w < 2 or r.random() < 0.45
            if lit:
                maxn = w
                cls = r.choice([1, 1, 3, 6, 13, 268, 600]) if w > 1 else 1
                n = r.randint(1, max(1, min(maxn, cls)))
                if w == ulen:       # first run: >= 2 bytes so that a string is possible
                    n = max(n, min(w, 2))
                if w - n == 1:      # a string (2 bytes or more) must follow a run
                    n = w
                self.bits(1, 1)
                self.literal_count(n - 1)
                stats.add("lit%d" % (0 if n == 1 else [b for _, _, b in unice.DIRECT if n - 1 >= b][-1]))
                for _ in range(n):
                    w -= 1
                    x = r.randrange(256)
                    out[w] = x
                    self.ev.append(("B", x))
            else:
                self.bits(0, 1)
            if w <= 0:
                break
            if w < 2:
                continue        # next iteration forces a literal
            # string
            written = ulen - w
            for _ in range(50):
                i = r.choice([0, 1, 2, 3, 4])
                if i == 4:
                    length = 8 + r.randrange(1 << 10)
                elif unice.LEN_READ[i]:
                    length = unice.LEN_BASE[i] + r.randrange(1 << unice.LEN_READ[i])
                else:
                    length = unice.LEN_BASE[i]
                if length + 2 > w:
                    continue
                if length:
                    j = r.choice([0, 1, 2])
                    nb, add = self.v["dist"][j]
                    val = r.randrange(1 << nb)
                    dist = val + add
                    if dist < 0 and self.v["negative_repeat"]:
                        dist -= length
                else:
                    j = r.choice([0, 1])
                    nb, add = self.v["short"][j]
                    val = r.randrange(1 << nb)
                    dist = val + add
                # source window [w+dist, w+dist+length+2) must be written or
                # being written (repeat): w+dist >= w-? and top <= ulen
                if w + length + 2 + dist > ulen or (dist < 0 and written == 0):
                    continue
                if dist < -1 - length:
                    continue
                break
            else:
                # fall back: shortest string at distance 0 (always possible here)
                assert written >= 2
                i, length, j, val = 0, 0, 0, -self.v["short"][0][1]
                nb, add = self.v["short"][0]
                dist = val + add
            self.bits((1 << i) - 1, i)
            if i < 4:
                self.bits(0, 1)
            if unice.LEN_READ[i]:
                self.bits(length - unice.LEN_BASE[i], unice.LEN_READ[i])
            if length:
                self.bits((1 << j) - 1, j)
                if j < 2:
                    self.bits(0, 1)
            else:
                self.bits(j, 1)
            self.bits(val, nb)
            stats.add("len%d" % i)
            stats.add(("dist%d" if length else "short%d") % j)
            if dist < 0:
                stats.add("repeat")
            s = w + length + 2 + dist
            for _ in range(length + 2):
                s -= 1
                w -= 1
                out[w] = out[s]
        # picture flag
        if pic:
            self.bits(1, 1)
            blocks = 4000
            if self.v["picture_count"]:
                self.ev.append(("PIC24",))
                v10 = r.randrange(4)
                self.bits(v10, 10)
                blocks = ((0b001111 << 10) | v10) + 1
            picture(out, ulen, blocks)
            stats.add("picture")
        else:
            self.bits(0, 1)
        return bytes(out), stats

    def serialize(self, ulen):
        width = 32 if self.v["long_buffer"] else 8
        units = []                   # consumption order
        init = []
        units.append(("init", init))
        cur, cap = init, width - 1
        for e in self.ev:
            if e[0] == "b":
                if len(cur) >= cap:
                    cur, cap = [], width
                    units.append(("buf", cur))
                cur.append(e[1])
            elif e[0] == "B":
                units.append(("lit", e[1]))
            else:                    # PIC24: buffer replaced by a constant
                cap = 0
        mem = []
        for kind, val in reversed(units):
            if kind == "lit":
                mem.append(bytes([val]))
                continue
            bits = list(val)
            if kind == "init":
                bits = bits + [1]
            bits += [0] * (width - len(bits))
            x = int("".join(map(str, bits)), 2)
            mem.append(x.to_bytes(width // 8, "big"))
        body = b"".join(mem)
        return self.v["magic"] + struct.pack(">II", 12 + len(body), ulen) + body


def run68k(code, blob, ulen):
    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(UC_CPU_M68K_M68000)
    uc.mem_map(0, 0x800000)
    BASE, SRC, DST, RET = 0x10000, 0x100000, 0x400000, 0x8000
    uc.mem_write(BASE, code)
    uc.mem_write(SRC, blob)
    uc.mem_write(DST - 64, b"\xAA" * (ulen + 128))
    uc.mem_write(RET, b"\x4e\x71")
    sp = 0x30000 - 4
    uc.mem_write(sp, struct.pack(">I", RET))
    uc.reg_write(UC_M68K_REG_A7, sp)
    uc.reg_write(UC_M68K_REG_A0, SRC)
    uc.reg_write(UC_M68K_REG_A1, DST)
    uc.emu_start(BASE, RET, count=500_000_000)
    guard = bytes(uc.mem_read(DST - 64, 64)) + bytes(uc.mem_read(DST + ulen, 64))
    return bytes(uc.mem_read(DST, ulen)), guard == b"\xAA" * 128


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in unice.VARIANTS:
        print(__doc__)
        return 2
    variant, ref = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    code = open(ref, "rb").read()
    r = random.Random(seed)
    seen = set()
    bad = 0
    for k in range(n):
        g = Gen(variant, r)
        big = k % 25 == 0
        pic = k % 50 == 0
        if pic:
            ulen = 32000 + r.randrange(2000) if variant == "2.3" else 8 * (0b001111 << 10 | 3) + 8 + r.randrange(800)
        else:
            ulen = r.randint(1, 40000 if big else 1500)
        expect, st = g.make(ulen, pic)
        blob = g.serialize(ulen)
        try:
            mine = unice.depack(blob, 0, variant)
        except Exception as e:
            mine = "ERR %s" % e
        ref_out, guard_ok = run68k(code, blob, ulen)
        ok = mine == expect and ref_out == expect and guard_ok
        seen |= st
        if not ok:
            bad += 1
            if bad <= 5:
                print("case %d ulen %d: unice==expect %s, 68k==expect %s, guard %s" % (
                    k, ulen, mine == expect, ref_out == expect, guard_ok))
    print("variant %s: %d cases, %d failures; paths covered: %s" % (variant, n, bad, " ".join(sorted(seen))))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
