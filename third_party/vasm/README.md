# vasm (third-party, NOT under this repository's MIT licence)

`vasm.tar.gz` is the **unmodified** source archive of vasm, the portable assembler by
Volker Barthelmann (http://sun.hasenbraten.de/vasm/), version **2.0f** (history dated
10.07.26). It is here so that `scripts/get-vasm.sh` can build the assembler when the
workspace network cannot reach the author's site (`docs/01`).

SHA-256 (see `SHA256SUMS`):
`c84b2de1cbb87831795fe64a85c5d9a7002a766e3a7c30b0a2d7d5e99d878f49`

## Licence (quoted from `vasm/doc/vasm.texi` inside the archive)

> vasm is copyright in 2002-2026 by Volker Barthelmann.
>
> This archive may be redistributed without modifications and used
> for non-commercial purposes.
>
> An exception for commercial usage is granted, provided that the target
> CPU is M68k and the target OS is AmigaOS. Resulting binaries may be
> distributed commercially without further licensing.
>
> In all other cases you need my written consent.
>
> Certain modules may fall under additional copyrights.

Consequences for this repository:

- the archive stays **byte-identical** to the author's (check with `sha256sum -c SHA256SUMS`);
  never commit an extracted or patched copy here;
- non-commercial use only (commercial use outside AmigaOS/M68k needs the author's consent);
- to update: replace `vasm.tar.gz` with a newer official archive, unmodified, and update
  `SHA256SUMS`, the version above and `docs/01`.
