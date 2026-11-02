#!/bin/sh
# setup-dev.sh: installs the development and test tools (Debian/Ubuntu).
#   Hatari (emulator), Xvfb + xdotool (virtual screen and simulated keys),
#   mtools/dosfstools (floppy images), Python: Pillow, Capstone, Unicorn.
# TOS ROMs, games and commercial software are NEVER provided:
# add them yourself (see docs/01-environment.md).
set -e
cd "$(dirname "$0")/.."
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
$SUDO apt-get update            # ESSENTIAL: without it, packages are "not found"
$SUDO apt-get install -y --no-install-recommends \
    build-essential python3-pip hatari xvfb xdotool mtools dosfstools
pip install --user pillow capstone unicorn 2>/dev/null \
  || pip install --break-system-packages pillow capstone unicorn
sh scripts/get-vasm.sh .tools "$1"
echo "Ready. Add your TOS ROMs in tos/ then run: sh scripts/smoke-test.sh"
