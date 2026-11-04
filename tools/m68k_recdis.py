#!/usr/bin/env python3
"""m68k_recdis.py: recursive (flow-following) 68000 disassembler for a raw memory
image, producing a study listing with labels.

usage: m68k_recdis.py IMAGE LOAD_ADDR OUT.lst [--entry ADDR ...] [--labels FILE]
                      [--stats]
  IMAGE      raw bytes loaded at LOAD_ADDR (no header)
  --entry    extra code entry points (hex accepted: 0x...); LOAD_ADDR is one
  --labels   file of "ADDRESS NAME [comment]" lines (# comments allowed)

Code is found by following the flow from the entry points: bra/bsr/Bcc/DBcc,
jsr/jmp to absolute or pc-relative targets, and addresses stored into the
exception vectors (move.l #ADDR,$xx.w with $xx < $400: VBL, MFP timers...).
A path stops at rts/rte/rtr, bra, jmp, or an instruction Capstone rejects in
68000 mode. Everything else is listed as data (dc.b, with ASCII runs shown).
Indirect jumps (jmp (a0), jump tables) are NOT followed: add --entry for them
(an SNDH file: LOAD_ADDR 0 with --entry 4 --entry 8, the exit and play branches).
The listing is for reading; it is not meant to be reassembled (docs/03).
"""
import argparse
import re
import struct
import sys

import capstone

BRANCH = re.compile(r"^(bra|bsr|b(hi|ls|cc|cs|ne|eq|vc|vs|pl|mi|ge|lt|gt|le|hs|lo)|db\w+)(\.[bswl])?$")
STOP = {"rts", "rte", "rtr", "bra", "jmp", "illegal"}
VEC_STORE = re.compile(r"^#\$([0-9a-f]+), \$([0-9a-f]+)\.w$")


def parse_num(s):
    return int(s, 0)


class Disasm:
    def __init__(self, data, base):
        self.d = data
        self.base = base
        self.end = base + len(data)
        self.md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_M68K_000)
        self.ins = {}            # addr -> (size, mnemonic, op_str)
        self.code_refs = {}      # target -> set(kind)
        self.data_refs = set()

    def inside(self, a):
        return self.base <= a < self.end

    def decode(self, a):
        off = a - self.base
        for i in self.md.disasm(self.d[off:off + 12], a, 1):
            return i
        return None

    def run(self, entries):
        todo = [e for e in entries if self.inside(e)]
        for e in todo:
            self.code_refs.setdefault(e, set()).add("entry")
        while todo:
            a = todo.pop()
            areg = {}                    # last address loaded into aN on this path
            while self.inside(a) and a not in self.ins:
                i = self.decode(a)
                if i is None or a & 1:
                    break
                m, ops = i.mnemonic, i.op_str
                self.ins[a] = (i.size, m, ops)
                tgt = self.target(i)
                if tgt is not None and self.inside(tgt):
                    kind = "sub" if m.startswith(("bsr", "jsr")) else "jmp"
                    self.code_refs.setdefault(tgt, set()).add(kind)
                    todo.append(tgt)
                v = VEC_STORE.match(ops) if m.startswith("move.l") else None
                if v and int(v.group(2), 16) < 0x400 and self.inside(int(v.group(1), 16)):
                    t = int(v.group(1), 16)
                    self.code_refs.setdefault(t, set()).add("vector $%x" % int(v.group(2), 16))
                    todo.append(t)
                for x in self.addresses(ops):
                    if self.inside(x) and x != tgt:
                        self.data_refs.add(x)
                # lea ADDR,aN followed by move.l aN,<vector> / jsr (aN) / jmp (aN)
                lm = re.match(r"^\$([0-9a-f]+)(\(pc\)|\.l|\.w), (a[0-6])$", ops) if m.startswith("lea") else None
                if lm:
                    areg[lm.group(3)] = int(lm.group(1), 16)
                vm = re.match(r"^(a[0-6]), \$([0-9a-f]+)(\((a[0-7])\)|\.w)$", ops) if m.startswith("move.l") else None
                # a vector: absolute short address, or a base register known to hold 0
                if vm and vm.group(4) and areg.get(vm.group(4)) != 0:
                    vm = None
                if vm and vm.group(1) in areg and int(vm.group(2), 16) < 0x400:
                    t = areg[vm.group(1)]
                    if self.inside(t):
                        self.code_refs.setdefault(t, set()).add("vector $%x" % int(vm.group(2), 16))
                        todo.append(t)
                jm = re.match(r"^\((a[0-6])\)$", ops) if m.split(".")[0] in ("jsr", "jmp") else None
                if jm and jm.group(1) in areg and self.inside(areg[jm.group(1)]):
                    t = areg[jm.group(1)]
                    self.code_refs.setdefault(t, set()).add("sub" if m.startswith("jsr") else "jmp")
                    todo.append(t)
                base_m = m.split(".")[0]
                if base_m in STOP:
                    break
                a += i.size

    def plausible(self, a, limit=300):
        """true if code at a decodes as 68000 code up to a closing instruction
        (rts/rte/rtr/bra/jmp) without any rejected opcode"""
        seen = 0
        if self.d[a - self.base] == 0:          # ori #imm,<ea>: almost always data
            return False
        while self.inside(a) and seen < limit:
            if a in self.ins:
                return True
            i = self.decode(a)
            if i is None or i.mnemonic in ("illegal",) or "dc.w" in i.mnemonic:
                return False
            if re.search(r"\[|\*\s?[248]|bf|cas|chk2|cmp2|pack|unpk", i.op_str + " " + i.mnemonic):
                return False          # 68020+ addressing or instructions
            if i.mnemonic.split(".")[0] in STOP:
                return True
            a += i.size
            seen += 1
        return False

    def pointer_scan(self):
        """long words of the data areas pointing into the image, tried as code
        entry points (function tables, object handlers); returns how many were kept"""
        kept = 0
        changed = True
        while changed:
            changed = False
            covered = set()
            for a, (size, _, _) in self.ins.items():
                covered.update(range(a, a + size))
            for off in range(0, len(self.d) - 3, 2):
                a = self.base + off
                if a in covered or a + 2 in covered:
                    continue
                t = struct.unpack_from(">I", self.d, off)[0]
                if t & 1 or not self.inside(t) or t in self.ins or t in covered:
                    continue
                if self.plausible(t):
                    self.code_refs.setdefault(t, set()).add("ptr")
                    self.run([t])
                    kept += 1
                    changed = True
                    break
        return kept

    def addresses(self, ops):
        """addresses of the program referenced by an operand string: absolute .l,
        pc-relative, absolute .w below $8000 (above: sign-extended, hardware);
        immediates (#) are values, not addresses"""
        out = []
        for m in re.finditer(r"(#)?\$([0-9a-f]{1,8})(\.w|\.l|\(pc)?", ops):
            if m.group(1):
                continue
            x = int(m.group(2), 16)
            if m.group(3) == ".w" and x >= 0x8000:
                continue
            if m.group(3) is None and not re.search(r"^(b|db)", ""):
                pass
            out.append(x)
        return out

    def target(self, i):
        m = i.mnemonic.split(".")[0]
        ops = i.op_str
        if BRANCH.match(i.mnemonic) or m in ("bra", "bsr"):
            t = re.findall(r"\$([0-9a-f]+)$", ops)
            return int(t[-1], 16) if t else None
        if m in ("jsr", "jmp"):
            t = re.match(r"^\$([0-9a-f]+)(\.[wl])?$", ops)
            if t:
                return int(t.group(1), 16)
            t = re.match(r"^\$([0-9a-f]+)\(pc\)$", ops)
            if t:
                return int(t.group(1), 16)
        return None


def load_labels(path):
    names, comments = {}, {}
    if not path:
        return names, comments
    for line in open(path):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split(None, 2)
        a = int(parts[0], 16) if not parts[0].startswith("0x") else int(parts[0], 0)
        names[a] = parts[1]
        if len(parts) > 2:
            comments[a] = parts[2]
    return names, comments


def write(dis, out, names, comments):
    def label(a):
        if a in names:
            return names[a]
        if a in dis.code_refs:
            k = dis.code_refs[a]
            if "sub" in k:
                return "sub_%06x" % a
            if "ptr" in k:
                return "ptr_%06x" % a
            return "L_%06x" % a
        if a in dis.data_refs:
            return "D_%06x" % a
        return None

    def sub_ops(ops):
        def rep(m):
            if m.group(1) or (m.group(3) == ".w" and int(m.group(2), 16) >= 0x8000):
                return m.group(0)
            x = int(m.group(2), 16)
            lab = label(x) if dis.inside(x) else None
            return lab + (m.group(3) or "") if lab else m.group(0)
        return re.sub(r"(#)?\$([0-9a-f]{1,8})(?![0-9a-f])(\.w|\.l|\(pc\))?", rep, ops)

    f = open(out, "w")
    f.write("; study listing generated by m68k_recdis.py - not reassemblable as is\n")
    a = dis.base
    while a < dis.end:
        lab = label(a)
        if lab:
            extra = ""
            if a in dis.code_refs:
                kinds = sorted(k for k in dis.code_refs[a] if k.startswith("vector"))
                extra = "\t; " + ", ".join(kinds) if kinds else ""
            if a in comments:
                extra += "\t; " + comments[a]
            f.write("\n%s:%s\n" % (lab, extra))
        if a in dis.ins:
            size, m, ops = dis.ins[a]
            raw = dis.d[a - dis.base:a - dis.base + size].hex()
            f.write("%06x  %-20s\t%s\t%s\n" % (a, raw, m, sub_ops(ops)))
            a += size
            continue
        # data run until the next instruction or label
        b = a + 1
        while b < dis.end and b not in dis.ins and label(b) is None and b - a < 16:
            b += 1
        chunk = dis.d[a - dis.base:b - dis.base]
        txt = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        f.write("%06x  %-20s\tdc.b\t%s\t; %s\n" % (a, "", ",".join("$%02x" % c for c in chunk), txt))
        a = b
    f.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("load", type=parse_num)
    ap.add_argument("out")
    ap.add_argument("--entry", action="append", type=parse_num, default=[])
    ap.add_argument("--labels")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--pointer-scan", action="store_true",
                    help="also try long words of the data areas that point into the image "
                         "as code (function tables); kept only if they decode as plausible code")
    a = ap.parse_args()
    data = open(a.image, "rb").read()
    names, comments = load_labels(a.labels)
    dis = Disasm(data, a.load)
    dis.run([a.load] + a.entry + [x for x in names if x not in a.entry])
    if a.pointer_scan:
        print("pointer scan: %d entry points added" % dis.pointer_scan())
    write(dis, a.out, names, comments)
    code = sum(s for s, _, _ in dis.ins.values())
    subs = sum(1 for k in dis.code_refs.values() if "sub" in k)
    print("%s: %d instructions, %d bytes of code (%.1f%% of %d), %d subroutines, %d vector handlers"
          % (a.out, len(dis.ins), code, 100.0 * code / len(data), len(data), subs,
             sum(1 for k in dis.code_refs.values() if any(x.startswith("vector") for x in k))))


if __name__ == "__main__":
    main()
