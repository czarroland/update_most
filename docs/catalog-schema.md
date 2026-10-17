# Catalog metadata and source attribution

Update_Most uses an application-specific JSON catalog with `schema: 1` and an independently incremented `catalog_revision` (a positive integer). The schema denotes parser compatibility; `catalog_revision` denotes reviewed catalog changes. The original format is processed by `update_most.load_catalog`. An additional offline provenance check is provided by `validate_catalog.py`.

## Validate before submitting

```sh
python3 validate_catalog.py --catalog catalog.json
python3 -m unittest discover -s tests -v
```

This checks local JSON syntax and many metadata constraints without downloading anything. It **does not** establish that a release exists, its ZIP is safe, its FPGA bitstream runs on hardware, or its author permits a particular use.

## Core record requirements

```json
{
  "id": "Example.Core",
  "name": "Example Core",
  "category": "Console",
  "channel": "beta",
  "enabled": false,
  "hardware": ["gamebub_rev4"],
  "requires_firmware": "Relevant tested firmware version",
  "source": {
    "type": "github_release",
    "repo": "developer/repo-name",
    "asset": "example-v*.zip",
    "tag": "optional-tag"
  },
  "homepage": "https://github.com/developer/repo-name",
  "upstream": {
    "author": "Original author and contributors",
    "license": "license not verified",
    "reference_only": true
  }
}
```

`reference_only: true` means Update_Most is linking to **another developer's release**, rather than incorporating that project's source into the updater repository. Listing a core does **not** relicense its code or binaries.

If a core's license cannot be confirmed from its actual repository and files, use `license not verified`. Validation warns by default; `--require-verified-licenses` treats such warnings as errors.

The `source` object supports a GitHub release or a SHA-256-pinned direct HTTPS URL. The main updater validates the source and FPGA metadata before installation. Stable/beta channel labels describe catalog update selection, not necessarily the upstream developer's maturity or hardware-testing status.

## BIOS records

BIOS requirements have their own `bios` array and paths. Some entries reference MiSTer's **MIT-licensed** BiosDB_MiSTer index. That does not imply firmware copyright holders have allowed distribution. Never attach commercial ROMs or BIOS dumps in issues or pull requests. See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## Changing database formats

The application loader continues to accept historical `schema: 1` catalogs without a `catalog_revision` field for backward compatibility. New community catalog contributions must set `catalog_revision` to a positive integer; increment it when publishing revised source listings or other reviewable metadata. A revision bump does not independently update the Python client or authorize new source repositories. Do not repurpose core IDs or change required install paths silently. Any incompatible schema change needs a new parser schema, explicit migration tests, and updated tooling.

Do not silently modify the `schema` number, core IDs, or update state conventions. New catalog/database formats require migration code, tests and a versioning document. Additional schema-1 databases may be selected with `--database`; each needs a permanent `database_id` matching the same identifier rules as core IDs. A database cannot override a core ID, BIOS ID, or BIOS destination from another selected database. Database sources are selected by the user and are not signed.

## AI and license disclosure

Changes submitted with AI help must identify the tool, affected files and testing performed. Third-party code adaptation must identify the original authors, license, commit and files. Project-authored Update_Most code is GPL-3.0-only.
