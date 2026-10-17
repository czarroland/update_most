#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Update_Most contributors
"""Offline catalog provenance and metadata checks for Update_Most.

AI-assisted implementation (OpenAI ChatGPT). No MiSTer updater code imported.
Usage: python3 validate_catalog.py --catalog catalog.json
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from urllib.parse import urlsplit

from update_most import UpdaterError, load_catalog

KNOWN_HARDWARE = {"gamebub_rev4", "gamebub_rev2"}


def validate_records(catalog: dict, require_verified_licenses: bool = False):
    """Return (errors, warnings). Does not contact GitHub or download content."""
    errors = []
    warnings = []
    revision = catalog.get("catalog_revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append("catalog_revision must be a positive integer independent of schema")
    if not isinstance(catalog.get("name"), str) or not catalog["name"].strip():
        errors.append("Catalog needs a nonempty name")
    seen_repos = {}
    for number, core in enumerate(catalog["cores"], start=1):
        prefix = f"cores[{number}] {core['id']}"
        hardware = core.get("hardware")
        if (not isinstance(hardware, list) or not hardware or
                any(not isinstance(h, str) or h not in KNOWN_HARDWARE for h in hardware) or
                len(set(hardware)) != len(hardware)):
            errors.append(f"{prefix}: hardware must be a nonempty list of unique supported targets")
        category = core.get("category")
        if not isinstance(category, str) or not category.strip():
            errors.append(f"{prefix}: category must be present")
        upstream = core.get("upstream")
        if not isinstance(upstream, dict):
            errors.append(f"{prefix}: upstream attribution object is required")
        else:
            for key in ("author", "license"):
                if not isinstance(upstream.get(key), str) or not upstream[key].strip():
                    errors.append(f"{prefix}: upstream.{key} must be nonempty")
            if upstream.get("reference_only") is not True:
                errors.append(f"{prefix}: upstream.reference_only must be true for a catalog-only link")
            status = str(upstream.get("license", "")).lower().strip()
            if status in ("license not verified", "unverified", "unknown"):
                message = f"{prefix}: upstream license not independently verified"
                (errors if require_verified_licenses else warnings).append(message)
        source = core["source"]
        if source["type"] == "github_release":
            repo = source["repo"]
            home = core.get("homepage")
            expected = "https://github.com/" + repo
            if not isinstance(home, str):
                errors.append(f"{prefix}: homepage must provide upstream repository URL")
            else:
                url = urlsplit(home)
                if (url.scheme != "https" or url.hostname != "github.com" or
                        url.path.strip("/").casefold() != repo.casefold() or
                        url.query or url.fragment or url.username or url.password):
                    errors.append(f"{prefix}: homepage does not match source.repo {repo}")
            # Same repo may have multiple cores, but catalog displays this for audit.
            seen_repos.setdefault(repo.casefold(), []).append(core["id"])
        media = core.get("arcade_media")
        if media is not None:
            if (not isinstance(media, dict) or
                    set(media) != {"description", "file_id", "extensions", "user_selected",
                                   "required", "read_only", "max_size"}):
                errors.append(f"{prefix}: arcade_media fields are incomplete or unexpected")
            elif (not isinstance(media["description"], str) or not media["description"].strip() or
                    not isinstance(media["file_id"], int) or isinstance(media["file_id"], bool) or
                    media["file_id"] < 0 or
                    not isinstance(media["extensions"], list) or not media["extensions"] or
                    any(not isinstance(ext, str) or not ext.isascii() or
                        not ext.isalnum() or ext.lower() != ext or len(ext) > 8
                        for ext in media["extensions"]) or
                    len(set(media["extensions"])) != len(media["extensions"]) or
                    media["user_selected"] is not True or media["required"] is not True or
                    media["read_only"] is not True or
                    not isinstance(media["max_size"], int) or isinstance(media["max_size"], bool) or
                    not (1 <= media["max_size"] <= 8 * 1024 * 1024)):
                errors.append(f"{prefix}: invalid user-supplied arcade_media specification")
        firmware = core.get("requires_firmware")
        if firmware is not None and (not isinstance(firmware, str) or not firmware.strip()):
            errors.append(f"{prefix}: requires_firmware must be nonempty text if supplied")
    if not isinstance(catalog.get("bios", []), list):
        errors.append("bios must be an array")
    return errors, warnings


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline validation of a Game Bub community catalog")
    parser.add_argument("--catalog", default=str(Path(__file__).with_name("catalog.json")),
                        help="Path to a local catalog JSON; HTTPS catalogs are not accepted by the validator")
    parser.add_argument("--require-verified-licenses", action="store_true",
                        help="Fail when a core's repository license is not yet independently verified")
    args = parser.parse_args(argv)
    if args.catalog.startswith("https://") or "://" in args.catalog:
        parser.error("Catalog validator accepts only local files; review remote contents separately")
    try:
        catalog = load_catalog(args.catalog)
        errors, warnings = validate_records(catalog, args.require_verified_licenses)
    except (UpdaterError, OSError, ValueError) as exc:
        print("INVALID CATALOG:", exc, file=sys.stderr)
        return 1
    for warning in warnings:
        print("WARNING:", warning)
    for error in errors:
        print("ERROR:", error, file=sys.stderr)
    print(f"Catalog: {len(catalog['cores'])} cores, {len(catalog.get('bios', []))} BIOS records; "
          f"{len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
