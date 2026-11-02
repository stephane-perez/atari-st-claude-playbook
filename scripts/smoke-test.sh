#!/bin/sh
# smoke-test.sh: proves the chain works end to end.
# Assembles examples/hello, runs it in Hatari under each TOS found in tos/
# (or $TOS_DIR) and checks that the screenshot shows the expected text.
#
# TOS ROMs are not in the repository: copy them into tos/ (see docs/05-hardware-and-tos.md).
# Recognised by file name: 1.04 -> STF, 1.62 -> STE, 2.06 -> Mega STE, 4.04 -> Falcon.
set -e
cd "$(dirname "$0")/.."
TOS_DIR=${TOS_DIR:-tos}
make -s all
fail=0
run() {  # name, pattern, machine, memory (KB), monitor, wait
  f=$(ls "$TOS_DIR"/*$2* 2>/dev/null | head -1)
  [ -n "$f" ] || { echo "SKIP  $1: no ROM '$2' in $TOS_DIR"; return; }
  rm -rf build/shots_$1
  python3 tools/hatari_run.py --prg build/HELLO.TOS --tos "$f" --machine "$3" --mem "$4" \
      --monitor "$5" --out build/shots_$1 "$6" >/dev/null 2>&1 || true
  png=$(ls build/shots_$1/*.png 2>/dev/null | tail -1)
  if [ -n "$png" ] && python3 - "$png" <<'P'
import sys
from PIL import Image
# The program clears the screen and writes 3 lines of black text at the top left:
# we require dark pixels in the first 60 rows and almost none lower down
# (a GEM desktop, with its icons, would not pass this test).
im = Image.open(sys.argv[1]).convert("L")
top = sum(im.crop((0, 0, 640, 60)).histogram()[:100])
low = sum(im.crop((0, 120, 640, 400)).histogram()[:100])
sys.exit(0 if top >= 200 and low <= 50 else 1)
P
  then echo "OK    $1 ($f)"; else echo "FAIL  $1 ($f)"; fail=1; fi
}
run stf    1.04 st      512  rgb 20
run ste    1.62 ste     1024 rgb 20
run megaste 2.06 megaste 4096 rgb 25
run falcon 4.04 falcon  4096 vga 40
exit $fail
