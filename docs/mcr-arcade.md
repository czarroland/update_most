# MCR arcade file requirements

This page documents the interface declared by a user-provided Bally Midway
MCR `files.json` and the published `alanswx/MCR_GameBub` core metadata at
`v0.6.0`. It is **not** an assertion that any arcade ROM distribution is
licensed, and it is not a tested compatibility list.

| Core file slot | Purpose | Selection | Maximum / exact size | Location |
|---|---|---|---|---|
| 0 | Game ROM (`.rom`) | User-selected, required | Up to 0x80000 = 524,288 bytes | Chosen from user's own files |
| 1 | SSIO Timing PROM | Fixed filename, required | Exactly 0x20 = 32 bytes | `cores/alanswx.MCR/ssio.prom` |

The required PROM has an existing SHA-256 pin in the catalog:
`4962a47f67ce0cebc655026efed495eb17fc29e7072650ecab2cecc4f16c06dc`.

**Implementation:** The BIOS manager now checks the installed core's
`core.json` and `files.json` before placing this PROM. It requires core ID
`alanswx.MCR`, the Game Bub Rev4 bitstream
`MCR3-gamebub_rev4.bit`, and the exact 32-byte, non-user-selected,
read-only mandatory `ssio.prom` declaration. Missing/mismatched metadata
results in an error rather than an unverified installation.

The BIOS step fetches the PROM from the pinned MAME 0.209 `midssio.zip` on
Archive.org when the file is missing. It checks the ZIP SHA-256 and the
extracted PROM SHA-256 before installation. A matching local `ssio.prom`
supplied with `--bios-dir` takes priority. The arcade step separately builds
checksum-verified MCR images from pinned MAME ZIPs. Existing differing files
are preserved rather than replaced.

The user's `files.json` establishes the two file interface entries. The
Rev4 bitstream name and core ID were separately checked against
[alanswx/MCR_GameBub v0.6.0 metadata](https://github.com/alanswx/MCR_GameBub/blob/v0.6.0/metadata/core.json).

This implementation and documentation were developed with substantial
**OpenAI ChatGPT** assistance; no MiSTer or MCR RTL source was copied.
External authors retain their respective licenses. See
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
