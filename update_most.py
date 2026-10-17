#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Update_Most contributors
"""Update_Most: community-curated Game Bub SD-card core and BIOS manager.

AI-assisted software: developed with OpenAI ChatGPT and human direction.
See AI_DISCLOSURE.md and THIRD_PARTY_NOTICES.md for provenance.
Python 3.9+, stdlib. Does not flash firmware, download games, or format cards.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import fnmatch
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

USER_AGENT = "Update_Most/0.7 (Game Bub community updater)"
MISTER_BIOS_CSV = "https://raw.githubusercontent.com/ajgowans/BiosDB_MiSTer/main/external_files.csv"
COMMUNITY_CATALOG_URL = "https://raw.githubusercontent.com/czarroland/update_most/main/catalog.json"
MISTER_BIOS_ARCHIVE = "https://archive.org/download/mister_bios_db/"
MAX_MISTER_CSV = 512 * 1024
MD5_RE = re.compile(r"^[0-9a-fA-F]{32}$")
MAX_DOWNLOAD = 256 * 1024 * 1024
MAX_UNPACKED = 512 * 1024 * 1024
MAX_FILES = 1024
ID_RE = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9_.-]*$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{64}$")
SHA1_RE = re.compile(r"^[0-9a-fA-F]{40}$")
BIOS_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
MAX_BIOS_SIZE = 8 * 1024 * 1024
PROTECTED_EXTS = {".sav", ".srm", ".rtc", ".state", ".sstate", ".rom", ".gb", ".gbc", ".gba", ".gg", ".sms", ".sg", ".bin.sav"}


class UpdaterError(Exception):
    """A human-readable, nonzero-exit updater error."""


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def https_url(url: str, hosts=None):
    if not isinstance(url, str) or not url:
        raise UpdaterError("Expected a nonempty HTTPS URL")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise UpdaterError("Only public HTTPS URLs are allowed")
    if hosts and parsed.hostname not in hosts:
        raise UpdaterError("Unexpected download host: " + parsed.hostname)
    if parsed.port not in (None, 443):
        raise UpdaterError("Nonstandard HTTPS ports are not allowed")
    return url


def fetch(url: str, limit: int = MAX_DOWNLOAD, hosts=None) -> bytes:
    https_url(url, hosts)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json" if urllib.parse.urlparse(url).hostname == "api.github.com" else "application/octet-stream, application/json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    if urllib.parse.urlparse(url).hostname == "api.github.com" and os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as res:
            final_host = urllib.parse.urlparse(res.geturl()).hostname
            if urllib.parse.urlparse(res.geturl()).scheme != "https":
                raise UpdaterError("Download redirected to non-HTTPS destination")
            # GitHub release binary redirects to release-assets.githubusercontent.com.
            if hosts and final_host not in hosts:
                raise UpdaterError("Unexpected redirect host: " + str(final_host))
            content_length = res.headers.get("Content-Length")
            if content_length and int(content_length) > limit:
                raise UpdaterError("Download exceeds maximum size")
            data = res.read(limit + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpdaterError(f"Download failed ({url}): {exc}") from exc
    if len(data) > limit:
        raise UpdaterError("Download exceeds maximum size")
    return data


def load_catalog(location: str) -> dict:
    if location.startswith("https://"):
        raw = fetch(location, 2 * 1024 * 1024)
    else:
        raw = Path(location).expanduser().read_bytes()
    try:
        doc = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise UpdaterError(f"Catalog JSON is invalid: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != 1 or not isinstance(doc.get("cores"), list):
        raise UpdaterError("Catalog must contain schema: 1 and a cores array")
    seen = set()
    for core in doc["cores"]:
        if not isinstance(core, dict) or not ID_RE.fullmatch(str(core.get("id", ""))) or len(str(core.get("id", ""))) > 32:
            raise UpdaterError("Invalid core ID in catalog")
        ident = core["id"].casefold()
        if ident in seen:
            raise UpdaterError("Duplicate core IDs in catalog")
        seen.add(ident)
        if not isinstance(core.get("name"), str) or not core["name"].strip():
            raise UpdaterError("Every core needs a name")
        if core.get("channel", "stable") not in ("stable", "beta"):
            raise UpdaterError(f"Invalid channel for {core['id']}")
        if not isinstance(core.get("enabled", True), bool):
            raise UpdaterError("enabled must be true or false")
        src = core.get("source")
        if not isinstance(src, dict) or src.get("type") not in ("github_release", "url"):
            raise UpdaterError(f"Invalid source for {core['id']}")
        if src["type"] == "github_release":
            if not REPO_RE.fullmatch(src.get("repo", "")):
                raise UpdaterError("Invalid GitHub repo for " + core["id"])
            if not isinstance(src.get("asset"), str) or not src["asset"].lower().endswith(".zip"):
                raise UpdaterError("Release asset glob must end with .zip")
            if "tag" in src and (not isinstance(src["tag"], str) or not src["tag"]):
                raise UpdaterError("Invalid release tag")
            if "sha256" in src and not SHA_RE.fullmatch(src["sha256"]):
                raise UpdaterError("Invalid release SHA-256")
        else:
            https_url(src.get("url", ""))
            if not isinstance(src.get("version"), str) or not src["version"]:
                raise UpdaterError("Direct URL sources must provide version")
            if not SHA_RE.fullmatch(src.get("sha256", "")):
                raise UpdaterError("Direct URL sources require SHA-256")
    validate_bios_catalog(doc)
    return doc


def validate_bios_catalog(doc: dict):
    entries = doc.get("bios", [])
    if not isinstance(entries, list):
        raise UpdaterError("Catalog bios must be an array")
    destinations = set()
    ids = set()
    for item in entries:
        if not isinstance(item, dict) or not BIOS_ID_RE.fullmatch(str(item.get("id", ""))):
            raise UpdaterError("Invalid BIOS entry ID")
        ident = item["id"].casefold()
        if ident in ids:
            raise UpdaterError("Duplicate BIOS ID: " + item["id"])
        ids.add(ident)
        if not isinstance(item.get("name"), str) or not item["name"].strip():
            raise UpdaterError("BIOS must have a display name")
        destination = item.get("destination", "")
        if not isinstance(destination, str):
            raise UpdaterError("Invalid BIOS destination")
        parts = normalize_zip_path(destination).parts
        if not parts or len(parts) > 4 or len(destination) > 180:
            raise UpdaterError("Invalid BIOS destination length")
        core_id = item.get("core_id")
        if core_id is not None:
            if not isinstance(core_id, str) or not ID_RE.fullmatch(core_id) or len(core_id) > 32:
                raise UpdaterError("Invalid BIOS core_id")
            if len(parts) != 3 or tuple(parts[:2]) != ("cores", core_id):
                raise UpdaterError(f"BIOS for {core_id} must go inside cores/{core_id}/")
        elif len(parts) != 2 or parts[0] != "system":
            raise UpdaterError("Built-in BIOS must be placed under system/")
        if parts[-1].startswith("."):
            raise UpdaterError("BIOS filename may not start with .")
        if PurePosixPath(parts[-1]).suffix.lower() not in (".bin", ".rom", ".prom", ".bios"):
            raise UpdaterError("BIOS target must have a BIOS/ROM extension, not .bit or .json")
        # Optional, guarded handoff from a provisional system/ holding file to
        # a third-party core.  A core.json alone cannot tell us BIOS filenames;
        # files.json on the mounted SD must explicitly confirm the target.
        target_core = item.get("target_core")
        if target_core is not None:
            if core_id is not None:
                if target_core.get("id") != core_id or tuple(parts) != ("cores", core_id, target_core.get("filename")):
                    raise UpdaterError("Verified core BIOS destination must match target_core ID and filename")
            elif parts[0] != "system":
                raise UpdaterError("Provisional target_core BIOS must be under system/")
            if not isinstance(target_core, dict) or set(target_core) != {"id", "bitstream", "filename"}:
                raise UpdaterError("target_core needs id, bitstream, and filename")
            if not ID_RE.fullmatch(str(target_core["id"])) or len(target_core["id"]) > 32:
                raise UpdaterError("Invalid target_core ID")
            for field in ("bitstream", "filename"):
                name = target_core[field]
                if not isinstance(name, str) or len(name) > 80 or len(normalize_zip_path(name).parts) != 1:
                    raise UpdaterError("Invalid target_core " + field)
            if not target_core["bitstream"].endswith(".bit") or not target_core["filename"].endswith(".rom"):
                raise UpdaterError("Unexpected target_core filename extension")
        if destination.casefold() in destinations:
            raise UpdaterError("Duplicate BIOS destination: " + destination)
        destinations.add(destination.casefold())
        size = item.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or not (0 < size <= MAX_BIOS_SIZE):
            raise UpdaterError(f"Invalid BIOS size for {item['id']}")
        for hashname, regex in (("sha1", SHA1_RE), ("sha256", SHA_RE), ("md5", MD5_RE)):
            if hashname in item and (not isinstance(item[hashname], str) or not regex.fullmatch(item[hashname])):
                raise UpdaterError(f"Invalid BIOS {hashname} for {item['id']}")
        for field in ("required", "enabled"):
            if field in item and not isinstance(item[field], bool):
                raise UpdaterError(f"BIOS {field} must be boolean")
        group = item.get("one_of")
        if group is not None and (not isinstance(group, str) or not BIOS_ID_RE.fullmatch(group) or not core_id):
            raise UpdaterError("one_of must name a group of alternative core BIOS files")
        if group and item.get("required", False):
            raise UpdaterError("Alternative BIOS entries must not be individually required")
        src = item.get("source")
        if src is not None:
            if not isinstance(src, dict):
                raise UpdaterError("BIOS source must be an object")
            if src.get("type") == "mister_bios_db":
                # Preserve provenance; catalog hashes and size must match the index.
                if item.get("redistribution") != "community_unverified":
                    raise UpdaterError("MiSTer BIOS sources require community_unverified status")
                path = src.get("path")
                if not isinstance(path, str) or len(path) > 150 or not path.startswith("games/") or len(normalize_zip_path(path).parts) != 3:
                    raise UpdaterError("MiSTer BIOS source requires exact games/System/file path")
                if not MD5_RE.fullmatch(str(item.get("md5", ""))):
                    raise UpdaterError("MiSTer BIOS entry requires pinned MD5")
                if set(src) != {"type", "path"}:
                    raise UpdaterError("MiSTer BIOS source accepts only type and path")
            elif src.get("type") == "url":
                if item.get("redistribution") != "redistributable":
                    raise UpdaterError("Remote BIOS source must be explicitly approved as redistributable")
                https_url(src.get("url", ""))
                if not isinstance(src.get("sha256"), str) or not SHA_RE.fullmatch(src["sha256"]):
                    raise UpdaterError("Remote BIOS must have an exact source.sha256")
                member = src.get("archive_member")
                if member is not None:
                    if not isinstance(member, str) or member.endswith("/") or not normalize_zip_path(member).parts:
                        raise UpdaterError("Invalid BIOS archive_member")
                    if not urllib.parse.urlparse(src["url"]).path.lower().endswith(".zip"):
                        raise UpdaterError("archive_member only applies to ZIP URLs")
                elif urllib.parse.urlparse(src["url"]).path.lower().endswith(".zip"):
                    raise UpdaterError("ZIP BIOS source requires archive_member")
            else:
                raise UpdaterError("Unsupported BIOS source type")
        aliases = item.get("aliases", [])
        if not isinstance(aliases, list) or any(not isinstance(x, str) or not x or len(normalize_zip_path(x).parts) != 1 for x in aliases):
            raise UpdaterError("BIOS aliases must be plain filenames")
        if len(aliases) > 10:
            raise UpdaterError("Too many BIOS aliases")
        legacy = item.get("legacy_destinations", [])
        if not isinstance(legacy, list) or len(legacy) > 4:
            raise UpdaterError("legacy_destinations must be a short array")
        if legacy and not core_id:
            raise UpdaterError("legacy_destinations requires a core BIOS destination")
        for previous in legacy:
            if not isinstance(previous, str) or len(previous) > 180:
                raise UpdaterError("Invalid legacy BIOS destination")
            p = normalize_zip_path(previous)
            if len(p.parts) != 2 or p.parts[0] != "system" or p.suffix.lower() not in (".rom", ".bin", ".prom"):
                raise UpdaterError("Legacy BIOS files must be under system/ as ROM/bin/PROM")
        import_paths = item.get("import_paths", [])
        if not isinstance(import_paths, list) or len(import_paths) > 12:
            raise UpdaterError("import_paths must be a short array")
        for imp in import_paths:
            if not isinstance(imp, str) or not imp or len(imp) > 180 or not normalize_zip_path(imp).parts:
                raise UpdaterError("Invalid import_paths location")


def resolve_release(src: dict):
    if src["type"] == "url":
        return src["version"], src["url"], src["sha256"].lower(), None
    repo = src["repo"]
    tag = src.get("tag")
    if tag:
        endpoint = f"https://api.github.com/repos/{repo}/releases/tags/{urllib.parse.quote(tag, safe='')}"
    else:
        endpoint = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        release = json.loads(fetch(endpoint, 2 * 1024 * 1024, {"api.github.com"}))
    except ValueError as exc:
        raise UpdaterError("Bad release metadata from GitHub") from exc
    if release.get("draft") or (release.get("prerelease") and not tag):
        raise UpdaterError("No suitable public, stable release found")
    candidates = [x for x in release.get("assets", [])
                  if fnmatch.fnmatchcase(x.get("name", ""), src["asset"])]
    if len(candidates) != 1:
        raise UpdaterError(f"Expected exactly one matching ZIP asset in {repo}@{release.get('tag_name')}; found {len(candidates)}")
    asset = candidates[0]
    url = asset.get("browser_download_url", "")
    https_url(url, {"github.com"})
    if not url.endswith(".zip"):
        raise UpdaterError("Release asset must be a ZIP")
    # GitHub API often includes digest sha256:<hex>. Verify it when available.
    digest = asset.get("digest", "")
    actual_digest = digest.split(":", 1)[1] if digest.startswith("sha256:") else None
    if actual_digest and not SHA_RE.fullmatch(actual_digest):
        raise UpdaterError("Invalid GitHub release digest")
    supplied_hash = src.get("sha256")
    if supplied_hash and actual_digest and supplied_hash.lower() != actual_digest.lower():
        raise UpdaterError("Catalog SHA-256 disagrees with GitHub release metadata")
    return release["tag_name"], url, (supplied_hash.lower() if supplied_hash else actual_digest.lower() if actual_digest else None), repo


def normalize_zip_path(name: str) -> PurePosixPath:
    if name.startswith("/") or "\\" in name or "\x00" in name:
        raise UpdaterError("Unsafe ZIP path")
    path = PurePosixPath(name)
    if any(part in ("..", ".", "") for part in name.rstrip("/").split("/")):
        raise UpdaterError("Unsafe ZIP path traversal")
    if path.parts and ":" in path.parts[0]:
        raise UpdaterError("Unsafe ZIP drive path")
    return path


def unpack_core(package: bytes, core_id: str, hardware: str) -> dict[str, bytes]:
    """Return deployable relative paths and their contents, never writing raw ZIP paths."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(package))
    except (zipfile.BadZipFile, OSError) as exc:
        raise UpdaterError("Release package is not a valid ZIP") from exc
    with zf:
        members = [m for m in zf.infolist() if not m.is_dir()]
        if len(members) > MAX_FILES or sum(m.file_size for m in members) > MAX_UNPACKED:
            raise UpdaterError("ZIP exceeds extraction safety limits")
        normalized = {}
        for m in zf.infolist():
            path = normalize_zip_path(m.filename)
            # Unix symlinks and other special types are never extracted.
            mode = m.external_attr >> 16
            if (mode & 0o170000) not in (0, 0o040000 if m.is_dir() else 0o100000):
                raise UpdaterError("ZIP contains symbolic link or special file")
            if not m.is_dir():
                key = str(path).casefold()
                if key in normalized:
                    raise UpdaterError("ZIP contains case-insensitive duplicate paths")
                normalized[key] = m
        matches = []
        for m in members:
            if PurePosixPath(m.filename).name != "core.json":
                continue
            try:
                info = json.loads(zf.read(m))
            except (ValueError, UnicodeDecodeError):
                continue
            if info.get("metadata", {}).get("id") == core_id:
                matches.append((PurePosixPath(m.filename).parent, info))
        if len(matches) != 1:
            raise UpdaterError(f"ZIP must include exactly one core.json for {core_id} (found {len(matches)})")
        base, info = matches[0]
        meta = info.get("metadata", {})
        if not isinstance(meta.get("name"), str) or not isinstance(meta.get("author"), str):
            raise UpdaterError("core.json lacks name or author")
        bitstreams = info.get("bitstreams")
        if not isinstance(bitstreams, list) or not any(
            isinstance(b, dict) and b.get("target") == hardware for b in bitstreams):
            raise UpdaterError(f"No bitstream targeting {hardware}")
        selected_bitstreams = []
        for b in bitstreams:
            if not isinstance(b, dict):
                raise UpdaterError("Invalid bitstream entry")
            filename = b.get("filename", "")
            p = normalize_zip_path(filename)
            if not filename.endswith(".bit") or len(filename) > 32 or len(p.parts) != 1:
                raise UpdaterError("Bitstream filename must be a short .bit filename")
            if b.get("target") == hardware:
                selected_bitstreams.append(filename)
        files = {}
        for m in members:
            p = PurePosixPath(m.filename)
            try:
                rel = p.relative_to(base)
            except ValueError:
                continue
            if len(rel.parts) > 8:
                raise UpdaterError("Excessively nested core path")
            if rel.suffix.lower() in PROTECTED_EXTS or rel.name.lower() in ("bios.bin", "bootrom.bin"):
                # Never distribute/overwrite ROMs, BIOSes or user saves.
                continue
            files[str(rel)] = zf.read(m)
        if "core.json" not in files:
            raise UpdaterError("Core JSON missing after extraction")
        for bit in selected_bitstreams:
            if bit not in files:
                raise UpdaterError("Missing hardware .bit in package: " + bit)
        for optional in ("files.json", "settings.json"):
            if optional in files:
                try:
                    json.loads(files[optional])
                except (ValueError, UnicodeDecodeError) as exc:
                    raise UpdaterError(f"Invalid {optional}") from exc
        # Ensure only one packaged definition of core.json, not a user-data archive.
        return files


def ensure_safe_root(sd: Path, init: bool, dry_run: bool):
    if not sd.is_dir():
        raise UpdaterError("SD path does not exist or is not a directory: " + str(sd))
    if sd.is_symlink():
        raise UpdaterError("SD path must not be a symlink")
    sd = sd.resolve()
    if sd == Path(sd.anchor) or sd == Path.home().resolve():
        raise UpdaterError("Refusing to operate on drive root or home directory")
    if (sd / "cores").is_symlink() or (sd / ".update_most").is_symlink():
        raise UpdaterError("SD management directories must not be symlinks")
    for rel in (".update_most/managed.json", ".update_most/backups"):
        check_no_symlink(sd, rel)
    marker = sd / ".update_most" / "managed.json"
    if not init and not marker.exists() and not (sd / "cores").is_dir():
        raise UpdaterError("Unrecognized SD directory. Use --init on an explicitly selected SD root")
    if init and not dry_run:
        (sd / "cores").mkdir(exist_ok=True)
    return sd


def check_no_symlink(root: Path, rel: str):
    current = root
    for part in PurePosixPath(rel).parts:
        current = current / part
        if current.is_symlink():
            raise UpdaterError("Refusing to follow a symlink: " + str(current))


def load_state(sd: Path):
    p = sd / ".update_most" / "managed.json"
    if p.exists():
        doc = json.loads(p.read_text(encoding="utf-8"))
        if doc.get("schema") != 1 or not isinstance(doc.get("installed"), dict):
            raise UpdaterError("SD state file has unsupported format")
        return doc
    return {"schema": 1, "installed": {}}


def write_state(sd: Path, state: dict):
    root = sd / ".update_most"
    root.mkdir(exist_ok=True)
    temp = root / "managed.json.tmp"
    temp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, root / "managed.json")


def deploy(sd: Path, core_id: str, files: dict, version: str, package_sha: str,
           state: dict, *, adopt: bool, force: bool, dry_run: bool):
    base = sd / "cores" / core_id
    check_no_symlink(sd, "cores/" + core_id)
    previous = state["installed"].get(core_id, {})
    tracked = previous.get("files", {})
    for rel, content in files.items():
        check_no_symlink(base, rel)
        target = base.joinpath(*PurePosixPath(rel).parts)
        if target.exists():
            if not target.is_file():
                raise UpdaterError("Non-file blocks core installation: " + str(target))
            current = file_sha(target)
            if rel not in tracked and not adopt:
                raise UpdaterError(f"Existing, unmanaged {core_id}/{rel}; refuse overwrite (use --adopt to back it up)")
            if rel in tracked and current != tracked[rel] and not force:
                raise UpdaterError(f"Locally modified {core_id}/{rel}; refuse overwrite (use --force to back it up)")
    if dry_run:
        print(f"  [DRY RUN] Would install {len(files)} files in cores/{core_id} (existing files preserved/backed up)")
        return
    # Save all pre-existing overwritten files before touching the core, for rollback.
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = sd / ".update_most" / "backups" / core_id / stamp
    check_no_symlink(sd, ".update_most/backups/" + core_id + "/" + stamp)
    originals = {}
    created = []
    for rel in files:
        src = base.joinpath(*PurePosixPath(rel).parts)
        if src.exists():
            originals[rel] = src.read_bytes()
    try:
        if originals:
            for rel, data in originals.items():
                dest = backup.joinpath(*PurePosixPath(rel).parts)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
        for rel, content in files.items():
            target = base.joinpath(*PurePosixPath(rel).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            if rel not in originals:
                created.append(target)
            temp = target.with_name(target.name + ".update_most_tmp")
            try:
                temp.write_bytes(content)
                os.replace(temp, target)
            finally:
                temp.unlink(missing_ok=True)
        state["installed"][core_id] = {
            "version": version, "package_sha256": package_sha,
            "files": {k: sha256(v) for k, v in files.items()}, "updated_at": utc_now()
        }
        write_state(sd, state)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        for rel, content in originals.items():
            target = base.joinpath(*PurePosixPath(rel).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        raise
    if originals:
        print(f"  Backup: {backup.relative_to(sd)}")
    print(f"  Installed: cores/{core_id} ({len(files)} files)")


def load_mister_bios_index(wanted_paths: set[str], fetcher=fetch) -> dict:
    """Load MiSTer BIOS CSV, treating all remote rows as untrusted metadata.

    A catalog-pinned MD5 and size must agree with the matching database row
    before downloading. This index does not itself establish permission to copy.
    """
    raw = fetcher(MISTER_BIOS_CSV, MAX_MISTER_CSV)
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UpdaterError("MiSTer BIOS database is not UTF-8") from exc
    reader = csv.DictReader(line for line in content.splitlines() if line.strip())
    expected = {"Path", "URL", "Size in bytes (optional but recommended)", "MD5 Hash (optional but recommended)"}
    if not reader.fieldnames or not expected.issubset(reader.fieldnames):
        raise UpdaterError("Unexpected MiSTer BIOS database format")
    records = {}
    for row in reader:
        path = (row.get("Path") or "").strip()
        if path not in wanted_paths:
            continue
        normalize_zip_path(path)
        size = (row.get("Size in bytes (optional but recommended)") or "").strip()
        digest = (row.get("MD5 Hash (optional but recommended)") or "").strip().lower()
        url = (row.get("URL") or "").strip()
        if not size.isdigit() or not MD5_RE.fullmatch(digest) or not (0 < int(size) <= MAX_BIOS_SIZE):
            continue
        https_url(url)
        # The original database is community maintained. The actual ROM host is
        # restricted to its known archival namespace, not arbitrary CSV URLs.
        if not url.startswith(MISTER_BIOS_ARCHIVE):
            continue
        if path in records:
            raise UpdaterError("Duplicate MiSTer BIOS database path: " + path)
        records[path] = {"url": url, "size": int(size), "md5": digest}
    return records


def bios_content_valid(data: bytes, item: dict) -> bool:
    if len(data) != item["size"]:
        return False
    if "sha1" in item and hashlib.sha1(data).hexdigest() != item["sha1"].lower():
        return False
    if "sha256" in item and sha256(data) != item["sha256"].lower():
        return False
    if "md5" in item and hashlib.md5(data).hexdigest() != item["md5"].lower():
        return False
    return True


def locate_bios_file(directory: Path, item: dict) -> bytes | None:
    if not directory.is_dir():
        raise UpdaterError("BIOS source directory does not exist: " + str(directory))
    # Only explicit paths, not recursive scans of a user's entire ROM library.
    destination = PurePosixPath(item["destination"])
    names = [destination.name] + item.get("aliases", [])
    candidates = [directory.joinpath(*destination.parts)]
    candidates.extend(directory.joinpath(*PurePosixPath(path).parts)
                      for path in item.get("import_paths", []))
    if item.get("core_id"):
        candidates.extend(directory / item["core_id"] / name for name in names)
    candidates.extend(directory / name for name in names)
    for file in candidates:
        if file.is_symlink():
            print(f"  Skipping symlink in BIOS import: {file}")
            continue
        if file.is_file():
            if file.stat().st_size > MAX_BIOS_SIZE:
                print(f"  Skipping oversized BIOS candidate: {file.name}")
                continue
            data = file.read_bytes()
            if bios_content_valid(data, item):
                print(f"  Local source: {file}")
                return data
            print(f"  Incorrect size/hash for {file.name}; searching next candidate")
    return None


def unpack_bios_asset(data: bytes, source: dict) -> bytes:
    member = source.get("archive_member")
    if member is None:
        return data
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_FILES or sum(m.file_size for m in infos) > MAX_UNPACKED:
                raise UpdaterError("BIOS ZIP exceeds safety limits")
            for m in infos:
                normalize_zip_path(m.filename)
                mode = m.external_attr >> 16
                if (mode & 0o170000) not in (0, 0o040000 if m.is_dir() else 0o100000):
                    raise UpdaterError("BIOS ZIP contains symlink or special file")
            matches = [m for m in infos if m.filename == member and not m.is_dir()]
            if len(matches) != 1:
                raise UpdaterError("BIOS archive member not found exactly once: " + member)
            if matches[0].file_size > MAX_BIOS_SIZE:
                raise UpdaterError("BIOS archive member is too large")
            return zf.read(matches[0])
    except zipfile.BadZipFile as exc:
        raise UpdaterError("Invalid BIOS archive") from exc


def acquire_bios(item: dict, directory: Path | None, fetcher=fetch,
                 *, mister_index=None, allow_mister_bios=True) -> tuple[bytes | None, str]:
    if directory is not None:
        found = locate_bios_file(directory, item)
        if found is not None:
            return found, "local"
    src = item.get("source")
    if src and src["type"] == "mister_bios_db":
        if not allow_mister_bios:
            return None, "MiSTer BIOS fetching disabled (--no-mister-bios)"
        if mister_index is None:
            raise UpdaterError("MiSTer BIOS database not loaded")
        record = mister_index.get(src["path"])
        if record is None:
            raise UpdaterError("MiSTer BIOS database entry missing: " + src["path"])
        if record["size"] != item["size"] or record["md5"] != item["md5"].lower():
            raise UpdaterError("MiSTer BIOS database size/hash differs from pinned catalog")
        print(f"  Fetch MiSTer database BIOS: {record['url']}")
        data = fetcher(record["url"], MAX_BIOS_SIZE + 1)
        if not bios_content_valid(data, item):
            raise UpdaterError("Downloaded MiSTer BIOS size/MD5 mismatch; rejected")
        return data, "MiSTer BIOS database (MD5 and length verified)"
    if src:
        print(f"  Fetch authorized BIOS: {src['url']}")
        data = fetcher(src["url"], MAX_DOWNLOAD)
        if sha256(data) != src["sha256"].lower():
            raise UpdaterError("BIOS download SHA-256 mismatch")
        blob = unpack_bios_asset(data, src)
        if not bios_content_valid(blob, item):
            raise UpdaterError("Fetched BIOS size or hash does not match catalog")
        return blob, "verified HTTPS"
    return None, "not found (supply BIOS with --bios-dir)"


def install_bios_file(sd: Path, item: dict, data: bytes, dry_run: bool):
    """Never overwrite any existing BIOS, even when --force or --adopt is set."""
    destination = item["destination"]
    check_no_symlink(sd, destination)
    target = sd.joinpath(*PurePosixPath(destination).parts)
    if target.exists():
        raise UpdaterError("BIOS destination already exists; refusing overwrite")
    if dry_run:
        print(f"  [DRY RUN] Would install {destination}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create protects against races (including manual changes during downloads).
    try:
        with target.open("xb") as output:
            try:
                output.write(data)
            except BaseException:
                target.unlink(missing_ok=True)
                raise
    except FileExistsError as exc:
        raise UpdaterError("BIOS appeared during update; refusing overwrite") from exc
    print(f"  Installed: {destination} ({len(data)} bytes, SHA-256 {sha256(data)[:12]}...)")


def confirmed_core_bios_destination(sd: Path, item: dict) -> str | None:
    """Return a core BIOS path only if the *installed* core explicitly declares it.

    Uploaded core.json files establish IDs/bitstreams, not the expected BIOS
    filename. Never guess a location from an emulator's or MiSTer's layout.
    This also accepts locally-installed, community-distributed cores which
    are not yet published in the update catalog.
    """
    target_core = item.get("target_core")
    if not target_core:
        return None
    cid = target_core["id"]
    core_root = sd / "cores" / cid
    check_no_symlink(sd, f"cores/{cid}")
    for rel in (f"cores/{cid}/core.json", f"cores/{cid}/files.json"):
        check_no_symlink(sd, rel)
    try:
        core_doc = json.loads((core_root / "core.json").read_text(encoding="utf-8"))
        file_doc = json.loads((core_root / "files.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UpdaterError(f"Invalid installed core metadata for {cid}: {exc}") from exc
    if not isinstance(core_doc, dict) or not isinstance(file_doc, dict):
        raise UpdaterError(f"Invalid core.json/files.json structure for {cid}")
    if not isinstance(core_doc.get("metadata"), dict):
        raise UpdaterError(f"Invalid metadata in installed core.json for {cid}")
    if core_doc["metadata"].get("id") != cid:
        raise UpdaterError(f"Installed core ID does not match {cid}")
    bitstreams = core_doc.get("bitstreams", [])
    if not isinstance(bitstreams, list) or not any(isinstance(b, dict) and
           b.get("target") == "gamebub_rev4" and
           b.get("filename") == target_core["bitstream"] for b in bitstreams):
        raise UpdaterError(f"Installed {cid} does not declare expected rev4 bitstream")
    expected = target_core["filename"]
    files = file_doc.get("files")
    if not isinstance(files, list):
        raise UpdaterError(f"Invalid files.json for {cid}: files array missing")
    matches = []
    for entry in files:
        if not isinstance(entry, dict) or entry.get("filename") != expected:
            continue
        raw_size = entry.get("exact_size")
        try:
            size = int(raw_size, 0) if isinstance(raw_size, str) else raw_size
        except ValueError:
            size = None
        if (size == item["size"] and entry.get("read_only") is True
                and entry.get("user_selected") is not True):
            matches.append(entry)
    if len(matches) != 1:
        return None
    return f"cores/{cid}/{expected}"


def manage_bios(sd: Path, catalog: dict, directory: Path | None, dry_run: bool,
                *, fetcher=None, predicted_core_ids=None,
                allow_mister_bios=True) -> tuple[int, int, int]:
    """Manage BIOS, automatically fetching pinned MiSTer DB entries by default."""
    if fetcher is None:
        fetcher = fetch
    entries = [item for item in catalog.get("bios", []) if item.get("enabled", True)]
    if not entries:
        print("\nBIOS: no entries in community catalog")
        return 0, 0, 0
    print("\nBIOS / boot ROM preparation")
    good, missing, failed = 0, 0, 0
    mister_index = None  # Fetch the CSV once, only when an eligible file needs it.
    groups: dict[tuple[str,str], list[str]] = {}
    grouped_ok: set[tuple[str,str]] = set()
    installed_core_ids = {
        item["core_id"] for item in entries if item.get("core_id") and
        (sd / "cores" / item["core_id"] / "core.json").is_file()
    }
    installed_core_ids.update(predicted_core_ids or ())
    for item in entries:
        core_id = item.get("core_id")
        if core_id and core_id not in installed_core_ids:
            continue
        group = (core_id, item["one_of"]) if item.get("one_of") else None
        if group:
            groups.setdefault(group, []).append(item["name"])
        provisional_dest = item["destination"]
        print(f"- {item['name']}")
        try:
            confirmed = confirmed_core_bios_destination(sd, item)
            # For authoritatively mapped core BIOSes, never silently stage or
            # download under a guessed location when installed metadata differs.
            if item.get("core_id") and item.get("target_core") and not confirmed:
                raise UpdaterError("Installed core.json/files.json does not confirm BIOS filename, Rev4 bitstream, and exact size")
            dest = confirmed or provisional_dest
            resolved_item = dict(item, destination=dest)
            if confirmed and provisional_dest != dest:
                # Recognize the old v0.4 staging filename when --bios-dir
                # points to a personal import folder or another SD card.
                resolved_item["aliases"] = list(dict.fromkeys(
                    [*item.get("aliases", []), PurePosixPath(provisional_dest).name]))
                resolved_item["import_paths"] = list(dict.fromkeys(
                    [*item.get("import_paths", []), provisional_dest]))
            target = sd.joinpath(*PurePosixPath(dest).parts)
            if item.get("target_core") and not confirmed:
                print(f"  Core BIOS filename not confirmed by installed files.json; staging -> {dest}")
            else:
                print(f"  Destination -> {dest}")
            check_no_symlink(sd, dest)
            if target.exists():
                if not target.is_file() or target.stat().st_size > MAX_BIOS_SIZE:
                    raise UpdaterError("Existing BIOS is not a supported regular file")
                data = target.read_bytes()
                if bios_content_valid(data, item):
                    print("  Present: size/checksum OK; preserved")
                    good += 1
                    if group:
                        grouped_ok.add(group)
                    continue
                print("  WARNING: existing BIOS has unexpected size/hash; preserved unchanged")
                failed += 1
                continue
            # Upgrade v0.5 holding files to verified Game Bub core folders.
            # Preserve the staged original; only trusted size/hash matches migrate.
            # Supports the earlier conditional-staging catalog unchanged.
            legacy_paths = list(item.get("legacy_destinations", []))
            if confirmed and provisional_dest != dest:
                legacy_paths.insert(0, provisional_dest)
            migrated = False
            for previous in dict.fromkeys(legacy_paths):
                check_no_symlink(sd, previous)
                holding = sd.joinpath(*PurePosixPath(previous).parts)
                if holding.is_file() and holding.stat().st_size <= MAX_BIOS_SIZE:
                    staged_data = holding.read_bytes()
                    if bios_content_valid(staged_data, item):
                        print(f"  Reusing verified staged BIOS from {previous}")
                        install_bios_file(sd, resolved_item, staged_data, dry_run)
                        good += 1
                        migrated = True
                        break
                    print(f"  WARNING: staged BIOS {previous} has an unexpected size/hash; ignoring it")
            if migrated:
                if group:
                    grouped_ok.add(group)
                continue
            # Local/imported BIOS always takes priority. Avoid contacting the
            # online index when an existing verified local file is sufficient.
            local_blob = locate_bios_file(directory, resolved_item) if directory is not None else None
            if local_blob is not None:
                blob, method = local_blob, "local"
            else:
                if (item.get("source", {}).get("type") == "mister_bios_db" and
                        allow_mister_bios and mister_index is None):
                    wanted = {b["source"]["path"] for b in entries
                              if b.get("source", {}).get("type") == "mister_bios_db"}
                    mister_index = load_mister_bios_index(wanted, fetcher=fetcher)
                blob, method = acquire_bios(
                    resolved_item, None, fetcher=fetcher, mister_index=mister_index,
                    allow_mister_bios=allow_mister_bios)
            if blob is None:
                if item.get("required", False):
                    missing += 1
                    print("  MISSING REQUIRED: " + method)
                elif not group:
                    print("  Optional: " + method)
                else:
                    print("  Alternative not present: " + method)
                continue
            install_bios_file(sd, resolved_item, blob, dry_run)
            good += 1
            if group:
                grouped_ok.add(group)
        except (UpdaterError, OSError, ValueError) as exc:
            failed += 1
            print(f"  BIOS ERROR: {exc}", file=sys.stderr)
    for group, names in groups.items():
        if group not in grouped_ok:
            missing += 1
            print(f"  MISSING REQUIRED: at least one of {', '.join(names)} for {group[0]}")
    print(f"BIOS summary: {good} present/installed, {missing} missing requirements, {failed} errors.")
    return good, missing, failed


def main(argv=None):
    parser = argparse.ArgumentParser(description="Update_Most: prepare a Game Bub microSD from a curated community database")
    parser.add_argument("--sd", help="Path to mounted Game Bub microSD card ROOT (never a subfolder)")
    parser.add_argument("--catalog", help="Explicit local JSON path or HTTPS catalog URL (overrides --catalog-track)")
    parser.add_argument("--catalog-track", choices=["bundled", "github"], default="bundled",
                        help="bundled=local snapshot (default); github=current community main-branch catalog, opt-in")
    parser.add_argument("--channel", choices=["stable", "beta"], default="stable", help="Beta installs both stable and beta entries")
    parser.add_argument("--hardware", choices=["gamebub_rev4", "gamebub_rev2"], default="gamebub_rev4")
    parser.add_argument("--list", action="store_true", help="List curated releases without SD card or downloads")
    parser.add_argument("--list-bios", action="store_true", help="List BIOS/boot ROM requirements and curated fetch permissions")
    parser.add_argument("--bios-only", action="store_true", help="Only check/import/fetch BIOS; skip core download")
    parser.add_argument("--skip-bios", action="store_true", help="Core updates only; do not inspect or fetch BIOS")
    parser.add_argument("--bios-dir", help="Optional folder of legally obtained BIOS dumps (copied to the correct filenames)")
    bios_mode = parser.add_mutually_exclusive_group()
    bios_mode.add_argument("--mister-bios", dest="mister_bios", action="store_true", help="Enable MiSTer BIOS database downloads (already enabled by default; retained for compatibility)")
    bios_mode.add_argument("--no-mister-bios", dest="mister_bios", action="store_false", help="Disable MiSTer community BIOS downloads (local BIOS import still works)")
    parser.set_defaults(mister_bios=True)
    parser.add_argument("--dry-run", action="store_true", help="Resolve releases and inspect packages, do not write to SD")
    parser.add_argument("--init", action="store_true", help="Initialize explicitly selected SD folder; does not format it")
    parser.add_argument("--adopt", action="store_true", help="Back up and replace unmanaged core files, e.g. manually installed cores")
    parser.add_argument("--force", action="store_true", help="Reinstall existing version and back up locally modified managed files")
    parser.add_argument("--allow-unverified", action="store_true", help="Allow older GitHub assets without release SHA-256 (not recommended)")
    args = parser.parse_args(argv)
    if args.bios_only and args.skip_bios:
        parser.error("--bios-only and --skip-bios cannot be combined")
    if not args.sd and not args.list and not args.list_bios:
        if sys.stdin.isatty():
            args.sd = input("Game Bub SD-card root path (e.g. /Volumes/GAMEBUB or E:\\): ").strip().strip('"')
        if not args.sd:
            parser.error("--sd required (or run interactively and enter SD path)")
    catalog_location = (args.catalog if args.catalog is not None else
                        COMMUNITY_CATALOG_URL if args.catalog_track == "github" else
                        str(Path(__file__).with_name("catalog.json")))
    catalog = load_catalog(catalog_location)
    print(f"Update_Most | {catalog.get('name', 'Game Bub community catalog')} | hardware {args.hardware}")
    if args.list_bios:
        for b in catalog.get("bios", []):
            src = b.get("source", {})
            origin = ("MiSTer community DB (auto, --no-mister-bios disables)" if src.get("type") == "mister_bios_db"
                      else "approved HTTPS" if src else "user-supplied")
            target = b.get("target_core")
            extra = f" | auto-targets {target['id']} when files.json confirms {target['filename']}" if target else ""
            print(f"- {b['name']} | {b['destination']} | {b['size']} bytes | {origin}{extra}")
        return 0
    if args.list:
        for c in catalog["cores"]:
            print(f"- {c['id']} | {c['name']} | {c.get('channel', 'stable')} | {'enabled' if c.get('enabled', True) else 'disabled'}")
        if not catalog["cores"]:
            print("No published core entries yet. Curator: add releases to catalog.json.")
        return 0
    sd = ensure_safe_root(Path(args.sd).expanduser(), args.init, args.dry_run)
    state = load_state(sd)
    ok, failed, skipped = 0, 0, 0
    eligible = [c for c in catalog["cores"] if c.get("enabled", True) and
                (args.channel == "beta" or c.get("channel", "stable") == "stable")]
    if not eligible and not args.bios_only:
        print("No approved core releases in this channel. Checking BIOS requirements.")
    for core in ([] if args.bios_only else eligible):
        ident = core["id"]
        print(f"\n{core['name']} [{ident}]")
        try:
            version, url, known_hash, repo = resolve_release(core["source"])
            old = state["installed"].get(ident)
            if old and old.get("version") == version and not args.force:
                old_files = old.get("files", {})
                base = sd / "cores" / ident
                check_no_symlink(sd, "cores/" + ident)
                for rel in old_files:
                    check_no_symlink(base, rel)
                if old_files and all(
                    (base / rel).is_file() and file_sha(base / rel) == digest
                    for rel, digest in old_files.items()
                ):
                    print(f"  Current: {version} (verified installed files)")
                    skipped += 1
                    continue
                print("  Previously installed files missing or modified; verifying latest package")
            if repo and not known_hash and not args.allow_unverified:
                raise UpdaterError("GitHub release has no SHA-256; curator must add a source.sha256 or use --allow-unverified")
            print(f"  Download: {version} | {url}")
            allowed = {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"} if repo else None
            package = fetch(url, MAX_DOWNLOAD, allowed)
            digest = sha256(package)
            if known_hash and digest != known_hash:
                raise UpdaterError("SHA-256 mismatch; package rejected")
            contents = unpack_core(package, ident, args.hardware)
            if core.get("requires_firmware"):
                print("  Firmware requirement (not checked automatically): " + str(core["requires_firmware"]))
            deploy(sd, ident, contents, version, digest, state,
                   adopt=args.adopt, force=args.force, dry_run=args.dry_run)
            ok += 1
        except (UpdaterError, OSError, ValueError, zipfile.BadZipFile) as exc:
            failed += 1
            print(f"  ERROR: {exc}", file=sys.stderr)
    print(f"\nCores: {ok} {'checked' if args.dry_run else 'installed'}, {skipped} current, {failed} errors.")
    if not args.skip_bios:
        bios_dir = Path(args.bios_dir).expanduser().resolve() if args.bios_dir else None
        planned = {c["id"] for c in eligible} if args.dry_run and not args.bios_only else set()
        _, _, errors = manage_bios(sd, catalog, bios_dir, args.dry_run,
                                   predicted_core_ids=planned, allow_mister_bios=args.mister_bios)
        failed += errors
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (UpdaterError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)