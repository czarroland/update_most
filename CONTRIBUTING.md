# Contributing to Update_Most

Update_Most is a GPL-3.0-only, AI-assisted community utility. Please submit focused changes, tests, and enough source information to review what is being installed.

## Required disclosures

For every pull request:

- Identify whether **AI tools** helped write code, documentation, or tests; name the tool(s) and describe which parts were assisted.
- Identify **any third-party source or other protected material** used or adapted. Include repository URL, original author, file paths, commit/tag, original license and attribution requirements. If none was copied, say so.
- Confirm you have the rights to contribute your changes under **GPL-3.0-only**, or identify any exception before review.
- Describe what was tested, what was not tested, and any hardware requirements.

The maintainer will not merge unattributed source imports, undisclosed AI-derived changes, or packages containing commercial firmware/ROM data without permission. GPL-3.0-compatible source imports are not automatically acceptable: preserve notices and credit authors.

## Core catalog submissions

Provide a public upstream repository, exact release asset glob/tag, `core.json` ID, supported hardware target(s), and author/license provenance. Note required firmware, BIOS paths, optional resources, known limitations, and whether the release was independently verified on a real Rev4 device. Repository metadata is not a substitute for verification.

Each `cores[]` record carries an `upstream` object including `author`, `license` and `reference_only: true` to distinguish *catalog references* from material included in this repository. If a license is unknown, mark it **license not verified** instead of guessing. Do not claim redistribution rights because an asset is publicly downloadable.

## Testing

```sh
python3 validate_catalog.py --catalog catalog.json
python3 -m unittest discover -s tests -v
python3 update_most.py --list
```

Use **synthetic data** in tests. Do not upload BIOS bytes, copyrighted game ROMs, private SD-card files, passwords, credentials, or unrelated personal data.

## Release discipline

The updater must never silently erase user ROMs, saves, BIOS files, or firmware. Any new remote database should have documented trust boundaries, integrity checks, and compatibility behavior. Update [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [AI_DISCLOSURE.md](AI_DISCLOSURE.md) when sources or assisted development practices change.

## License

Copyright (C) 2026 Update_Most contributors. New original contributions are expected to be licensed under [GNU GPL version 3 only](LICENSE). External work retains its original copyrights and license requirements.
