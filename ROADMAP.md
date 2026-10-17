# Development roadmap

This is a list of proposed work, not promised functionality or a release schedule.

1. **Publish and review v0.7 baseline.** Test from a clean checkout on Windows, macOS and Linux; independently verify selected public core ZIPs; perform Game Bub Rev4 hardware checks.
2. **Release governance.** Review BIOS source rights/default behavior, third-party provenance, GPL-3.0-only license compliance and upstream source provenance, and release package contents. Add source-attribution checks to code review.
3. **Catalog management.** Versioned schema, schema validation in CI, contributor submissions, stable and experimental channels, compatibility statuses, multiple databases.
4. **Usability.** The terminal menu, card suggestions, SD settings, and update checks are implemented. Add richer installation health reports and platform-specific removable-media identification.
5. **Download reliability.** Retry handling, free-space preflight, verified package cache, tracked-file verification, restore, and explicit uninstall are implemented. Add resumable downloads, more integrity modes, and stronger interrupted-update recovery.
6. **Optional additional workflows.** Verified official stable and pinned community-hosted core-loading beta UF2 downloads, plus the authors' offline MCR and Universal arcade builders and a checksum-verified export importer, are available. Firmware compatibility reporting uses the version entered from the handheld's Settings > About screen and the current core-author README. Direct handheld-version detection can follow if a reliable interface becomes available.

Each feature should have dedicated tests before being enabled by default. Avoid comparisons or unsupported quality claims about alternative downloaders.
