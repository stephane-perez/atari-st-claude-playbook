# 01 — Environment: install, reproduce, supply

Versions this repository was verified with (November 2026): vasm 2.0f (M68k backend 2.8c,
Motorola module 3.19f), Hatari 2.4.1 (Ubuntu package `2.4.1+dfsg`), Python 3.13, Capstone 5.0.7,
Unicorn 2.1.4.

## What the repository contains / does not contain

| In the repository | To supply yourself (never in git) |
|---|---|
| scripts, Python tools, `examples/hello` example, documentation | **TOS ROMs** (1.04, 1.62, 2.06, 4.04…), in `tos/` |
| | `vasm.tar.gz` if the network is restricted (otherwise downloaded) |
| | games, programs, floppies you want to study |

TOS ROMs are copyrighted by Atari: they go neither in the repository nor in a release.
The repository's `.gitignore` excludes `tos/`, `*.img`, `*.rom`, `build/`, `.tools/`.

## Installation

```sh
sh scripts/setup-dev.sh                 # Debian/Ubuntu (root or sudo)
sh scripts/setup-dev.sh vasm.tar.gz     # same, with a local vasm archive
```

The script does, in this order: `apt-get update` (**mandatory**), installs
`hatari xvfb xdotool mtools dosfstools build-essential python3-pip`, then
`pip install pillow capstone unicorn` (with `--break-system-packages` if pip demands it),
then builds vasm into `.tools/vasm/`.

### Why `apt-get update` is mandatory

In a fresh workspace the package lists are empty. Without `apt-get update`,
`apt-get install hatari` answers "package not found". One session once wrongly concluded
"Hatari cannot be installed here" for that reason alone, and the user had to correct it.
Rule: **an installation failure is never concluded before `apt-get update` and a second
attempt.**

## Workspace network

In this project's claude.ai sessions the shell goes through an allowlist: package repositories
(apt, PyPI, npm) and GitHub work; most other sites (curl, wget, Python requests) are refused.
Practical consequences:

- vasm: if `sun.hasenbraten.de` is unreachable, attach `vasm.tar.gz` to the conversation.
- The web-reading tools (search, WebFetch) are separate and respect `robots.txt`: a site that
  forbids it cannot be fetched by Claude. Then write a script the user runs on their machine.
- Do not retry the same request with another command: every path goes through the same
  allowlist.
- A private GitHub repository is not reachable without authentication: provide a zip or a
  `git bundle`, and let the user push.

## Virtual screen

Hatari runs without a real window: `Xvfb :99` + `SDL_AUDIODRIVER=dummy`. `tools/hatari_run.py`
starts all this, sends keys with `xdotool` and asks Hatari for screenshots through its control
socket (`--control-socket`). Details and variants: `docs/04`.

## Where to keep copyrighted files

Proven convention: a folder **next to** the repository (for example `../local/` with `rom/`,
`disk/`, `game/`), never inside it. Scripts receive paths as parameters or environment
variables (`TOS_DIR`, `ATOR=…`). Before each commit: `git status` then
`git log --all --name-only` to make sure no original file got in.

## Resuming work in a new session

A recycled workspace has lost everything. An effective resume message (adapt it):

> Resume project X. Read `CLAUDE.md` and `docs/ROADMAP.md` from the attached repository. Install the
> tools with `scripts/setup-dev.sh`, build with `make`, verify with `make check`, then let's tackle: …

Attach: the latest zip of the repository, the TOS ROMs, `vasm.tar.gz`, the game or program
under study. Keep a state file in the repository ("where we are", what is only tested in
Hatari, next steps): that is what lets you restart without the conversation history.

## Toolchains for other languages

This repository mostly documents 68000 assembly with vasm. Other toolchains met:

- **C for TOS/MiNT**: cross-compiler `m68k-atari-mint-gcc`. On Ubuntu, the PPA
  `ppa:vriviere/ppa` provides `cross-mint-essential` (binutils, gcc, mintbin, mintlib, gemlib,
  pml). This PPA is *rolling*: for a reproducible build two years from now, pin the package
  versions. This is the mechanism of the public `freemint/teradesk` repository
  (GitHub Actions); it transposes to a personal repository.
- **Generic m68k GCC + home-made converter to `.PRG`**: used for an adventure engine in C;
  it required providing own 32-bit multiplication/division routines for a plain 68000.
- **GNU as** (`binutils-m68k-linux-gnu`) with an ELF → PRG converter: used for an existing
  demo written for GNU as.
- **Devpac sources**: vasm with `-devpac -no-opt` approximates Devpac 2 behaviour to check
  that a source meant for Devpac assembles (see `docs/02`).
