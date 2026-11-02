#!/usr/bin/env python3
"""Two minimal, tested templates for 68000 reverse engineering in Python.

  python3 tools/emu_snippets.py        # runs the self-test (disassembles + emulates a mini code)

1. disassemble(code, base)  : linear disassembly with Capstone.
2. run_68000(code, ...)     : execution in Unicorn (68000 model), with a trace of
                              instructions and memory writes. This is the basis of
                              "unpacking by emulation" of a packed program: let the
                              depacker run, stop when the PC enters the unpacked area,
                              then copy the memory.

Pitfalls met (see docs/03-reverse-engineering.md):
  * Unicorn: without ctl_set_cpu_model(UC_CPU_M68K_M68000) the behaviour differs from the
    68000 (unexpected exceptions); set it BEFORE mem_map/emu_start.
  * Capstone: decodes 68020+ modes in 68000 mode, gets the size of some memory shifts
    wrong, rejects movec; always check on known code.
"""
import struct

from capstone import CS_ARCH_M68K, CS_MODE_BIG_ENDIAN, CS_MODE_M68K_000, Cs
from unicorn import UC_ARCH_M68K, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_MODE_BIG_ENDIAN, Uc
from unicorn.m68k_const import UC_CPU_M68K_M68000, UC_M68K_REG_A7, UC_M68K_REG_D0, UC_M68K_REG_PC, UC_M68K_REG_SR


def disassemble(code, base=0):
    md = Cs(CS_ARCH_M68K, CS_MODE_BIG_ENDIAN | CS_MODE_M68K_000)
    return ["%06x: %-14s %s %s" % (i.address, i.bytes.hex(), i.mnemonic, i.op_str)
            for i in md.disasm(code, base)]


def run_68000(code, base=0x10000, stop=None, d0=0, max_insn=100000, trace=False):
    """Runs `code` loaded at `base` up to address `stop` (or the end of the code).
    Returns (emulator, write log)."""
    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(UC_CPU_M68K_M68000)           # BEFORE mem_map
    uc.mem_map(0, 0x200000)
    uc.mem_write(base, code)
    uc.reg_write(UC_M68K_REG_A7, 0x1F0000)
    uc.reg_write(UC_M68K_REG_SR, 0x2000)               # supervisor mode
    uc.reg_write(UC_M68K_REG_D0, d0)
    writes, pcs = [], []
    uc.hook_add(UC_HOOK_MEM_WRITE, lambda u, t, a, s, v, ud: writes.append((a, s, v)))
    if trace:
        uc.hook_add(UC_HOOK_CODE, lambda u, a, s, ud: pcs.append(a))
    uc.emu_start(base, stop if stop is not None else base + len(code), count=max_insn)
    if trace:
        print("pc trace:", " ".join("%x" % p for p in pcs[:20]))
    return uc, writes


def _selftest():
    # moveq #5,d0 ; add.l d0,d0 ; move.l d0,$20000 ; nop
    code = bytes.fromhex("7005" "d080" "23c000020000" "4e71")
    lst = disassemble(code, 0x10000)
    print("\n".join(lst))
    uc, writes = run_68000(code, 0x10000, trace=True)
    assert uc.reg_read(UC_M68K_REG_D0) == 10
    assert writes == [(0x20000, 4, 10)], writes
    assert struct.unpack(">I", bytes(uc.mem_read(0x20000, 4)))[0] == 10
    print("self-test OK: D0 =", uc.reg_read(UC_M68K_REG_D0), "write", writes)


if __name__ == "__main__":
    _selftest()
