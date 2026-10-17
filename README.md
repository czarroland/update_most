# Update_Most

Update_Most is an **unofficial, community-maintained Game Bub core updater**. It downloads published FPGA core release archives and prepares a user-selected microSD card on **macOS, Linux, and Windows** using **Python 3.9+**. This repository is an early development baseline; hardware compatibility and network download behavior have not been comprehensively verified.

**Development disclosure:** The project was written with substantial assistance from **OpenAI ChatGPT**, under the maintainer's direction and review. This includes code, tests, catalog work, documentation, and proposed features. See [AI_DISCLOSURE.md](AI_DISCLOSURE.md).

**License:** Original Update_Most source code and documentation in this repository are published under the **GNU General Public License, version 3 only (GPL-3.0-only)**. See [LICENSE](LICENSE). This license applies only to material the Update_Most contributors have rights to license. It does **not** relicense external Game Bub cores, firmware, BIOS, MAME ROMs, upstream databases, or other third-party material.

**Upstream attribution:** The design was informed by [MiSTer Update All](https://github.com/theypsilon/Update_All_MiSTer) and [MiSTer Downloader](https://github.com/MiSTer-devel/Downloader_MiSTer), both GPL-3.0 projects. Their source code has **not** been copied into this repository. The updater can consult [BiosDB_MiSTer](https://github.com/ajgowans/BiosDB_MiSTer) (MIT) by URL for BIOS-index metadata. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for credits, license boundaries, and per-core provenance.

## Implemented behavior

- Reads a JSON catalog of reviewed core release sources.
- Downloads GitHub release ZIP archives, checks release SHA-256 values where available, and validates Game Bub core metadata and hardware targets.
- Installs to `/cores/<core-id>/`, backs up managed files before replacement, and keeps a record of managed files.
- Handles BIOS paths, user-supplied BIOS imports, and selected MiSTer community BIOS database entries.
- Preserves unrelated saves and ROM files. Does **not** format a card, download games, or flash the handheld firmware.
- Allows a local catalog (default) or explicitly supplied HTTPS catalog.
- Runs offline unit tests on synthetic data. Includes a core archive verification utility.

## Requirements

Python 3.9 or later, a computer with Internet access for core downloads, and a Game Bub-compatible microSD card. **Back up the card before the first development-build run.** Firmware supporting SD-card core loading is required for third-party cores; this program does not install it.

## Usage

### macOS or Linux

```sh
# Inspect bundled catalog, without accessing the card
python3 update_most.py --list

# An existing correctly formatted card; replace with its mount path
./update_most.sh --sd /Volumes/GAMEBUB --init
./update_most.sh --sd /Volumes/GAMEBUB

# Check planned changes without writing files
./update_most.sh --sd /Volumes/GAMEBUB --dry-run
```

On Linux the SD mount path will differ, for example `/run/media/$USER/GAMEBUB`. Only use `--init` when preparing a previously unrecognized card. The updater does not format storage.

### Windows PowerShell

```powershell
.\update_most.ps1 --sd 'E:\' --init
.\update_most.ps1 --sd 'E:\'
```

### Experimental releases and BIOS handling

```sh
python3 update_most.py --sd /Volumes/GAMEBUB --channel beta
python3 update_most.py --sd /Volumes/GAMEBUB --list-bios
python3 update_most.py --sd /Volumes/GAMEBUB --bios-only --bios-dir ~/My-BIOS
python3 update_most.py --sd /Volumes/GAMEBUB --no-mister-bios
```

**BIOS source caution:** The existing v0.7 behavior fetches matching entries from the public MiSTer community BIOS URL index **by default**, when missing. Users can disable this with `--no-mister-bios` or skip BIOS handling with `--skip-bios`. The linked firmware images may be copyrighted; being listed in a public index is **not** a grant of permission to download or redistribute them. The per-source authorization and safe default policy are under review in [issue #2](https://github.com/czarroland/update_most/issues/2). The repository includes **no BIOS or commercial game image bytes**.

## Catalog and community contributions

The tracked catalog is [catalog.json](catalog.json). The default program behavior currently uses this **bundled local file**, so a newer repository catalog is not automatically adopted. Users who explicitly want the repository-hosted version can pass:

```sh
python3 update_most.py --sd /Volumes/GAMEBUB \
  --catalog https://raw.githubusercontent.com/czarroland/update_most/main/catalog.json
```

The URL above references `main` **after** the current draft pull request is merged. Catalog entries require attribution, a documented upstream source and a compatible Game Bub target. Run the catalog validator before submitting changes:

```sh
python3 validate_catalog.py --catalog catalog.json
python3 -m unittest discover -s tests -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the metadata, author/AI disclosure and licensing requirements. No external code, ROM, firmware, or BIOS should be embedded in catalog submissions without confirmed rights.

## Tests and verification

```sh
python3 -m unittest discover -s tests -v
python3 validate_catalog.py --catalog catalog.json
python3 update_most.py --list
python3 verify_all.py --help
```

GitHub Actions runs the checks on macOS, Linux, and Windows. Unit tests use synthetic archives and mocked downloads; they are **not** hardware tests or proof of real remote server availability. Independent ZIP-download verification and Game Bub Rev4 smoke tests remain open in [issue #3](https://github.com/czarroland/update_most/issues/3).

## License and project status

Copyright (C) 2026 Update_Most contributors. Project-authored content is distributed under **GPL-3.0-only** with **no warranty**; see [LICENSE](LICENSE). External projects are separately licensed by their authors. References to MiSTer, Game Bub, and individual core authors do not imply endorsement.

[ROADMAP.md](ROADMAP.md) documents proposed development work without a release commitment. [Game Bub](https://github.com/elipsitz/gamebub) is developed by Eli Lipsitz and contributors; this updater is independent of that project.
