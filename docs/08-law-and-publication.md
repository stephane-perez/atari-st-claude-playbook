# 08 — Law and publication

> I am not a lawyer. This document lists prudent precautions; it does not replace legal advice,
> which depends on your country.

## Simple rule

A public repository contains **only what belongs to you** or what is freely redistributable:
your tools, your documentation, your original examples, your method.

## What stays out of the repository

- TOS ROMs (Atari copyright);
- commercial games, programs and floppies;
- disassemblies or reconstructed sources of a commercial program (derivative work);
- images, sounds, texts extracted from a program;
- excerpts of original bytes (even short ones, in tests);
- any circumvention of protection (dongle, copy protection).

`.gitignore` blocks common extensions (`*.img`, `*.rom`, `*.st`, `*.msa`, `tos/`…): it is a
safety net, not a guarantee. Check before pushing:

```sh
git status
git log --all --name-only --format= | sort -u     # no original file must appear
```

## How to document without publishing originals

- Describe the **method** and its results (coverage percentage, sizes, flags), not the content.
- Identify original files by their **hash** (SHA-256) rather than including them:
  "this patch applies to the executable with SHA-256 …".
- Start from an **original example** (like `examples/hello`).
- Prefer publishing a **generic tool** (recursive disassembler, unpacker) rather than the
  disassembly of a title.

## If you want to publish work on a game

1. Contact the rights holder (some grant permission, notably for old games).
2. Publish **light notes** (file format, structure) rather than the code.
3. Do not redistribute the original; provide a **patch** that applies to the original the user
   owns, after checking the hash.

## Repository licence

The repository is under the MIT licence (see `LICENSE`): this covers **your** files, not those
of third parties that you might put in by mistake.

Exception, deliberate and documented: `third_party/` holds files redistributed under their own
licence (currently the unmodified vasm source archive, non-commercial use). Each sub-folder
states the licence and the SHA-256 of the original; such a file is never modified in place.

## Reminder for Claude

Do not include in a public repository or delivery archive: ROMs, games, disassemblies of
commercial programs. If the user asks for it, explain why and propose the alternative (hash,
patch, notes).
