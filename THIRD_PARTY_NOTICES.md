# Third-party notices and source provenance

Update_Most is an **unofficial**, substantially **AI-assisted** project. This file distinguishes architectural references, read-only external indexes, independently authored core packages, and code actually contained in this repository.

**Project-authored Update_Most code is GPL-3.0-only.** See [LICENSE](LICENSE). That choice does **not** automatically confer rights to use or redistribute other people's source, binaries, or firmware. An open GitHub repository, downloadable asset, or matching checksum is not a redistribution license.

## MiSTer ecosystem: studied, not copied

- **[MiSTer Update All](https://github.com/theypsilon/Update_All_MiSTer)** — José Manuel Barroso Galindo and contributors, **GPL-3.0**. Architectural inspiration for database selection, user-facing configuration, and maintenance workflows. **No code copied into Update_Most.**
- **[MiSTer Downloader](https://github.com/MiSTer-devel/Downloader_MiSTer)** — MiSTer-devel contributors, **GPL-3.0**. Reference for installer integrity validation, update checking, custom databases, and safe managed files. **No source code copied into Update_Most.**
- **[BiosDB_MiSTer](https://github.com/ajgowans/BiosDB_MiSTer)** — ajgowans, **MIT**. The application reads a remote `external_files.csv` database of file names, URLs, sizes, and MD5 digests. **Its source/database is not vendored.** The upstream MIT license applies to the index code/data, **not necessarily to commercial firmware images linked in that index**. The original repository and license are credited here.

GPL-3.0 project sources must not be copied without a provenance and license review even though Update_Most now also uses GPL-3.0-only. A matching license is **necessary but not sufficient**: copyright notices, authorship, version-specific conditions, modifications, source availability and any separately licensed components still need checking. If upstream code is added later, identify it by filename and commit and include mandatory notices.

## Game Bub and externally maintained cores

- **[Game Bub](https://github.com/elipsitz/gamebub)** — Eli Lipsitz and contributors. Core loading format, firmware requirements, and published metadata were consulted; no framework/firmware code is vendored.
- [danisla/gamebub-nes](https://github.com/danisla/gamebub-nes) — NES / Famicom core; GPL-3.0 (GitHub license metadata).
- [danisla/gamebub-snes](https://github.com/danisla/gamebub-snes) — SNES core; GPL-3.0.
- [Wenwald/gamebub-2600](https://github.com/Wenwald/gamebub-2600) — Atari 2600; MIT.
- [danisla/gamebub-pico8](https://github.com/danisla/gamebub-pico8) — PICO-8; MIT.
- [alanswx/ColecoVision_GameBub](https://github.com/alanswx/ColecoVision_GameBub) — ColecoVision; GPL-3.0.
- [alanswx/Apple-IIgs_GameBub](https://github.com/alanswx/Apple-IIgs_GameBub) — Apple IIgs; GPL-3.0.
- [danifunker/MacLC_GameBub](https://github.com/danifunker/MacLC_GameBub) — Macintosh LC; GPL-3.0-or-later (project README).
- [alanswx/MCR_GameBub](https://github.com/alanswx/MCR_GameBub) — Bally Midway MCR arcade; repository license not independently resolved for this notice. **No code imported.** The MCR fixed `ssio.prom` and user-selected game ROM slots are described in [docs/mcr-arcade.md](docs/mcr-arcade.md), based on user-provided file metadata and published v0.6.0 core metadata; the uploaded `files.json` is not copied into this repository.
- [alanswx/Universal_GameBub](https://github.com/alanswx/Universal_GameBub) — Universal arcade; repository license not independently resolved for this notice. **No code imported.**
- [czarroland/gamegear-bub](https://github.com/czarroland/gamegear-bub) — Sega Game Gear / Master System; GPL-3.0.
- **Kitrinx** — credited for the Game Bub Neo Geo Pocket Color and Tiger Game.com cores. Their supplied `core.json` described GPL-3.0-only; `files.json` established BIOS filenames and sizes. These original files are **not included verbatim**. Synthetic test fixtures reproduce only the needed interface details, not the FPGA source.

The catalog stores links and facts about release packages; it does not embed FPGA core RTL or authorize copying games. External FPGA release ZIPs remain subject to each author's terms and any bundled dependency licenses. Version labels in catalog entries are not universal indicators of hardware maturity.

### Firmware and arcade source references added for management workflows

- The official stable UF2 is fetched from [elipsitz/gamebub releases](https://github.com/elipsitz/gamebub/releases) and checked against GitHub's asset digest and UF2 structure. The v1.1-beta2 core-loading UF2 is fetched from [danisla/gamebub-nes v1.0.0](https://github.com/danisla/gamebub-nes/releases/tag/v1.0.0), also listed with the same SHA-256 in [danisla/gamebub-snes v1.0.0](https://github.com/danisla/gamebub-snes/releases/tag/v1.0.0). No UF2 bytes are committed here.
- Update_Most offers SHA-256-pinned, unmodified offline HTML builders from [MCR_GameBub commit a47b413](https://github.com/alanswx/MCR_GameBub/commit/a47b413b533e750978761d52efa4fdf4c278e2cb) and [Universal_GameBub commit d76c093](https://github.com/alanswx/Universal_GameBub/commit/d76c093bf77ecaa49ea54657d71cdc31a22797fd). The HTML is downloaded directly from the authors' repositories to the user's selected folder; it is not vendored in this repository.
- [databases/arcade_images.json](databases/arcade_images.json) contains only game names, output filenames, sizes and checksums extracted from those same authors' `gamedb/games.json` files at the pinned commits. It contains no game, PROM, sample or builder code bytes. The checksums identify exact compatible image revisions; they do not grant rights to obtain or distribute game content.

## Source inclusion policy

1. Before importing a third-party component, document **author, repository, source URL, exact commit/tag, original license, affected files, and use case**.
2. Confirm **the file's actual license** and compatibility with GPL-3.0-only; a repository license alone may not cover every submodule, BIOS, asset, or contributor.
3. Carry forward copyright statements, licenses, attribution, notices, and relevant modifications. Record exact incorporated upstream files in this notice.
4. Distribute source and comply with GPL obligations for any permitted merged or derivative work. **Do not copy upstream code solely because both projects use GPL-3.0**.
5. Prefer independent implementations or links when provenance or permission is unresolved.
6. Disclose AI-written/AI-assisted contributions, including the tool involved; never present upstream work as generated by AI.

**Commercial firmware and game ROMs:** Neither the project license nor BiosDB's MIT license grants rights to download or distribute firmware. The program currently reads an unverified public index. See [issue #2](https://github.com/czarroland/update_most/issues/2) for the required rights/default review.
