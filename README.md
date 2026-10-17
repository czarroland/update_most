# Update_Most

Update_Most is an **unofficial, community-maintained Game Bub core updater**. It downloads published FPGA core release archives and prepares a user-selected microSD card on **macOS, Linux, and Windows** using **Python 3.9+**. This repository is an early development baseline; hardware compatibility and network download behavior have not been comprehensively verified.

**Development disclosure:** The project was written with substantial assistance from **OpenAI ChatGPT**, under the maintainer's direction and review. This includes code, tests, catalog work, documentation, and proposed features. See [AI_DISCLOSURE.md](AI_DISCLOSURE.md).

**License:** Original Update_Most source code and documentation in this repository are published under the **GNU General Public License, version 3 only (GPL-3.0-only)**. See [LICENSE](LICENSE). This license applies only to material the Update_Most contributors have rights to license. It does **not** relicense external Game Bub cores, firmware, BIOS, MAME ROMs, upstream databases, or other third-party material.

**Upstream attribution:** The design was informed by [MiSTer Update All](https://github.com/theypsilon/Update_All_MiSTer) and [MiSTer Downloader](https://github.com/MiSTer-devel/Downloader_MiSTer), both GPL-3.0 projects. Their source code has **not** been copied into this repository. The updater can consult [BiosDB_MiSTer](https://github.com/ajgowans/BiosDB_MiSTer) (MIT) by URL for BIOS-index metadata. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for credits, license boundaries, and per-core provenance.

## Implemented behavior

- Reads a JSON catalog of reviewed core release sources.
- Downloads GitHub release ZIP archives, checks release SHA-256 values where available, and validates Game Bub core metadata and hardware targets.
- Installs to `/cores/<core-id>/`, backs up managed files before replacement, and keeps a record of managed files.
- Handles BIOS paths, local BIOS imports, selected MiSTer community BIOS database entries, and pinned Archive.org ColecoVision OS-7 and Macintosh LC ROMs.
- Preserves unrelated saves and ROM files. Does **not** format a card or flash the handheld firmware.
- Allows a local catalog (default) or explicitly supplied HTTPS catalog.
- Combines separately identified community databases with conflict checks; an interactive menu saves preferences on the selected card.
- Checks available versions without package downloads, verifies tracked files, restores pre-update snapshots, and removes only verified managed core files.
- Produces a read-only card health report covering managed cores, required BIOS files, prepared arcade images, and the reported handheld firmware version.
- Reuses SHA-256-verified release packages from an SD-card cache and checks free space before installation.
- Separately downloads the official stable Rev4 UF2 or the pinned v1.1-beta2 core-loading UF2 to a computer folder; firmware is never flashed during a core update.
- Automatically downloads checksum-pinned MAME ZIPs from Archive.org and prepares author-verified MCR and Universal arcade images when those cores are installed. The authors' offline builders remain available.
- Runs offline unit tests on synthetic data. Includes a core archive verification utility.
- Validates the MCR SSIO timing PROM from the same Archive.org collection against its pinned hash and installed core metadata.

## Requirements

Python 3.9 or later, a computer with Internet access for core downloads, and a Game Bub-compatible microSD card. **Back up the card before the first development-build run.** Firmware supporting SD-card core loading is required for third-party cores; this program does not install it.

## Usage

### Interactive menu

Run `python3 update_most.py --menu` in a terminal. The menu suggests likely mounted Game Bub cards, then offers **Update everything**, update checks, a category-filtered core browser, BIOS management, a card health report, verification, restore, uninstall, safe eject, and settings. The browser shows the installed version, firmware requirement, current update/README check, and author release notes before installing a selected core. You can provide `--sd /path/to/card` to skip card selection. Menu preferences are saved as `.update_most/settings.json` on the chosen card. The updater does not format cards.

New cards default to the beta catalog channel so Update everything includes third-party cores that require the v1.1 beta firmware. This does not change the handheld's firmware; use Settings to switch the catalog channel to stable if desired.

On macOS the menu lists mounted external FAT32 cards, including cards without an Update_Most layout, and shows their size and partition scheme when disk metadata is available. It offers to create `cores`, `system`, and `roms` on a selected new card. The updater rejects writes to a macOS mounted volume when disk metadata shows a filesystem other than FAT32 or a partition table other than MBR. On other platforms, confirm the card format yourself using the [Game Bub card requirements](https://docs.gamebub.net/user-guide/playing-games/). Detection still requires you to select the destination; it never formats a drive.

After Update everything, choose **Safely eject card** in the menu or run `python3 update_most.py --sd /path/to/card --eject`. The eject action requires a selected removable mount. It uses macOS `diskutil`, Linux `udisksctl`, or the Windows removable-drive Eject action and reports a failure if the operating system cannot release the card.

### Firmware needed for third-party cores

The official stable release is currently v1.0.2. The [NES core author's README](https://github.com/danisla/gamebub-nes#install) identifies **v1.1-beta2 or newer** as the first Rev4 firmware that lists SD-card cores, and the [NES v1.0.0 release](https://github.com/danisla/gamebub-nes/releases/tag/v1.0.0) carries `gamebub-rev4_v1.1-beta2.uf2`. The same UF2 and SHA-256 appear in the [SNES author's release](https://github.com/danisla/gamebub-snes/releases/tag/v1.0.0). Update_Most pins that beta asset to SHA-256 `7c9ae9f4e0a80b59bcb7abc6baa8a3e7379ae14b5259b7bec76e6b0e559f4937`.

```sh
python3 update_most.py --firmware-check --firmware-channel core-loading-beta
python3 update_most.py --firmware-download ~/Downloads --firmware-channel core-loading-beta
```

The program verifies the GitHub release digest and UF2 block structure before saving the file. The stable channel remains separately available with `--firmware-channel stable`. Follow the [Game Bub USB firmware update procedure](https://docs.gamebub.net/user-guide/firmware-updates/) to install a selected UF2; the SD updater cannot read the handheld's installed firmware version from the card. `--check-only` reads each GitHub core README and prints its firmware notes alongside the catalog requirement. Enter the version shown in **Settings → About** to get a compatibility report:

```sh
python3 update_most.py --sd /Volumes/GAMEBUB --check-only --installed-firmware v1.1-beta2
```

The interactive menu can save that reported version in the card's settings. If it is unknown, the check says so instead of assuming that stable firmware can load third-party cores.

### Arcade ROM preparation

```sh
python3 update_most.py --sd /Volumes/GAMEBUB --arcade-auto
python3 update_most.py --sd /Volumes/GAMEBUB --arcade-auto --arcade-system universal --arcade-game ladybug
```

The normal **Update everything** action runs this automatically after core and BIOS updates for installed MCR and Universal cores. The first run downloads only needed source ZIPs from the [MAME 0.209 Archive.org collection](https://archive.org/details/MAME209RomsOnlyMerged) and three files from its [newer merged collection](https://archive.org/details/mame-roms-merged_). Every source ZIP is checked against its pinned Archive.org SHA-1 and every prepared image against the [core authors' output hashes](databases/arcade_images.json). We verified all 19 MCR and 57 Universal images. The MCR timing PROM is installed automatically only when the installed core confirms its destination. Existing differing card files are preserved. Use `--skip-arcade` to omit this step in an Update everything run.

The offline builder and prepared ZIP import are still available:

```sh
python3 update_most.py --arcade-builder mcr --output ~/Downloads
python3 update_most.py --arcade-builder universal --output ~/Downloads
python3 update_most.py --sd /Volumes/GAMEBUB --arcade-import ~/Downloads/MCR-GameBub-ROMs.zip --arcade-system mcr
python3 update_most.py --sd /Volumes/GAMEBUB --arcade-import ~/Downloads/Universal-GameBub-ROMs.zip --arcade-system universal
```

The builder commands save SHA-256-pinned, self-contained offline tools published by the [MCR](https://github.com/alanswx/MCR_GameBub/tree/main/web) and [Universal](https://github.com/alanswx/Universal_GameBub/tree/main/web) core authors. The import commands verify each prepared `.rom` image before installing it. The builders run locally and do not upload files.

### macOS or Linux

```sh
# Inspect bundled catalog, without accessing the card
python3 update_most.py --list

# An existing correctly formatted card; replace with its mount path
./update_most.sh --sd /Volumes/GAMEBUB --init
./update_most.sh --sd /Volumes/GAMEBUB

# Check planned changes without writing files
./update_most.sh --sd /Volumes/GAMEBUB --dry-run

# Check versions without downloading ZIPs or writing to the card
./update_most.sh --sd /Volumes/GAMEBUB --check-only

# Verify all files recorded by Update_Most
./update_most.sh --sd /Volumes/GAMEBUB --verify-installation

# Read-only readiness report, using the version shown in Settings > About
./update_most.sh --sd /Volumes/GAMEBUB --health --installed-firmware v1.1-beta2

# Restore a prior managed version or remove one managed core
./update_most.sh --sd /Volumes/GAMEBUB --restore-core NES
./update_most.sh --sd /Volumes/GAMEBUB --uninstall-core NES
```

On Linux the SD mount path will differ, for example `/run/media/$USER/GAMEBUB`. Only use `--init` when preparing a previously unrecognized card. The updater does not format storage. The health report does not access the network or change files; it reports missing required BIOS/PROM files and distinguishes verified managed cores from other cores already on the card. It checks arcade images against the pinned game manifest and flags firmware as unknown unless you supply a version or save one in the menu.

### Windows PowerShell

```powershell
.\update_most.ps1 --sd 'E:\' --init
.\update_most.ps1 --sd 'E:\'
```

An explicitly selected SD card mounted at a non-system drive root (for example
`E:\\`) is supported. The system drive, the current user's home drive,
Python's installation drive, Windows' installation drive, and network-share
roots are refused. **Confirm the drive letter** before using `--init`;
initialization creates directories but does not format the card.

### Experimental releases and BIOS handling

```sh
python3 update_most.py --sd /Volumes/GAMEBUB --channel beta
python3 update_most.py --sd /Volumes/GAMEBUB --list-bios
python3 update_most.py --sd /Volumes/GAMEBUB --bios-only --bios-dir ~/My-BIOS
python3 update_most.py --sd /Volumes/GAMEBUB --no-mister-bios
```

**BIOS source caution:** The existing v0.7 behavior fetches matching entries from the public MiSTer community BIOS URL index **by default**, when missing. Users can disable this with `--no-mister-bios` or skip BIOS handling with `--skip-bios`. The linked firmware images may be copyrighted; being listed in a public index is **not** a grant of permission to download or redistribute them. The per-source authorization and safe default policy are under review in [issue #2](https://github.com/czarroland/update_most/issues/2). The repository includes **no BIOS or commercial game image bytes**.

ColecoVision OS-7 and Macintosh LC ROMs now use pinned ZIP members from the Archive.org MAME 0.209 collection. The ZIP and extracted ROM both require exact SHA-256 matches before installation. The Mac LC ROM matches the [$67C / $350EACF0 revision documented by the core author](https://github.com/danifunker/MacLC_MiSTer#rom); the OS-7 ROM matches the [MAME ColecoVision driver](https://github.com/mamedev/mame/blob/master/src/mame/coleco/coleco.cpp). Existing differing BIOS files are preserved.

## Catalog and community contributions

The tracked catalog is [catalog.json](catalog.json). The default program behavior currently uses this **bundled local file**, so a newer repository catalog is not automatically adopted. Users who explicitly want the repository-hosted version can pass:

```sh
python3 update_most.py --sd /Volumes/GAMEBUB \
  --catalog https://raw.githubusercontent.com/czarroland/update_most/main/catalog.json
```

The URL above references the current `main` catalog in this repository. Alternatively, the same repository catalog can be selected with `--catalog-track github`; `--catalog-track bundled` is the default. Selecting GitHub means trusting future catalog changes on the maintainer's main branch. The client validates the document and each downloaded core archive, but **the catalog itself is not yet signed or pinned to a fixed revision**.

Additional databases can be enabled with repeatable `--database /path/to/database.json` or `--database https://...` options, or through menu settings. Each additional schema-1 catalog needs a stable `database_id`; duplicate database IDs, core IDs, BIOS IDs, and BIOS destinations are rejected before updating. Local custom databases are reviewed by their user; remote database URLs are trust decisions because they can direct future downloads. For one core, use `--core ID`.

Restore requires a backup created by this version after an earlier managed install. Older backups have no restore manifest. Restore and uninstall refuse locally modified managed files, and uninstall leaves untracked ROMs, saves, and other user files in place. Update checks resolve release metadata but do not prove a release ZIP is valid or that a bitstream runs on hardware.

Catalog entries require attribution, a documented upstream source and a compatible Game Bub target. Run the catalog validator before submitting changes:

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

GitHub Actions runs the checks on macOS, Linux, and Windows. A separate **manually triggered** [core archive audit workflow](.github/workflows/verify-core-archives.yml) can verify release metadata or download and hash-check actual core ZIPs on a GitHub-hosted runner. Neither mode checks physical Game Bub behavior. See [MCR arcade requirements](docs/mcr-arcade.md). Unit tests use synthetic archives and mocked downloads; they are **not** hardware tests or proof of real remote server availability. Independent ZIP-download verification and Game Bub Rev4 smoke tests remain open in [issue #3](https://github.com/czarroland/update_most/issues/3).

## License and project status

Copyright (C) 2026 Update_Most contributors. Project-authored content is distributed under **GPL-3.0-only** with **no warranty**; see [LICENSE](LICENSE). External projects are separately licensed by their authors. References to MiSTer, Game Bub, and individual core authors do not imply endorsement.

[ROADMAP.md](ROADMAP.md) documents proposed development work without a release commitment. [Game Bub](https://github.com/elipsitz/gamebub) is developed by Eli Lipsitz and contributors; this updater is independent of that project.
