#!/bin/sh
# get-vasm.sh [folder] [archive]
# Builds vasm (68000 assembler, Motorola syntax) and installs the binary
# in <folder>/vasm/vasmm68k_mot.
#   - with archive: uses your local vasm.tar.gz;
#   - without archive: downloads the latest sources from the author's site and,
#     if that fails (restricted network), falls back to the unmodified archive
#     shipped in third_party/vasm/ (vasm 2.0f, its own licence: see its README).
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEST=${1:-.tools}
ARCHIVE=$2
URL=http://sun.hasenbraten.de/vasm/release/vasm.tar.gz
BUNDLED="$ROOT/third_party/vasm/vasm.tar.gz"
case "$ARCHIVE" in ""|/*) ;; *) ARCHIVE="$(pwd)/$ARCHIVE" ;; esac
mkdir -p "$DEST"
cd "$DEST"
if [ -x vasm/vasmm68k_mot ]; then echo "vasm already present: $DEST/vasm/vasmm68k_mot"; exit 0; fi
if [ -z "$ARCHIVE" ]; then
  rm -f vasm.tar.gz
  if { command -v curl >/dev/null && curl -fsSL -o vasm.tar.gz "$URL"; } \
     || { command -v wget >/dev/null && wget -q -O vasm.tar.gz "$URL"; }; then
    ARCHIVE=$(pwd)/vasm.tar.gz
    echo "vasm: downloaded from $URL"
  else
    rm -f vasm.tar.gz            # a failed download leaves an empty file
    ARCHIVE=$BUNDLED
    echo "vasm: download failed, using $ARCHIVE"
    (cd "$ROOT/third_party/vasm" && sha256sum -c SHA256SUMS)
  fi
fi
tar xzf "$ARCHIVE"
cd vasm
make CPU=m68k SYNTAX=mot -j"$(nproc 2>/dev/null || echo 2)" >/dev/null
./vasmm68k_mot 2>&1 | head -1
echo "OK: $DEST/vasm/vasmm68k_mot"
