#!/usr/bin/env python3
"""sndh_record.py: plays an SNDH sub-tune in Hatari (real emulator, real TOS),
records the audio and checks the YM registers against tools/ym_emu.py.

usage: sndh_record.py TUNE.SNDH OUT.(ogg|wav|flac) --tos TOS.IMG [--sub N]
                      [--seconds S] [--machine st|ste] [--display :97] [--keep DIR]
Needs: vasmm68k_mot (VASM env var, default .tools/vasm/), hatari, Xvfb, ffmpeg.

1. tools/sndhplay.s (init, then play from the VBL) is assembled with the tune.
2. Hatari runs it from a GEMDOS drive (1 MB, --sound 44100, --avirecord,
   --trace psg_write,video_vbl) and stops by itself (--run-vbls).
3. The YM registers written by the player in each VBL are compared with
   ym_emu.py, frame by frame ("as heard": mixer bits 6-7 = I/O port directions
   ignored, noise period compared only when a channel uses noise). A VBL in
   which Hatari shows no player write while ym_emu expects one is counted as a
   missed VBL and the comparison resynchronises (the player then continues one
   frame later, from the same state).
4. ffmpeg keeps the audio from the first sound for the tune's length + 2 s.
Duration: --seconds, else ym_emu's length (until 3 s of silence).
Hatari runs about in real time (AVI encoding): count the tune's length + ~40 s.
Verified (Nov 2026, Hatari 2.4.1, TOS 1.04 FR, 50 Hz): a game's 9 tunes,
3302 to 11575 frames each, 0 difference; examples/sndh/beep.s.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ym_emu  # noqa: E402

VASM = os.environ.get("VASM", os.path.join(ROOT, ".tools", "vasm", "vasmm68k_mot"))
BOOT_VBLS = 1800      # TOS boot + GEMDOS drive + autostart: > 30 s measured with TOS 1.04
TAIL_VBLS = 150


def norm(r):
    r = bytearray(r[:13])
    r[7] &= 0x3F
    if (r[7] >> 3) & 7 == 7:
        r[6] = 0
    return bytes(r)


def same(a, b):
    if a is None or b is None:
        return a is None and b is None
    return norm(a) == norm(b)


def trim(frames):
    i = 0
    while i < len(frames) and frames[i] is None:
        i += 1
    return frames[i:]


def hatari_frames(log, lo=0x800, hi=0x400000):
    """one entry per "VBL n" line: registers 0..13 after the writes made by code at
    lo..hi (TOS in ROM excluded), or None; leading None dropped"""
    rx = re.compile(r"ym write data reg=0x([0-9a-f]+) val=0x([0-9a-f]+) .*pc=([0-9a-f]+)")
    frames, regs, wrote, r13 = [], [0] * 16, False, False
    for line in open(log, errors="replace"):
        if line.startswith("VBL "):
            if wrote:
                r = regs[:14]
                r[13] = r[13] if r13 else 0xFF
                frames.append(bytes(r))
            else:
                frames.append(None)
            wrote = r13 = False
            continue
        m = rx.search(line)
        if m and lo <= int(m.group(3), 16) < hi:
            reg = int(m.group(1), 16)
            regs[reg] = int(m.group(2), 16)
            wrote = True
            r13 = r13 or reg == 13
    return trim(frames)


def compare_resync(hf, ef, off=0):
    """(identical, different, missed VBLs, compared)"""
    i, j, ok, bad, missed = 0, off, 0, 0, 0
    while i < len(ef) and j < len(hf):
        if same(hf[j], ef[i]):
            ok += 1; i += 1; j += 1
        elif hf[j] is None and ef[i] is not None:
            missed += 1; j += 1
        else:
            bad += 1; i += 1; j += 1
    return ok, bad, missed, ok + bad


def best_resync(hf, ef):
    return max((compare_resync(hf, ef, off) for off in range(4)), key=lambda r: r[0])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tune")
    ap.add_argument("out")
    ap.add_argument("--tos", required=True)
    ap.add_argument("--sub", type=int, default=1)
    ap.add_argument("--seconds", type=float)
    ap.add_argument("--machine", default="st", choices=["st", "ste"])
    ap.add_argument("--display", default=":97")
    ap.add_argument("--keep", help="copy the Hatari trace and the AVI there")
    a = ap.parse_args()
    tos = os.path.abspath(a.tos)
    data = open(a.tune, "rb").read()
    if not ym_emu.is_sndh(data):
        sys.exit("not an SNDH file (tools/sndh_wrap.py makes one from a raw player)")
    lowmem = ym_emu.tos_lowmem(tos)
    if a.seconds:
        frames = int(a.seconds * 50)
        ef, _ = ym_emu.run(data, 0, 8, a.sub, frames=frames, lowmem=lowmem)
    else:
        ef, _ = ym_emu.run(data, 0, 8, a.sub, lowmem=lowmem)
        frames = len(ef)
    ef = trim(ef)
    tmp = tempfile.mkdtemp()
    try:
        hd = os.path.join(tmp, "hd")
        os.makedirs(hd)
        shutil.copy(a.tune, os.path.join(tmp, "tune.sndh"))
        subprocess.run([VASM, "-Ftos", "-tos-flags=1", "-no-opt", "-nosym", "-quiet",
                        "-DSUBTUNE=%d" % a.sub, "-o", os.path.join(hd, "PLAY.TOS"),
                        os.path.join(HERE, "sndhplay.s")], cwd=tmp, check=True)
        avi, log = os.path.join(tmp, "rec.avi"), os.path.join(tmp, "psg.log")
        env = dict(os.environ, DISPLAY=a.display, SDL_AUDIODRIVER="dummy", HOME=tmp)
        xvfb = subprocess.Popen(["Xvfb", a.display, "-screen", "0", "800x600x24"], stderr=subprocess.DEVNULL)
        try:
            subprocess.run(["hatari", "--machine", a.machine, "--memsize", "1024", "--tos", tos,
                            "--monitor", "rgb", "--confirm-quit", "no", "--sound", "44100",
                            "--harddrive", hd, "--auto", "C:\\PLAY.TOS",
                            "--avirecord", "--avi-file", avi,
                            "--trace", "psg_write,video_vbl", "--trace-file", log,
                            "--run-vbls", str(BOOT_VBLS + frames + TAIL_VBLS)],
                           env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=BOOT_VBLS / 50 + frames / 25 + 600)
        finally:
            xvfb.terminate()
        hz = re.findall(r"vbl_cycles=(\d+)", open(log, errors="replace").read()[-20000:])
        hf = hatari_frames(log)
        ok, bad, missed, n = best_resync(hf, ef)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", avi, "-vn",
                        "-af", "silenceremove=start_periods=1:start_threshold=-60dB",
                        "-t", "%.1f" % (frames / 50 + 2), a.out], check=True)
        if a.keep:
            os.makedirs(a.keep, exist_ok=True)
            shutil.copy(log, a.keep)
            shutil.copy(avi, a.keep)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("%s sub-tune %d: %.1f s; Hatari (%s) vs ym_emu: %d/%d frames identical, %d different, "
          "%d VBL without player call -> %s"
          % (a.tune, a.sub, frames / 50, "50 Hz" if hz and hz[-1] in ("160256", "160240") else
             "vbl_cycles=%s" % (hz[-1] if hz else "?"), ok, n, bad, missed, a.out))
    sys.exit(0 if bad == 0 and n > 0 else 1)


if __name__ == "__main__":
    main()
