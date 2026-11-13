#!/usr/bin/env python3
"""acsi_bench.py - run a program in Hatari with an emulated ACSI disk and read back counters from RAM.

  acsi_bench.py --tos TOS162.img --acsi disk.img --boot-floppy boot.st --hd-dir DIR \
                --auto 'P:\\TEST.PRG' [--warm 30] [--meas 8] [--counters 0x3F0000]

Hatari is started under xvfb with a control socket; after --warm seconds it dumps `--len` bytes at
--counters, waits --meas seconds, dumps again, and prints the differences. `--fast-forward` (default on)
keeps the emulated time valid (VBLs are counted, not wall-clock seconds).
Counter layout expected by the example in examples/acsi-stream (long each): +0 idle loops, +4 VBL word,
+8 frame number; others are printed raw. Adapt `decode()` to your own program.

What this proves: the ACSI protocol and the data read (Hatari's ACSI disk answers instantly).
What it does NOT prove: timing on a real drive/adapter (docs/11).
The hard-disk driver (HDDRIVER or similar) is NOT included: put it on --boot-floppy (in AUTO),
because TOS 1.62 has no ACSI driver of its own that mounts an MBR partition.
"""
import argparse, os, re, socket, subprocess, sys, tempfile, time

ap = argparse.ArgumentParser()
ap.add_argument('--tos', required=True); ap.add_argument('--acsi', required=True)
ap.add_argument('--boot-floppy'); ap.add_argument('--hd-dir', help='GEMDOS drive (host dir) holding the program; mapped to P:')
ap.add_argument('--auto', required=True, help='program started by TOS, e.g. P:\\\\TEST.PRG')
ap.add_argument('--machine', default='ste'); ap.add_argument('--memsize', default='4096')
ap.add_argument('--warm', type=float, default=30); ap.add_argument('--meas', type=float, default=8)
ap.add_argument('--counters', default='0x3F0000'); ap.add_argument('--len', type=int, default=80)
ap.add_argument('--no-ff', action='store_true'); ap.add_argument('--config')
a = ap.parse_args()

tmp = tempfile.mkdtemp(); sock = os.path.join(tmp, 'hatari.sock'); logf = os.path.join(tmp, 'out.txt')
srv = socket.socket(socket.AF_UNIX); srv.bind(sock); srv.listen(1)
cmd = ['xvfb-run', '-a', '-s', '-screen 0 800x600x24', 'hatari'] + (['--configfile', a.config] if a.config else []) + [
    '--machine', a.machine, '--memsize', a.memsize, '--tos', a.tos, '--fast-boot', 'true', '--sound', 'off',
    '--frameskips', '0', '--statusbar', 'false', '--borders', 'false', '--acsi', '0=' + a.acsi,
    '--auto', a.auto, '--control-socket', sock, '--monitor', 'rgb']
if a.hd_dir: cmd += ['--harddrive', a.hd_dir, '--gemdos-drive', 'P']
if a.boot_floppy: cmd += ['--disk-a', a.boot_floppy]
if not a.no_ff: cmd += ['--fast-forward', 'true']
p = subprocess.Popen(cmd, stdout=open(logf, 'w'), stderr=subprocess.STDOUT)
srv.settimeout(30); conn, _ = srv.accept()
send = lambda c: conn.sendall((c + '\n').encode())
dump = 'hatari-debug memdump %s %d' % (a.counters, a.len)
time.sleep(a.warm); send(dump); time.sleep(a.meas); send(dump); time.sleep(1)
send('hatari-shortcut quit'); time.sleep(1); p.terminate()

out = open(logf).read(); base = int(a.counters, 16)
dumps, cur = [], None
for addr, data in re.findall(r'^\s*\$?0*([0-9a-fA-F]{4,8}):\s*((?:[0-9a-fA-F]{2}\s*)+)', out, re.M):
    if int(addr, 16) == base: dumps.append('')
    if dumps: dumps[-1] += ''.join(data.split())
if len(dumps) < 2: sys.exit('no counter dump found; Hatari output: ' + logf)
b0, b1 = (bytes.fromhex(d)[:a.len] for d in dumps[:2])
L = lambda b, o: int.from_bytes(b[o:o+4], 'big')
idle, frames = L(b1, 0) - L(b0, 0), L(b1, 8) - L(b0, 8)
dv = abs((int.from_bytes(b1[4:6], 'big') - int.from_bytes(b0[4:6], 'big') + 32768) % 65536 - 32768)
print('VBLs %d, frames %d => %.2f VBL per frame; idle loops per VBL %.1f' % (dv, frames, dv / max(frames, 1), idle / max(dv, 1)))
print('raw longs (end):', [L(b1, o) for o in range(12, min(a.len, 72), 4)])
