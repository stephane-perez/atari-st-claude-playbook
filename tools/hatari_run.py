#!/usr/bin/env python3
"""Runs a program (or a floppy image) in Hatari WITHOUT a real window (Xvfb),
simulates key presses and saves screenshots at given times.

Examples:
  # GEMDOS program started automatically, 2 screenshots (after 15 s and 25 s)
  tools/hatari_run.py --prg build/HELLO.TOS --tos tos/TOS104.IMG --out out/h 15 25

  # floppy image (boot from A:, program in \\AUTO), F2 key at 30 s
  tools/hatari_run.py --disk build/intro.st --tos tos/TOS162.IMG --machine ste \\
      --mem 1024 --key F2@30 --out out/d 20 40

  # 520 ST from a floppy, GEMDOS calls (Pexec, Mshrink, Malloc) logged
  # in out/m/hatari.log
  tools/hatari_run.py --disk d.st --tos tos/TOS104.IMG --mem 512 \\
      --key F1@35 --extra "--trace gemdos" --out out/m 45

  # STE, Jaguar pad on extended port A emulated on the keyboard, held from 20 to 26 s
  tools/hatari_run.py --prg JOYTEST.TOS --tos etos512uk.img --machine ste \\
      --extra "--configfile tools/hatari-joysticks.cfg" --down h@20 --down r@20 \\
      --up h@26 --up r@26 --out out/j 22 28

  # Falcon with VGA
  tools/hatari_run.py --prg x.prg --tos tos/TOS404.IMG --machine falcon \\
      --mem 4096 --monitor vga --extra "--dsp none" --out out/f 40

Times are seconds since Hatari was started; TOS takes about 8 s to boot
(more on Falcon). Keys are sent with xdotool (X11 names: space, Escape,
F1..F10, Return, ...), so they go through Hatari's joystick emulation; keys
sent through the control socket or the command FIFO do not.

Prerequisites (Debian/Ubuntu): hatari xvfb xdotool   (scripts/setup-dev.sh)
"""
import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

MACHINES = {"st": "st", "ste": "ste", "megaste": "megaste", "tt": "tt", "falcon": "falcon"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--prg", help="program .PRG/.TOS started automatically from a GEMDOS hard disk")
    src.add_argument("--disk", help="floppy image .ST/.MSA (boot from A:)")
    ap.add_argument("--tos", required=True, help="TOS ROM image (supply it yourself)")
    ap.add_argument("--machine", default="st", choices=MACHINES)
    ap.add_argument("--mem", default="1024", help="RAM in KB (Falcon: 1..14 MB depending on the Hatari version)")
    ap.add_argument("--monitor", default="rgb", choices=["mono", "rgb", "vga", "tv"])
    ap.add_argument("--out", required=True, help="output folder for the screenshots")
    ap.add_argument("--key", action="append", default=[], metavar="KEY@SEC",
                    help="xdotool key sent at SEC seconds (repeatable), e.g. space@30")
    ap.add_argument("--down", action="append", default=[], metavar="KEY@SEC",
                    help="key pressed and held from SEC seconds (repeatable), e.g. a joystick "
                         "direction emulated on the keyboard (see tools/hatari-joysticks.cfg)")
    ap.add_argument("--up", action="append", default=[], metavar="KEY@SEC",
                    help="key released at SEC seconds (repeatable)")
    ap.add_argument("--hd-files", action="append", default=[], metavar="SRC[:DEST]",
                    help="file copied next to the program in the GEMDOS hard disk (repeatable)")
    ap.add_argument("--borders", choices=["on", "off"], default="off",
                    help="show the borders (useful for overscan)")
    ap.add_argument("--display", default=":99", help="Xvfb display number")
    ap.add_argument("--extra", default="", help="additional Hatari options (a single string)")
    ap.add_argument("--boot-timeout", type=float, default=30, help="wait for Hatari to connect (s)")
    ap.add_argument("waits", nargs="*", type=float, default=[15, 25], help="screenshot times (s)")
    a = ap.parse_args()

    for tool in ("hatari", "Xvfb", "xdotool"):
        if not shutil.which(tool):
            sys.exit("Missing tool: %s (see scripts/setup-dev.sh)" % tool)

    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    work = tempfile.mkdtemp(prefix="hatari_")
    sock_path = os.path.join(work, "ctl.sock")
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(sock_path)
    srv.listen(1)

    env = dict(os.environ, DISPLAY=a.display, SDL_AUDIODRIVER="dummy", HOME=work)
    xvfb = subprocess.Popen(["Xvfb", a.display, "-screen", "0", "1024x768x24"],
                            stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    time.sleep(1.5)

    cmd = ["hatari", "--machine", MACHINES[a.machine], "--memsize", str(a.mem),
           "--tos", os.path.abspath(a.tos), "--monitor", a.monitor,
           "--sound", "off", "--statusbar", "off", "--borders", a.borders,
           "--zoom", "1", "--fast-boot", "true", "--confirm-quit", "off",
           "--screenshot-dir", out, "--control-socket", sock_path]
    if a.prg:
        hd = os.path.join(work, "hd")
        os.makedirs(hd)
        name = os.path.basename(a.prg).upper()
        shutil.copy(a.prg, os.path.join(hd, name))
        for spec in a.hd_files:
            s, _, d = spec.partition(":")
            dest = os.path.join(hd, d or os.path.basename(s))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy(s, dest)
        cmd += ["--harddrive", hd, "--auto", "C:\\" + name]
    else:
        cmd += ["--disk-a", os.path.abspath(a.disk)]
    if a.extra:
        cmd += a.extra.split()

    # Hatari's messages (and the --trace output, e.g. --extra "--trace gemdos")
    # go to <out>/hatari.log
    log = open(os.path.join(out, "hatari.log"), "w")
    h = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
    srv.settimeout(a.boot_timeout)
    try:
        conn, _ = srv.accept()
    except socket.timeout:
        h.terminate(); xvfb.terminate()
        sys.exit("Hatari did not connect (wrong option? ROM refused?). "
                 "Rerun the command by hand to see the error message.")

    events = [(w, "shot", None) for w in a.waits]
    for kind, specs in (("key", a.key), ("keydown", a.down), ("keyup", a.up)):
        events += [(float(k.partition("@")[2]), kind, k.partition("@")[0]) for k in specs]
    t0 = time.time()
    for t, kind, k in sorted(events, key=lambda e: e[0]):
        time.sleep(max(0, t - (time.time() - t0)))
        if kind != "shot":
            win = subprocess.run(["xdotool", "search", "--name", "hatari"], env=env,
                                 capture_output=True, text=True).stdout.split()
            if win:
                subprocess.run(["xdotool", "windowfocus", win[0]], env=env, stderr=subprocess.DEVNULL)
            subprocess.run(["xdotool", kind, k], env=env)
        else:
            conn.sendall(b"hatari-shortcut screenshot\n")
            time.sleep(1.0)
    h.terminate()
    try:
        h.wait(timeout=5)
    except subprocess.TimeoutExpired:
        h.kill()
    xvfb.terminate()
    shutil.rmtree(work, ignore_errors=True)
    print("screenshots in", out, ":", sorted(f for f in os.listdir(out) if f.endswith(".png")))


if __name__ == "__main__":
    main()
