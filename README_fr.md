# Atari ST + Claude : le manuel de bord

Tout ce qui a permis, au fil de plusieurs projets, d'écrire du 68000, de désassembler des
binaires Atari ST/STE/Mega STE/Falcon et de les tester, avec Claude : méthode, outils, pièges.

- **`CLAUDE.md`** : règles et mémo court (lu automatiquement par Claude Code).
- **`docs/`** : le détail (environnement, vasm, rétro-ingénierie, tests Hatari, matériel/TOS,
  pièges, études de cas, droit, travail avec Claude).
- **`tools/`** : `hatari_run.py` (Hatari sans écran), `hatari-joysticks.cfg` (joysticks au
  clavier), `mkst.py` (images FAT12), `prg_info.py` (inspecteur de PRG), `emu_snippets.py`
  (Capstone/Unicorn), `txt2st.py` (textes dans le jeu de caractères du ST), `packiff.py`
  (IFF ILBM recompressées en ByteRun1), `stx.py` (lecteur Pasti .STX), `unice.py`
  (décompresseur Pack-Ice 2.3x/2.40) et `unice_fuzz.py` (son test différentiel).
- **`scripts/`** : installation, vasm, test de bout en bout.
- **`examples/hello`** : exemple original minimal.

## Démarrage

```sh
sh scripts/setup-dev.sh [vasm.tar.gz]
cp /vos/ROM/*.img tos/        # ROM TOS : à fournir vous-même, jamais dans git
sh scripts/smoke-test.sh      # STF 1.04, STE 1.62, Mega STE 2.06, Falcon 4.04
make && make check
```

## Ce qui est vérifié, et ce qui ne l'est pas

Vérifié (Hatari 2.4.1, vasm 2.0f) : construction reproductible, image FAT12 valide
(`fsck.fat`), exemple lancé sous les quatre TOS. **Non vérifié sur machine réelle.**

## Ce qui n'est pas ici

ROM, jeux, désassemblages de programmes commerciaux, contournements de protection
(voir `docs/08-law-and-publication.md`). Les outils des projets passés ne sont pas inclus.

Licence : MIT. English version: [`README.md`](README.md).
