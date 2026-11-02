#!/bin/sh
# get-vasm.sh [folder] [archive]
# Builds vasm (68000 assembler, Motorola syntax) and installs the binary
# in <folder>/vasm/vasmm68k_mot.
#   - without archive: downloads the sources from the author's site
#     (needs network access to that site);
#   - with archive: uses your local vasm.tar.gz (case of a workspace with a
#     restricted network: attach the archive to the conversation).
set -e
DEST=${1:-.tools}
ARCHIVE=$2
URL=http://sun.hasenbraten.de/vasm/release/vasm.tar.gz
mkdir -p "$DEST"
cd "$DEST"
if [ -x vasm/vasmm68k_mot ]; then echo "vasm already present: $DEST/vasm/vasmm68k_mot"; exit 0; fi
if [ -n "$ARCHIVE" ]; then
  tar xzf "$ARCHIVE"
else
  command -v curl >/dev/null && curl -fsSL -o vasm.tar.gz "$URL" || wget -q -O vasm.tar.gz "$URL"
  tar xzf vasm.tar.gz
fi
cd vasm
make CPU=m68k SYNTAX=mot -j"$(nproc 2>/dev/null || echo 2)" >/dev/null
./vasmm68k_mot 2>&1 | head -1
echo "OK: $DEST/vasm/vasmm68k_mot"
