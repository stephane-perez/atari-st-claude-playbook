#!/usr/bin/env python3
"""Converts a UTF-8 text into a file readable on the Atari ST desktop.

  python3 tools/txt2st.py README.txt build/README.TXT

- character set: the ST's, identical to CP437 for accented letters and the
  guillemets (bytes $80-$AF); what lies above $AF (box drawing in CP437)
  differs on the ST, so it is refused, as are characters CP437 lacks
  (for French: no capital A grave, no oe ligature);
- CR LF line endings, trailing spaces removed, trailing blank lines removed;
- 78 characters per line at most (the desktop's "show" window).
Plain ASCII needs no conversion beyond the line endings.
"""
import sys


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    lines = open(sys.argv[1], encoding="utf-8").read().split("\n")
    out = bytearray()
    for n, line in enumerate(lines, 1):
        line = line.rstrip()
        if len(line) > 78:
            sys.exit("%s:%d: line longer than 78 characters" % (sys.argv[1], n))
        try:
            b = line.encode("cp437")
        except UnicodeEncodeError as e:
            sys.exit("%s:%d: character not in the ST set: %r" % (sys.argv[1], n, e.object[e.start]))
        if any(c >= 0xB0 for c in b):
            sys.exit("%s:%d: character not in the ST set (above $AF)" % (sys.argv[1], n))
        out += b + b"\r\n"
    while out.endswith(b"\r\n\r\n"):
        out = out[:-2]
    open(sys.argv[2], "wb").write(out)


if __name__ == "__main__":
    main()
