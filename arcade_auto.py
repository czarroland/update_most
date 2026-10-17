"""Build Game Bub arcade images from checksum-pinned Archive.org MAME sets.

Recipes are factual chip layouts recorded from the core authors' builders.
No game data is included in this project.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tempfile
import zipfile
import zlib


class ArcadeError(Exception):
    pass


DATA = Path(__file__).with_name("databases")


def catalogs(data_dir: Path = DATA):
    recipes = json.loads((data_dir / "arcade_recipes.json").read_text(encoding="utf-8"))
    sources = json.loads((data_dir / "arcade_sources.json").read_text(encoding="utf-8"))
    images = json.loads((data_dir / "arcade_images.json").read_text(encoding="utf-8"))
    if any(doc.get("schema") != 1 for doc in (recipes, sources, images)):
        raise ArcadeError("Unsupported arcade catalog schema")
    return recipes, sources, images


def source_zip(name: str, source: dict, fetcher) -> bytes:
    """Fetch one independently hashed file from the pinned Archive item."""
    entry = source["files"].get(name)
    if entry is None:
        raise ArcadeError("No verified Archive.org source for " + name)
    if not name.endswith(".zip") or "/" in name or "\\" in name:
        raise ArcadeError("Invalid archived ZIP name")
    size = entry["size"]
    if not isinstance(size, int) or not 0 < size <= 8 * 1024 * 1024:
        raise ArcadeError("Archived ZIP exceeds the source limit")
    data = fetcher(source["base_url"] + name, size + 1, {"archive.org"})
    if len(data) != size or hashlib.sha1(data).hexdigest() != entry["sha1"]:
        raise ArcadeError("Archived ZIP size or SHA-1 mismatch: " + name)
    return data


def assemble(recipe: dict, archives: dict[str, bytes]) -> bytes:
    """Assemble a core image from ZIP chips, then verify the author's CRC32."""
    chips: dict[int, list[tuple[str, zipfile.ZipFile, zipfile.ZipInfo]]] = {}
    opened = []
    try:
        for archive_name, data in archives.items():
            bundle = zipfile.ZipFile(io.BytesIO(data))
            opened.append(bundle)
            infos = bundle.infolist()
            if len(infos) > 512 or sum(i.file_size for i in infos) > 32 * 1024 * 1024:
                raise ArcadeError("Archived MAME ZIP exceeds chip limits: " + archive_name)
            for info in infos:
                if info.is_dir() or info.file_size > 2 * 1024 * 1024:
                    continue
                chips.setdefault(info.CRC, []).append((info.filename.rsplit("/", 1)[-1], bundle, info))
        output = bytearray()
        expected_size = recipe["size"]
        if not isinstance(expected_size, int) or not 0 < expected_size <= 4 * 1024 * 1024:
            raise ArcadeError("Invalid arcade recipe size")
        for part in recipe["parts"]:
            if "name" in part:
                crc = int(part["crc"], 16)
                matches = chips.get(crc, [])
                if "size" in part:
                    matches = [item for item in matches if item[2].file_size == part["size"]]
                if not matches:
                    raise ArcadeError("Missing chip " + part["name"] + " (CRC " + part["crc"] + ")")
                chosen = next((item for item in matches if item[0] == part["name"]), matches[0])
                data = chosen[1].read(chosen[2])  # zipfile checks the chip CRC on read.
                start = part.get("offset", 0)
                length = part.get("length", len(data) - start)
                if start < 0 or length <= 0 or start + length > len(data):
                    raise ArcadeError("Invalid arcade chip slice")
                data = data[start:start + length]
            else:
                data = bytes.fromhex(part["fill"])
            repeat = part["repeat"]
            if not isinstance(repeat, int) or repeat < 1 or len(output) + len(data) * repeat > expected_size:
                raise ArcadeError("Arcade recipe exceeds expected image size")
            output.extend(data * repeat)
        if len(output) != expected_size or f"{zlib.crc32(output):08x}" != recipe["crc32"]:
            raise ArcadeError("Prepared image does not match the author's expected size and CRC32")
        return bytes(output)
    finally:
        for bundle in opened:
            bundle.close()


def prepare(system: str, sd: Path, fetcher, importer, dry_run: bool = False,
            data_dir: Path = DATA, game_key: str | None = None,
            include_prom: bool = False) -> tuple[int, int, int]:
    """Download only needed sources and hand exact images to the existing safe importer."""
    if system not in ("mcr", "universal"):
        raise ArcadeError("Arcade system must be mcr or universal")
    recipe_doc, sources, image_doc = catalogs(data_dir)
    images = {(x["system"], x["key"]): x for x in image_doc["images"]}
    recipes = [r for r in recipe_doc["recipes"] if r["system"] == system and
               (game_key is None or r["key"] == game_key)]
    if not recipes:
        raise ArcadeError("No arcade recipe matches the selected game")
    recipes = [r for r in recipes if r.get("archive209_verified")]
    if not recipes:
        raise ArcadeError("Selected game has no checksum-verified source in the pinned Archive.org collection")
    folder = "MCR" if system == "mcr" else "Universal"
    pending = []
    current = 0
    for recipe in recipes:
        image = images[(system, recipe["key"])]
        target = sd / "roms" / folder / image["filename"]
        if target.is_file() and not target.is_symlink():
            if target.stat().st_size == image["size"]:
                digest = (hashlib.sha256(target.read_bytes()).hexdigest() if image.get("sha256") else
                          hashlib.md5(target.read_bytes()).hexdigest())
                if digest == (image.get("sha256") or image["md5"]):
                    current += 1
                    continue
        pending.append(recipe)
    prom_path = sd / "cores" / "alanswx.MCR" / "ssio.prom"
    prom_hash = "4962a47f67ce0cebc655026efed495eb17fc29e7072650ecab2cecc4f16c06dc"
    need_prom = system == "mcr" and include_prom and not (
        prom_path.is_file() and not prom_path.is_symlink() and prom_path.stat().st_size == 32 and
        hashlib.sha256(prom_path.read_bytes()).hexdigest() == prom_hash)
    if need_prom and not pending:
        pending.append(recipes[0])
        current -= 1
    if not pending:
        print(f"{system.upper()} arcade: 0 installed, {current} current, 0 unavailable or mismatched.")
        return 0, current, 0
    archive_bytes = {}
    failures = 0
    built = []
    prom_included = False
    with tempfile.TemporaryDirectory(prefix="update-most-arcade-") as scratch:
        prepared = Path(scratch) / "prepared.zip"
        with zipfile.ZipFile(prepared, "w", zipfile.ZIP_DEFLATED) as output:
            if need_prom:
                try:
                    prom_zip = source_zip("midssio.zip", sources, fetcher)
                    with zipfile.ZipFile(io.BytesIO(prom_zip)) as bundle:
                        matches = [info for info in bundle.infolist()
                                   if info.file_size == 32 and info.CRC == 0xe1281ee9]
                        if len(matches) != 1:
                            raise ArcadeError("MCR timing PROM missing from verified Archive ZIP")
                        prom = bundle.read(matches[0])
                    if hashlib.sha256(prom).hexdigest() != prom_hash:
                        raise ArcadeError("MCR timing PROM SHA-256 mismatch")
                    output.writestr("cores/alanswx.MCR/ssio.prom", prom)
                    prom_included = True
                except Exception as exc:
                    print("MCR timing PROM: " + str(exc))
                    failures += 1
            for recipe in pending:
                needed = [name for name in recipe["zips"] if name in sources["files"]]
                for name in needed:
                    if name not in archive_bytes:
                        try:
                            archive_bytes[name] = source_zip(name, sources, fetcher)
                        except Exception as exc:
                            archive_bytes[name] = None
                            print("Arcade source unavailable: " + str(exc))
                try:
                    image = assemble(recipe, {name: archive_bytes[name] for name in needed
                                              if archive_bytes[name] is not None})
                    item = images[(system, recipe["key"])]
                    digest = (hashlib.sha256(image).hexdigest() if item.get("sha256") else
                              hashlib.md5(image).hexdigest())
                    if len(image) != item["size"] or digest != (item.get("sha256") or item["md5"]):
                        raise ArcadeError("Prepared image differs from the core author's published hash")
                    output.writestr(f"roms/{folder}/{item['filename']}", image)
                    built.append(recipe["key"])
                except (ArcadeError, zipfile.BadZipFile, OSError) as exc:
                    failures += 1
                    print(f"Arcade {recipe['key']}: {exc}")
        if built:
            installed, already = importer(sd, prepared, system, dry_run, data_dir / "arcade_images.json")
            if prom_included:
                installed -= 1
                print("MCR timing PROM: " + ("ready to install" if dry_run else "installed"))
            current += already
        else:
            installed = 0
    print(f"{system.upper()} arcade: {installed} {'ready' if dry_run else 'installed'}, "
          f"{current} current, {failures} unavailable or mismatched.")
    return installed, current, failures
