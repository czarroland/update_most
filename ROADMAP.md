# Development roadmap

This is a list of proposed work, not promised functionality or a release schedule.

1. **Publish and review v0.7 baseline.** Test from a clean checkout on Windows, macOS and Linux; independently verify selected public core ZIPs; perform Game Bub Rev4 hardware checks.
2. **Release governance.** Review BIOS source rights/default behavior, third-party provenance, GPL-3.0-only license compliance and upstream source provenance, and release package contents. Add source-attribution checks to code review.
3. **Catalog management.** Versioned schema, schema validation in CI, contributor submissions, stable and experimental channels, compatibility statuses, multiple databases.
4. **Usability.** Interactive menu, safe removable-card identification, settings saved on SD, update-check-only and human-readable reports.
5. **Download reliability.** Retries, free-space preflight, resumable or cached releases, integrity modes, safer interrupted-update recovery, restore and explicit uninstall.
6. **Optional additional workflows.** ROM-free arcade preparation helpers and separately confirmed firmware downloads. Do not automatically flash Game Bub firmware.

Each feature should have dedicated tests before being enabled by default. Avoid comparisons or unsupported quality claims about alternative downloaders.