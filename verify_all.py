#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Update_Most contributors
"""Audit actual GitHub core release packages without writing to a Game Bub card.

Runs on Python 3.9+ with no third-party modules. This is a *host-side* test,
not a hardware playability test or firmware verifier.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import tempfile
import urllib.parse

import update_most as u

HERE = Path(__file__).resolve().parent


def run(argv=None):
    parser = argparse.ArgumentParser(description="Metadata and binary-integrity verification for Update_Most curated releases")
    parser.add_argument("--catalog", default=str(HERE / "catalog.json"))
    parser.add_argument("--snapshot", default=str(HERE / "audit" / "verification_snapshot.json"))
    parser.add_argument("--channel", choices=["stable", "beta"], default="beta",
                        help="beta checks both stable and beta; default: all")
    parser.add_argument("--metadata-only", action="store_true", help="Do not fetch the actual ZIP assets or simulate SD installation")
    parser.add_argument("--report", help="Write a machine-readable JSON audit report to the specified file")
    args = parser.parse_args(argv)

    catalog = u.load_catalog(args.catalog)
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    expected = {c["id"]: c for c in snapshot["entries"]}
    eligible = [c for c in catalog["cores"] if c.get("enabled", True)
                and (args.channel == "beta" or c.get("channel", "stable") == "stable")]
    records = []
    with tempfile.TemporaryDirectory(prefix="update_most_verification_") as temp:
        sd = Path(temp) / "simulated_sd"
        sd.mkdir()
        (sd / "cores").mkdir()
        state = {"schema": 1, "installed": {}}
        for item in eligible:
            core_id = item["id"]
            record = {"id": core_id, "name": item["name"], "metadata_verified": False,
                      "binary_digest_verified": False, "simulated_install_verified": False,
                      "hardware_verified": False, "status": "not_checked"}
            records.append(record)
            print("\nChecking:", item["name"], "[", core_id, "]")
            try:
                spec = expected.get(core_id)
                if not spec:
                    raise u.UpdaterError("No independent snapshot expectation for this core")
                src = item["source"]
                if src["type"] != "github_release" or src["repo"] != spec["repo"]:
                    raise u.UpdaterError("Source repository differs from auditor's reference")
                version, url, digest, repo = u.resolve_release(src)
                record.update({"tag": version, "zip_url": url, "published_sha256": digest})
                if not digest:
                    raise u.UpdaterError("Release does not advertise a SHA-256 digest")
                if version == spec["tag"]:
                    if digest != spec["sha256"] or Path(urllib.parse.urlparse(url).path).name != spec["asset"]:
                        raise u.UpdaterError("Release asset/hash differs from recorded snapshot")
                else:
                    record["snapshot_changed"] = f"Previously audited {spec['tag']}; release now {version}"
                source_uri = "https://raw.githubusercontent.com/{}/{}/{}".format(
                    repo, urllib.parse.quote(version, safe=""),
                    urllib.parse.quote(spec["core_json_path"], safe="/"))
                source = json.loads(u.fetch(source_uri, limit=128 * 1024, hosts={"raw.githubusercontent.com"}))
                if source.get("metadata", {}).get("id") != core_id:
                    raise u.UpdaterError("Tagged source core.json has a different metadata.id")
                bits = [b["filename"] for b in source.get("bitstreams", [])
                        if b.get("target") == "gamebub_rev4"]
                if not bits:
                    raise u.UpdaterError("Tagged source core.json has no rev4 bitstream")
                if version == spec["tag"] and spec["bitstream"] not in bits:
                    raise u.UpdaterError("Tagged bitstream filename differs from snapshot")
                record["metadata_verified"] = True
                record["bitstreams"] = bits
                if args.metadata_only:
                    record["status"] = "metadata_only_passed"
                    print("  Metadata PASS (ZIP bytes not checked)")
                    continue
                package = u.fetch(url, u.MAX_DOWNLOAD, {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"})
                result = u.sha256(package)
                record["downloaded_sha256"] = result
                record["zip_bytes"] = len(package)
                if result != digest:
                    raise u.UpdaterError("Downloaded ZIP SHA-256 differs from release metadata")
                record["binary_digest_verified"] = True
                files = u.unpack_core(package, core_id, "gamebub_rev4")
                installed = json.loads(files["core.json"])
                if installed.get("metadata", {}).get("id") != core_id:
                    raise u.UpdaterError("Embedded release ID differs from expected ID")
                u.deploy(sd, core_id, files, version, result, state,
                         adopt=False, force=False, dry_run=False)
                for name, data in files.items():
                    actual = sd / "cores" / core_id / name
                    if not actual.is_file() or hashlib.sha256(actual.read_bytes()).digest() != hashlib.sha256(data).digest():
                        raise u.UpdaterError("Staged installation content mismatch: " + name)
                record["simulated_install_verified"] = True
                record["installed_files"] = sorted(files)
                record["status"] = "computer_side_passed"
                print("  ZIP digest, extraction, and temporary SD installation PASS")
            except Exception as exc:
                record["status"] = "failed"
                record["error"] = str(exc)
                print("  FAILED:", exc)
    report = {
        "schema": 1, "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "mode": "metadata_only" if args.metadata_only else "download_sha256_extract_and_temporary_sd_install",
        "hardware": "gamebub_rev4", "real_handheld_tested": False,
        "total": len(records), "passed": sum(r["status"] != "failed" for r in records),
        "failed": sum(r["status"] == "failed" for r in records), "entries": records,
    }
    if args.report:
        dest = Path(args.report).expanduser()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("\nSaved report:", dest)
    print(f"\nCompleted: {report['passed']} passed / {report['total']} attempted, "
          f"{report['failed']} failed. No actual Game Bub SD card was modified.")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(run())