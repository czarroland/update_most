# Update_Most

A community-maintained updater for publicly released Game Bub FPGA cores and associated support files. Runs on a computer with Python 3.9+ (macOS, Linux or Windows PowerShell). This repository is an **initial public development baseline** based on v0.7 of the updater.

**Development disclosure:** Update_Most's implementation, tests, and documentation were written with substantial assistance from **OpenAI ChatGPT**, directed and reviewed by the maintainer. This is not a claim of independent human authorship. See [AI_DISCLOSURE.md](AI_DISCLOSURE.md).

**Third-party attribution:** The project takes architectural inspiration from MiSTer Update All and MiSTer Downloader, and reads URL/index information from `BiosDB_MiSTer`. We have not copied the GPL-3.0 MiSTer updater source into this project. Source, licenses, and attribution are documented in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The core and metadata projects remain the work of their respective authors.

## Current scope

- Download selected GitHub core release ZIPs using an editable catalog.
- Check archive hashes and Game Bub metadata, and install supported core directories on a microSD card.
- Track managed files and back up files before approved replacement.
- Inspect BIOS requirements, import user-supplied files, and use curated references to the MiSTer community BIOS index.
- Preserve unrelated ROMs and saves; the program does not format the card or flash firmware.

**Verification status:** Offline unit tests use synthetic fixtures and mocked downloads. Release listings and published metadata were checked in October 2026, but the published binaries and BIOS archives have **not been independently downloaded** in the test environment, and this repository has **not been verified on physical Game Bub hardware**. Features and external source availability can change; this is not a stable release announcement.

## Install / run

Clone the repository or download its files. A terminal with Python 3.9 or newer is required.

```sh
# macOS / Linux — replace with the real SD-card mount point
./update_most.sh --sd /Volumes/GAMEBUB --init
./update_most.sh --sd /Volumes/GAMEBUB

# Inspect catalog without writing
python3 update_most.py --list
python3 update_most.py --sd /Volumes/GAMEBUB --dry-run
```

Windows PowerShell:

```powershell
.\update_most.ps1 --sd 'E:\' --init
.\update_most.ps1 --sd 'E:\'
```

Use `--init` only for an initial prepared SD card. The SD card must already be correctly formatted; this tool does not format it. Back up your card before using a development build.

By default the script reads **its bundled `catalog.json`**. The hosted-catalog feature is still opt-in; to use a GitHub-hosted catalog, pass `--catalog https://raw.githubusercontent.com/.../catalog.json`. We will make the repository-hosted catalog the default only after the release and integrity policy is reviewed.

## BIOS handling and licensing

The v0.7 baseline has automatic MiSTer community-index BIOS fetching enabled by default when the corresponding file is missing. Users can disable it with `--no-mister-bios` or bypass all BIOS handling with `--skip-bios`. Community URLs and checksums do **not** establish that copyrighted BIOS images are licensed for redistribution; do not interpret this project as providing such permission. **Review of these sources and the download-default policy remains a release blocker.** No BIOS or commercial game images are included in this repository.

## Tests

```sh
python3 -m unittest discover -s tests -v
python3 update_most.py --list
python3 verify_all.py --help
```

The verifier can fetch core *release ZIPs* and simulate installation in a temporary folder; running it does not test hardware. See `verify_all.py --help` for options.

## Contributions and licensing

See [CONTRIBUTING.md](CONTRIBUTING.md) for submission requirements and [ROADMAP.md](ROADMAP.md) for planned development. The repository's existing LGPL-2.1 license has been retained for project-authored code, pending formal provenance review. **That license does not relicense third-party cores, scripts, metadata, BIOS or ROMs.** We accept no copied third-party code without a documented compatible license and proper attribution.

Game Bub is a separate project by [Eli Lipsitz](https://github.com/elipsitz/gamebub). This updater is an unofficial community project.