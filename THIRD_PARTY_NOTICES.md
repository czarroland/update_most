# Third-party notices and provenance

This document records references and third-party work used or consulted by Update_Most. **A link, filename, hash, or public availability is not permission to redistribute copyrighted software or ROM images.** This repo does not include commercial BIOS or game ROM bytes.

## MiSTer updater ecosystem (architecture and reference only)

- **[Update All](https://github.com/theypsilon/Update_All_MiSTer)** — by José Manuel Barroso Galindo / community contributors; **GPL-3.0**. Studied as a reference for database selection, configuration and user workflows. **No source code copied into Update_Most.** GPL-3.0 code must not be pasted into the LGPL-2.1 codebase without a documented licensing decision.
- **[Downloader_MiSTer](https://github.com/MiSTer-devel/Downloader_MiSTer)** — MiSTer-devel contributors; **GPL-3.0**. Studied for validation concepts, integrity modes, custom databases and transactional updates. **No source code copied into Update_Most.**
- **[BiosDB_MiSTer](https://github.com/ajgowans/BiosDB_MiSTer)** — database curated by ajgowans; **MIT**. Update_Most reads the upstream `external_files.csv` as a remote URL, size and checksum index. That database **is not bundled or mirrored** in this repository. The MIT license applies to the database project, not necessarily to linked third-party firmware images.

## Game Bub and core developers

- **[Game Bub](https://github.com/elipsitz/gamebub)** by Eli Lipsitz and contributors. Core packaging and metadata documentation informed path checks. Game Bub firmware and framework sources are **not included** in Update_Most.
- Core and/or release metadata is catalogued from [danisla/gamebub-nes](https://github.com/danisla/gamebub-nes), [danisla/gamebub-snes](https://github.com/danisla/gamebub-snes), [danisla/gamebub-pico8](https://github.com/danisla/gamebub-pico8), [Wenwald/gamebub-2600](https://github.com/Wenwald/gamebub-2600), [alanswx/ColecoVision_GameBub](https://github.com/alanswx/ColecoVision_GameBub), [alanswx/Apple-IIgs_GameBub](https://github.com/alanswx/Apple-IIgs_GameBub), [danifunker/MacLC_GameBub](https://github.com/danifunker/MacLC_GameBub), [alanswx/MCR_GameBub](https://github.com/alanswx/MCR_GameBub), [alanswx/Universal_GameBub](https://github.com/alanswx/Universal_GameBub), and [czarroland/gamegear-bub](https://github.com/czarroland/gamegear-bub).
- **Kitrinx** is credited as the author of the Neo Geo Pocket Color and Tiger Game.com cores. Game Bub metadata provided for mapping BIOS paths described those cores as GPL-3.0-only. The provided metadata files **are not included verbatim** here; tests construct independent synthetic metadata with matching required filenames and sizes. Neither Kitrinx FPGA designs nor BIOS bytes are included.

Each core is separately licensed by its author. Listing a release is not an assignment of copyright, endorsement by the author, license grant for related ROMs, or a claim that its package has been tested on device.

## Code use policy

1. Record the upstream project, author, exact file or component, upstream commit/tag, license and copyright notices **before copying code**.
2. Check compatibility with the repository license and any additional source obligations, obtaining explicit permission when required.
3. Preserve notices and required license texts when shipping permitted third-party material.
4. If provenance, authorship or licensing cannot be established, use an independent implementation, data-only references, or omit the material pending review.
5. Mark AI-written work as AI-assisted. Do not use AI generation to conceal copied third-party code.

The existing repository license is LGPL-2.1. It applies only where the project may legally grant that license; it does not cover the external projects listed above. The exact legal obligations of any future source import must be reviewed before merging it.