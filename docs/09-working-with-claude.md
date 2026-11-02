# 09 — Working with Claude on the Atari ST

## What Claude does well here

- Write 68000 and assemble it with the real vasm.
- Run Hatari headless, inject keys, produce screenshots.
- Disassemble, write tools (unpacker, extractor, targeted emulator).
- Document what it found and prepare a package ready to copy to the machine.

## What it cannot do alone

- Try on a real machine: that is up to you, with a precise list (`TO_TEST.TXT`).
- Read a site forbidden to its reading tool, or reach a closed network.
- Remember a previous session: a fresh workspace is empty.

## Temporary workspace

Everything installed or downloaded disappears at some point. Therefore:

1. keep the **repository** up to date (code, docs, state file);
2. join each session with: repository (zip), TOS ROMs, `vasm.tar.gz`, the binary under study;
3. run `scripts/setup-dev.sh` then `scripts/smoke-test.sh`.

## Claude.ai and Claude Code

- **Claude.ai (projects)**: cloud shell and tools; the project's documents serve as memory
  shared between conversations. Hatari can be installed there (after `apt-get update`).
- **Claude Code** on your machine: direct access to your files and ROMs; installing Hatari,
  Xvfb and the dependencies remains to be done on that machine; `CLAUDE.md` is read
  automatically at the repository root.

## Cloud sessions (Claude Code on the web)

Observed limits and habits:

- the container can be reset **in the middle of a session**: files sent by the user and
  unpushed work disappear. Push often; if files are gone, ask for them again;
- the session's git proxy may refuse to push tags and to delete remote branches: Claude gives
  the command to the user (`git tag -a v1.0.1 <commit> -m …` then `git push origin v1.0.1`),
  after pushing the commit that carries that version's MD5;
- GitHub through the MCP tools (pull requests, merges); merge only on the user's go-ahead,
  after the real-machine trial;
- a SessionStart hook running `scripts/setup-dev.sh` reinstalls the tools at every session;
- files the user sends (ROMs, game) arrive in an uploads folder: move them to a fixed folder
  next to the repository, outside git;
- long Hatari runs go to the background, with a wait loop on the process (`until ! pgrep -x
  hatari; do sleep 3; done`); a chain of `sleep` calls may be refused;
- deliverables (zip, screenshots) go in the session's scratchpad and are sent as files; the
  zip may contain the patched game, the repository never does;
- throw-away scripts (applying a trial patch to a known image, measurements) live in the
  session's temporary folder, not in the repository;
- without the original input file, work on a published output with a known MD5, and label
  every checksum computed that way "to re-check";
- the container is fresh at every session: `apt-get update && apt-get install hatari xvfb
  xdotool` (Hatari 2.4.1), vasm built from source by `get-vasm.sh`; without ROMs, EmuTOS
  (`docs/04`);
- the network goes through a proxy that, in the JOYTEST session (Nov 2026), let through
  SourceForge (EmuTOS) and the vasm site, unlike the claude.ai allowlist of `docs/01`: try
  before concluding;
- another of the user's repositories can be added to the session on request;
- the repository's `CLAUDE.md` is loaded automatically: put there what a new session needs
  (install commands, ROM fallback, how to run the tests, known pitfalls).

## Diagnosing a hardware difference

When the real machine does something Hatari does not:

1. add a **diagnostic display** to the program: raw register values, the same read done
   several ways (order, delay);
2. build it, check it in Hatari, deliver it with a precise list of what to note (a photo of
   the screen is enough);
3. write the conclusion in the project notes and in `docs/05`/`docs/06`;
4. remove the diagnostic display once the cause is known, and keep the read that works.

## Project documents = memory

For each piece of work, keep in the project:

- `README`: goal, status;
- `METHODOLOGY`: how we proceed;
- `CODE_MAP`: map of the code;
- `REPRISE` / state: where we stopped, what is verified or not;
- `VERSIONS`: one numbered section per change, with the measurements, the trials and the
  real-machine feedback; the other documents point to it (`§25`).

Claude re-reads these documents at the start of a session; the result is much better than a
long conversation.

## Credits and names

Ask the user how they want to be credited in the distributed texts, and use only that (a
handle rather than a civil name, if that is their choice). Typical lines: "Reverse engineering
and code: Claude AI (Anthropic)." and "Game design, testing and additional graphics: <handle>."
Record the decision in the project's `CLAUDE.md`, as well as the user's other decisions
("no UPX for the game"…), so that a later session does not propose them again.

## Organising a long project (lessons from Bubble Bobble)

Over dozens of sessions and versions, this organisation kept the work under control:

- **One ticket per defect** reported from a real machine, with the analysis; a fix branch;
  Claude proposes the branch and the target version, **the user decides** what is merged and
  when a version is built. No zip at every bug: feedback accumulates.
- **Numbered versions** (X.Y.Z) shown on screen; trial builds of a branch are sent separately,
  keep the version number and do not go into the release folder.
- **`TO_TEST.TXT`** (ASCII, CR/LF) lists only the current version's numbered checks; the user
  answers point by point ("1 OK, 2 not tested…"), which becomes the next state.
- **State section in `CLAUDE.md`** ("where we are": version on the main branch, branches,
  open tickets, what is verified on which machine, what is not): updated at every delivery,
  read first by a new session.
- **Closing tickets** with a comment giving the version and what remains unverified.
- The user may ask for small changes "directly on the main branch, no ticket": keep both
  modes in the rules.
- Ask the user for **fast forward and snapshots** in Hatari: tests become cheap enough to run
  after every change.

## Honest reporting

What the user must always be able to read:

- **verified**: tool + environment ("`cmp` identical", "Hatari 2.4.1 TOS 1.04"),
- **not verified**: real machine, other TOS versions,
- **unknown**: "I don't see the cause; here is what has been ruled out".

## Request templates

**Understand a binary**
> Here is `PROG.PRG`. Read `docs/03-reverse-engineering.md`. Inspect the header, tell me whether it
> is packed, unpack it, then produce a source that reassembles identically. Report the code
> coverage and what remains unclassified.

**Write a program**
> Write in 68000 (vasm) a program that … Test it under the 4 TOS versions with
> `scripts/smoke-test.sh`, number the version 0.0.1, and prepare a zip with `TO_TEST.TXT` in ASCII.

**Modify a program**
> First make the source identical to the original (`cmp`). Then add the modification behind
> `ifd OPTION`: the default build must remain identical.

**Measure**
> Measure the frame rate at 50 Hz with the real TOS 1.04 (not EmuTOS). Give the method and the numbers.

**Resume**
> Resume the project with `CLAUDE.md` and the attached repository state; install the environment,
> rerun the checks, then continue from `REPRISE`.
