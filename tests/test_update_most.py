import io
import base64
from contextlib import redirect_stdout
import json
import hashlib
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import update_most as u

CORE_ID = "Tests.Demo"


def package(version="1.0", bit=b"BITSTREAM", suffix="", extra=None):
    meta = {"metadata": {"id": CORE_ID, "name": "Demo Core", "author": "Tests", "version": version},
            "bitstreams": [{"target": "gamebub_rev4", "filename": "Demo-gamebub_rev4.bit"}]}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        root = "release/cores/" + CORE_ID + "/"
        z.writestr(root + "core.json", json.dumps(meta))
        z.writestr(root + "Demo-gamebub_rev4.bit", bit)
        z.writestr(root + "settings.json", '{"settings": []}')
        for name, val in (extra or {}).items():
            z.writestr(root + name, val)
    return buf.getvalue()


class TestUpdateMost(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sd = Path(self.tmp.name) / "CARD"
        self.sd.mkdir()
        self.sd.joinpath("cores").mkdir()
        self.state = {"schema": 1, "installed": {}}

    def tearDown(self):
        self.tmp.cleanup()

    def test_install_and_update_backups_and_save_preserved(self):
        first = u.unpack_core(package(), CORE_ID, "gamebub_rev4")
        u.deploy(self.sd, CORE_ID, first, "v1", u.sha256(package()), self.state,
                 adopt=False, force=False, dry_run=False)
        root = self.sd / "cores" / CORE_ID
        self.assertEqual((root / "Demo-gamebub_rev4.bit").read_bytes(), b"BITSTREAM")
        (root / "MyGame.sav").write_bytes(b"MY SAVE")
        second = u.unpack_core(package("2", b"BIT 2"), CORE_ID, "gamebub_rev4")
        u.deploy(self.sd, CORE_ID, second, "v2", "xyz", self.state,
                 adopt=False, force=False, dry_run=False)
        self.assertEqual((root / "MyGame.sav").read_bytes(), b"MY SAVE")
        self.assertEqual((root / "Demo-gamebub_rev4.bit").read_bytes(), b"BIT 2")
        backup = self.sd / ".update_most" / "backups" / CORE_ID
        self.assertTrue(any(backup.rglob("Demo-gamebub_rev4.bit")))
        self.assertEqual(u.load_state(self.sd)["installed"][CORE_ID]["version"], "v2")

    def test_unmanaged_overwrite_refused_until_adopt(self):
        root = self.sd / "cores" / CORE_ID
        root.mkdir()
        (root / "core.json").write_text("manually installed")
        contents = u.unpack_core(package(), CORE_ID, "gamebub_rev4")
        with self.assertRaisesRegex(u.UpdaterError, "unmanaged"):
            u.deploy(self.sd, CORE_ID, contents, "v1", "hash", self.state,
                     adopt=False, force=False, dry_run=False)
        u.deploy(self.sd, CORE_ID, contents, "v1", "hash", self.state,
                 adopt=True, force=False, dry_run=False)
        self.assertEqual(json.loads((root / "core.json").read_text())["metadata"]["id"], CORE_ID)

    def test_modified_managed_file_protected(self):
        contents = u.unpack_core(package(), CORE_ID, "gamebub_rev4")
        u.deploy(self.sd, CORE_ID, contents, "v1", "hash", self.state,
                 adopt=False, force=False, dry_run=False)
        (self.sd / "cores" / CORE_ID / "core.json").write_text("local changes")
        with self.assertRaisesRegex(u.UpdaterError, "Locally modified"):
            u.deploy(self.sd, CORE_ID, contents, "v2", "hash2", self.state,
                     adopt=False, force=False, dry_run=False)

    def test_missing_hardware_bitstream(self):
        with self.assertRaisesRegex(u.UpdaterError, "No bitstream"):
            u.unpack_core(package(), CORE_ID, "gamebub_rev2")

    def test_zip_path_traversal_rejected(self):
        b = io.BytesIO(package())
        # Reassemble from existing valid archive, then add suspicious file.
        with zipfile.ZipFile(b, "a") as z:
            z.writestr("../../outside.txt", "bad")
        with self.assertRaisesRegex(u.UpdaterError, "Unsafe"):
            u.unpack_core(b.getvalue(), CORE_ID, "gamebub_rev4")
        self.assertFalse((self.sd / "outside.txt").exists())

    def test_symlink_zip_rejected(self):
        b = io.BytesIO(package())
        with zipfile.ZipFile(b, "a") as z:
            i = zipfile.ZipInfo("release/cores/Tests.Demo/link")
            i.create_system = 3
            i.external_attr = (0o120777 << 16)
            z.writestr(i, "../../foo")
        with self.assertRaisesRegex(u.UpdaterError, "symbolic link"):
            u.unpack_core(b.getvalue(), CORE_ID, "gamebub_rev4")

    def test_zip_preserves_rom_and_bios(self):
        content = u.unpack_core(package(extra={"SomeGame.sms": b"no", "bios.bin": b"no", "assets/font.bin": b"yes"}), CORE_ID, "gamebub_rev4")
        self.assertNotIn("SomeGame.sms", content)
        self.assertNotIn("bios.bin", content)
        self.assertIn("assets/font.bin", content)

    def test_dry_run_writes_nothing(self):
        content = u.unpack_core(package(), CORE_ID, "gamebub_rev4")
        u.deploy(self.sd, CORE_ID, content, "v1", "hash", self.state,
                 adopt=False, force=False, dry_run=True)
        self.assertFalse((self.sd / ".update_most").exists())
        self.assertFalse((self.sd / "cores" / CORE_ID).exists())

    def test_release_catalog_validation_and_mock_end_to_end(self):
        archive = package()
        config = {"schema": 1, "cores": [{"id": CORE_ID, "name": "Demo", "source": {
            "type": "url", "url": "https://example.org/test.zip", "version": "v1", "sha256": u.sha256(archive)}}]}
        cpath = Path(self.tmp.name) / "catalog.json"
        cpath.write_text(json.dumps(config))
        with patch.object(u, "fetch", return_value=archive):
            rc = u.main(["--sd", str(self.sd), "--catalog", str(cpath)])
        self.assertEqual(rc, 0)
        self.assertTrue((self.sd / "cores" / CORE_ID / "core.json").exists())

    def test_same_version_repairs_deleted_files(self):
        archive = package()
        config = {"schema": 1, "cores": [{"id": CORE_ID, "name": "Demo", "source": {
            "type": "url", "url": "https://example.org/test.zip", "version": "v1", "sha256": u.sha256(archive)}}]}
        cpath = Path(self.tmp.name) / "catalog.json"
        cpath.write_text(json.dumps(config))
        with patch.object(u, "fetch", return_value=archive):
            self.assertEqual(u.main(["--sd", str(self.sd), "--catalog", str(cpath)]), 0)
        bitstream = self.sd / "cores" / CORE_ID / "Demo-gamebub_rev4.bit"
        bitstream.unlink()
        with patch.object(u, "fetch", return_value=archive):
            self.assertEqual(u.main(["--sd", str(self.sd), "--catalog", str(cpath)]), 0)
        self.assertEqual(bitstream.read_bytes(), b"BITSTREAM")

    def test_bad_sha_rejected_no_changes(self):
        config = {"schema": 1, "cores": [{"id": CORE_ID, "name": "Demo", "source": {
            "type": "url", "url": "https://example.org/test.zip", "version": "v1", "sha256": "b" * 64}}]}
        cpath = Path(self.tmp.name) / "catalog.json"
        cpath.write_text(json.dumps(config))
        with patch.object(u, "fetch", return_value=package()):
            self.assertEqual(u.main(["--sd", str(self.sd), "--catalog", str(cpath)]), 1)
        self.assertFalse((self.sd / "cores" / CORE_ID).exists())

    def test_unsafe_sd_root_refused(self):
        with self.assertRaisesRegex(u.UpdaterError, "Refusing"):
            u.ensure_safe_root(Path("/"), init=False, dry_run=True)

    def test_published_single_segment_ids(self):
        for core_id in ("NES", "SNES", "PICO-8"):
            self.assertTrue(u.ID_RE.fullmatch(core_id))
        for bad in ("../unsafe", "a/b", "", "bad id"):
            self.assertFalse(u.ID_RE.fullmatch(bad))

    def test_shipped_catalog_is_valid_and_has_rev4_releases(self):
        cat = u.load_catalog(str(Path(__file__).resolve().parents[1] / "catalog.json"))
        ids = {entry["id"] for entry in cat["cores"]}
        self.assertGreaterEqual(len(ids), 10)
        self.assertTrue({"NES", "SNES", "PICO-8", "alanswx.MCR", "alanswx.Universal", "Sega8bit.Dev"}.issubset(ids))
        for entry in cat["cores"]:
            self.assertEqual(entry["hardware"], ["gamebub_rev4"])

    def test_no_changes_with_blank_catalog(self):
        cpath = Path(self.tmp.name) / "catalog.json"
        cpath.write_text('{"schema":1,"cores":[]}')
        rc = u.main(["--sd", str(self.sd), "--catalog", str(cpath)])
        self.assertEqual(rc, 0)
        self.assertEqual(sorted(p.name for p in self.sd.iterdir()), ["cores"])

    def test_verify_restore_and_uninstall_preserve_user_files(self):
        first = u.unpack_core(package(), CORE_ID, "gamebub_rev4")
        second = u.unpack_core(package("2", b"BIT 2"), CORE_ID, "gamebub_rev4")
        u.deploy(self.sd, CORE_ID, first, "v1", "a" * 64, self.state,
                 adopt=False, force=False, dry_run=False)
        user_file = self.sd / "cores" / CORE_ID / "MyGame.sav"
        user_file.write_bytes(b"SAVE")
        u.deploy(self.sd, CORE_ID, second, "v2", "b" * 64, self.state,
                 adopt=False, force=False, dry_run=False)
        self.assertEqual(u.verify_installation(self.sd, self.state)[CORE_ID], [])
        restored = u.restore_core(self.sd, self.state, CORE_ID)
        self.assertTrue((restored / "manifest.json").is_file())
        self.assertEqual(self.state["installed"][CORE_ID]["version"], "v1")
        self.assertEqual((self.sd / "cores" / CORE_ID / "Demo-gamebub_rev4.bit").read_bytes(), b"BITSTREAM")
        self.assertEqual(user_file.read_bytes(), b"SAVE")
        u.uninstall_core(self.sd, self.state, CORE_ID)
        self.assertEqual(user_file.read_bytes(), b"SAVE")
        self.assertFalse((self.sd / "cores" / CORE_ID / "core.json").exists())
        self.assertNotIn(CORE_ID, u.load_state(self.sd)["installed"])

    def test_management_refuses_modified_managed_file(self):
        contents = u.unpack_core(package(), CORE_ID, "gamebub_rev4")
        u.deploy(self.sd, CORE_ID, contents, "v1", "a" * 64, self.state,
                 adopt=False, force=False, dry_run=False)
        (self.sd / "cores" / CORE_ID / "core.json").write_text("changed")
        self.assertIn(("core.json", "modified"), u.verify_installation(self.sd, self.state)[CORE_ID])
        with self.assertRaisesRegex(u.UpdaterError, "locally modified"):
            u.uninstall_core(self.sd, self.state, CORE_ID)

    def test_check_only_does_not_download_or_write(self):
        archive = package()
        config = {"schema": 1, "cores": [{"id": CORE_ID, "name": "Demo", "source": {
            "type": "url", "url": "https://example.org/test.zip", "version": "v1", "sha256": u.sha256(archive)}}]}
        cpath = Path(self.tmp.name) / "catalog.json"
        cpath.write_text(json.dumps(config))
        with patch.object(u, "fetch", side_effect=AssertionError("unexpected download")):
            self.assertEqual(u.main(["--sd", str(self.sd), "--catalog", str(cpath), "--check-only"]), 0)
        self.assertFalse((self.sd / ".update_most").exists())

    def test_init_creates_game_bub_layout(self):
        fresh = Path(self.tmp.name) / "NEW_CARD"
        fresh.mkdir()
        u.ensure_safe_root(fresh, init=True, dry_run=False)
        self.assertTrue((fresh / "cores").is_dir())
        self.assertTrue((fresh / "system").is_dir())
        self.assertTrue((fresh / "roms").is_dir())
        self.assertFalse((fresh / ".update_most").exists())

    def test_macos_card_format_and_new_card_discovery(self):
        blank = Path(self.tmp.name) / "BLANK"
        blank.mkdir()
        volume = {"MountPoint": str(blank), "ParentWholeDisk": "disk4", "Content": "Windows_FAT_32",
                  "RemovableMediaOrExternalDevice": True, "VolumeSize": 32 * 1024 ** 3, "FreeSpace": 31 * 1024 ** 3}
        whole = {"Content": "FDisk_partition_scheme"}
        with patch.object(u, "mac_diskutil_plist", side_effect=[volume, whole]):
            info = u.mac_card_info(blank)
        self.assertIsNone(u.card_format_issue(info))
        listing = {"AllDisksAndPartitions": [{"Partitions": [{"Content": "Windows_FAT_32",
                    "MountPoint": str(blank)}]}]}
        self.assertIn(blank, u.mac_external_fat32_mounts(listing))

    def test_bad_card_format_blocks_writes_but_allows_read_only_inspection(self):
        wrong = {"filesystem": "ExFAT", "scheme": "GUID_partition_scheme", "removable": True}
        with patch.object(u, "mac_card_info", return_value=wrong):
            with self.assertRaisesRegex(u.UpdaterError, "FAT32 on an MBR"):
                u.ensure_safe_root(self.sd, False, False)
            self.assertEqual(u.ensure_safe_root(self.sd, False, True), self.sd.resolve())

    def test_health_report_checks_required_bios_and_firmware_without_writes(self):
        core_dir = self.sd / "cores" / CORE_ID
        core_dir.mkdir()
        (core_dir / "core.json").write_text(json.dumps({"metadata": {"id": CORE_ID}}))
        catalog = {"schema": 1, "cores": [{"id": CORE_ID, "name": "Demo",
                   "requires_firmware": "v1.1-beta2 or newer"}],
                   "bios": [{"id": "boot", "name": "Required boot ROM", "core_id": CORE_ID,
                             "destination": "cores/Tests.Demo/boot.rom", "size": 4, "required": True}]}
        report = u.installation_health(self.sd, catalog, self.state, "gamebub_rev4", "stable", "v1.0.2")
        self.assertEqual(report["bios_missing"], ["Required boot ROM"])
        self.assertEqual(report["firmware_incompatible"], [CORE_ID])
        self.assertFalse((self.sd / ".update_most").exists())
        (core_dir / "boot.rom").write_bytes(b"BOOT")
        report = u.installation_health(self.sd, catalog, self.state, "gamebub_rev4", "stable", "v1.1-beta2")
        self.assertEqual(report["bios_missing"], [])
        self.assertEqual(report["firmware_incompatible"], [])
        self.assertTrue(u.print_health_report(report))

    def test_independent_databases_merge_and_reject_conflicts(self):
        source = {"type": "url", "url": "https://example.org/demo.zip", "version": "1", "sha256": "a" * 64}
        primary = {"schema": 1, "cores": [{"id": "Main", "name": "Main", "source": source}]}
        extra = {"schema": 1, "database_id": "community", "cores": [
            {"id": "Extra", "name": "Extra", "source": source}]}
        main_path = Path(self.tmp.name) / "main.json"
        extra_path = Path(self.tmp.name) / "extra.json"
        main_path.write_text(json.dumps(primary))
        extra_path.write_text(json.dumps(extra))
        merged = u.merge_catalogs(u.load_catalog(str(main_path)), [u.load_catalog(str(extra_path))])
        self.assertEqual({core["id"] for core in merged["cores"]}, {"Main", "Extra"})
        self.assertEqual(merged["cores"][1]["database_id"], "community")
        with self.assertRaisesRegex(u.UpdaterError, "Core ID conflicts"):
            u.merge_catalogs(u.load_catalog(str(main_path)), [{**extra, "cores": primary["cores"]}])

    def test_settings_persist_on_card(self):
        settings = u.load_settings(self.sd)
        self.assertEqual(settings["channel"], "beta")
        settings["channel"] = "stable"
        settings["databases"] = ["https://example.org/extra.json"]
        u.save_settings(self.sd, settings)
        self.assertEqual(u.load_settings(self.sd), settings)

    def test_core_filter_only_installs_selected_core(self):
        archive = package()
        source = {"type": "url", "url": "https://example.org/test.zip", "version": "v1", "sha256": u.sha256(archive)}
        config = {"schema": 1, "cores": [
            {"id": CORE_ID, "name": "Demo", "source": source},
            {"id": "Other.Core", "name": "Other", "source": source}]}
        cpath = Path(self.tmp.name) / "catalog.json"
        cpath.write_text(json.dumps(config))
        with patch.object(u, "fetch", return_value=archive):
            self.assertEqual(u.main(["--sd", str(self.sd), "--catalog", str(cpath), "--core", CORE_ID]), 0)
        self.assertTrue((self.sd / "cores" / CORE_ID / "core.json").is_file())
        self.assertFalse((self.sd / "cores" / "Other.Core").exists())

    def test_verified_cache_reuses_package_and_rejects_corruption(self):
        archive = package()
        digest = u.sha256(archive)
        with patch.object(u, "fetch", return_value=archive) as fetcher:
            self.assertEqual(u.obtain_package(self.sd, "https://example.org/test.zip", digest, None, False), archive)
            self.assertEqual(u.obtain_package(self.sd, "https://example.org/test.zip", digest, None, False), archive)
            self.assertEqual(fetcher.call_count, 1)
            cache = self.sd / ".update_most" / "cache" / (digest + ".zip")
            cache.write_bytes(b"corrupt")
            self.assertEqual(u.obtain_package(self.sd, "https://example.org/test.zip", digest, None, False), archive)
            self.assertEqual(fetcher.call_count, 2)

    def test_official_firmware_is_verified_and_only_saved_to_chosen_folder(self):
        block = bytearray(512)
        struct.pack_into("<8I", block, 0, 0x0A324655, 0x9E5D5157, 0, 0x1000, 256, 0, 1, 0)
        struct.pack_into("<I", block, 508, 0x0AB16F30)
        uf2 = bytes(block)
        digest = hashlib.sha256(uf2).hexdigest()
        asset_url = "https://github.com/elipsitz/gamebub/releases/download/v1.0.2/gamebub-rev4_v1.0.2.uf2"
        metadata = {"tag_name": "v1.0.2", "html_url": "https://github.com/elipsitz/gamebub/releases/tag/v1.0.2",
                    "assets": [{"name": "gamebub-rev4_v1.0.2.uf2", "size": len(uf2),
                                "digest": "sha256:" + digest, "browser_download_url": asset_url}]}
        release = u.official_firmware_release(lambda *_: json.dumps(metadata).encode())
        output = Path(self.tmp.name) / "downloads"
        output.mkdir()
        self.assertEqual(u.download_official_firmware(output, release, lambda *_: uf2).read_bytes(), uf2)
        self.assertFalse((self.sd / ".update_most").exists())
        (output / release["name"]).unlink()
        with self.assertRaisesRegex(u.UpdaterError, "SHA-256 mismatch"):
            u.download_official_firmware(output, release, lambda *_: bytes(512))
        self.assertFalse((output / release["name"]).exists())

    def test_arcade_builder_requires_pinned_hash(self):
        output = Path(self.tmp.name) / "builders"
        output.mkdir()
        html = b"<!doctype html><title>Local test builder</title>"
        url = "https://raw.githubusercontent.com/example/project/commit/builder.html"
        with patch.dict(u.ARCADE_BUILDERS, {"mcr": (url, u.sha256(html))}):
            with self.assertRaisesRegex(u.UpdaterError, "SHA-256 mismatch"):
                u.download_arcade_builder("mcr", output, lambda *_: b"wrong")
            self.assertFalse((output / "MCR-ROM-Builder.html").exists())
            self.assertEqual(u.download_arcade_builder("mcr", output, lambda *_: html).read_bytes(), html)

    def test_beta_firmware_and_readme_requirement(self):
        asset_url = "https://github.com/danisla/gamebub-nes/releases/download/v1.0.0/gamebub-rev4_v1.1-beta2.uf2"
        metadata = {"tag_name": "v1.0.0", "html_url": "https://github.com/danisla/gamebub-nes/releases/tag/v1.0.0",
                    "assets": [{"name": "gamebub-rev4_v1.1-beta2.uf2", "size": 8560640,
                                "digest": "sha256:" + u.CORE_LOADING_BETA_SHA256, "browser_download_url": asset_url}]}
        release = u.firmware_release("core-loading-beta", lambda *_: json.dumps(metadata).encode())
        self.assertEqual(release["version"], "v1.1-beta2")
        self.assertEqual(release["source_repo"], "danisla/gamebub-nes")
        readme = b"# NES\nRequires Game Bub firmware v1.1-beta2 or later.\nOther details.\n"
        response = {"encoding": "base64", "content": base64.b64encode(readme).decode()}
        self.assertIn("v1.1-beta2", u.readme_firmware_notes("danisla/gamebub-nes",
                                                           lambda *_: json.dumps(response).encode())[0])

    def test_check_only_reads_core_readme_firmware_notes(self):
        catalog = {"schema": 1, "cores": [{"id": CORE_ID, "name": "Demo",
            "requires_firmware": "v1.1-beta2 or newer", "source": {
                "type": "github_release", "repo": "danisla/gamebub-nes", "asset": "demo.zip"}}]}
        cpath = Path(self.tmp.name) / "catalog.json"
        cpath.write_text(json.dumps(catalog))
        output = io.StringIO()
        with patch.object(u, "resolve_release", return_value=("v1", "https://example.org/demo.zip", "a" * 64,
                                                               "danisla/gamebub-nes")), \
             patch.object(u, "readme_firmware_notes", return_value=["Requires firmware v1.1-beta2"]), \
             redirect_stdout(output):
            self.assertEqual(u.main(["--sd", str(self.sd), "--catalog", str(cpath), "--check-only"]), 0)
        self.assertIn("README: Requires firmware v1.1-beta2", output.getvalue())

    def test_firmware_compatibility_uses_readme_and_reported_version(self):
        core = {"requires_firmware": "core-loading v1.1 beta family"}
        notes = ["Requires firmware v1.1-beta2 or later"]
        self.assertIn("incompatible", u.firmware_compatibility(core, notes, "v1.0.2"))
        self.assertIn("incompatible", u.firmware_compatibility(core, notes, "v1.1-beta1"))
        self.assertIn("meets known minimum", u.firmware_compatibility(core, notes, "v1.1-beta2"))
        self.assertIn("unknown", u.firmware_compatibility(core, notes, None))
        custom = {"requires_firmware": "custom core-loading v1.1 beta firmware"}
        self.assertIn("manual review", u.firmware_compatibility(custom, [], "v1.1-beta2"))

    def test_core_browser_filters_category_and_release_notes(self):
        source = {"type": "github_release", "repo": "danisla/gamebub-nes", "asset": "demo.zip"}
        catalog = {"cores": [{"id": "NES", "name": "NES", "category": "Console", "source": source},
                             {"id": "Arcade", "name": "Arcade", "category": "Arcade", "channel": "beta",
                              "source": source}]}
        self.assertEqual([core["id"] for core in u.browse_cores(catalog, "gamebub_rev4", "stable")], ["NES"])
        self.assertEqual([core["id"] for core in u.browse_cores(catalog, "gamebub_rev4", "beta", "Arcade")],
                         ["Arcade"])
        release = {"html_url": "https://github.com/danisla/gamebub-nes/releases/tag/v1.0.0",
                   "body": "Fixed SD card loading."}
        url, notes = u.github_release_notes(source, lambda *_: json.dumps(release).encode())
        self.assertIn("/v1.0.0", url)
        self.assertIn("SD card", notes)

    def test_check_only_reports_beta_firmware_mismatch(self):
        catalog = {"schema": 1, "cores": [{"id": CORE_ID, "name": "Demo",
            "requires_firmware": "v1.1-beta2 or newer", "source": {
                "type": "github_release", "repo": "danisla/gamebub-nes", "asset": "demo.zip"}}]}
        cpath = Path(self.tmp.name) / "catalog.json"
        cpath.write_text(json.dumps(catalog))
        output = io.StringIO()
        with patch.object(u, "resolve_release", return_value=("v1", "https://example.org/demo.zip", "a" * 64,
                                                               "danisla/gamebub-nes")), \
             patch.object(u, "readme_firmware_notes", return_value=["Requires firmware v1.1-beta2"]), \
             redirect_stdout(output):
            self.assertEqual(u.main(["--sd", str(self.sd), "--catalog", str(cpath), "--check-only",
                                     "--installed-firmware", "v1.0.2"]), 0)
        self.assertIn("Firmware incompatible", output.getvalue())

    def test_arcade_import_checks_exact_image_and_preserves_existing(self):
        image = b"synthetic prepared arcade image"
        manifest = {"schema": 1, "images": [{"system": "universal", "key": "demo",
            "filename": "Demo.rom", "size": len(image), "sha256": u.sha256(image), "md5": None}]}
        manifest_path = Path(self.tmp.name) / "arcade.json"
        manifest_path.write_text(json.dumps(manifest))
        archive = Path(self.tmp.name) / "prepared.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("roms/Universal/Demo.rom", image)
        self.assertEqual(u.import_arcade_images(self.sd, archive, "universal", True, manifest_path), (1, 0))
        self.assertFalse((self.sd / "roms").exists())
        self.assertEqual(u.import_arcade_images(self.sd, archive, "universal", False, manifest_path), (1, 0))
        target = self.sd / "roms" / "Universal" / "Demo.rom"
        self.assertEqual(target.read_bytes(), image)
        self.assertEqual(u.import_arcade_images(self.sd, archive, "universal", False, manifest_path), (0, 1))
        target.write_bytes(b"user modified")
        with self.assertRaisesRegex(u.UpdaterError, "preserving"):
            u.import_arcade_images(self.sd, archive, "universal", False, manifest_path)
        self.assertEqual(target.read_bytes(), b"user modified")

    def test_arcade_import_rejects_unexpected_zip_member(self):
        manifest_path = Path(self.tmp.name) / "arcade.json"
        manifest_path.write_text('{"schema":1,"images":[]}')
        archive = Path(self.tmp.name) / "bad.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("roms/Universal/Unknown.rom", b"bad")
        with self.assertRaisesRegex(u.UpdaterError, "Unexpected"):
            u.import_arcade_images(self.sd, archive, "universal", False, manifest_path)
        self.assertFalse((self.sd / "roms").exists())

    def test_update_everything_runs_arcade_for_installed_core_unless_skipped(self):
        core = self.sd / "cores" / "alanswx.MCR"
        core.mkdir()
        (core / "core.json").write_text("{}")
        catalog = Path(self.tmp.name) / "empty-catalog.json"
        catalog.write_text('{"schema":1,"cores":[],"bios":[]}')
        with patch.object(u, "auto_arcade_images", return_value=0) as arcade, redirect_stdout(io.StringIO()):
            self.assertEqual(u.main(["--sd", str(self.sd), "--catalog", str(catalog),
                                     "--dry-run", "--skip-bios"]), 0)
            arcade.assert_called_once_with(self.sd.resolve(), "mcr", True)
            arcade.reset_mock()
            self.assertEqual(u.main(["--sd", str(self.sd), "--catalog", str(catalog),
                                     "--dry-run", "--skip-bios", "--skip-arcade"]), 0)
            arcade.assert_not_called()

    def test_eject_requires_removable_mount_and_uses_diskutil(self):
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, "Disk ejected", "")
        with patch.object(u, "mac_card_info", return_value=None), patch.object(u.os, "sync"):
            with self.assertRaisesRegex(u.UpdaterError, "mounted external/removable"):
                u.eject_sd_card(self.sd, runner=runner, platform="darwin")
        self.assertEqual(calls, [])
        info = {"removable": True, "filesystem": "Windows_FAT_32", "scheme": "FDisk_partition_scheme"}
        with patch.object(u, "mac_card_info", return_value=info), patch.object(u.os, "sync") as sync:
            u.eject_sd_card(self.sd, runner=runner, platform="darwin")
            sync.assert_called_once()
        self.assertEqual(calls, [["diskutil", "eject", str(self.sd.resolve())]])

    def test_linux_eject_checks_mount_and_parent_disk(self):
        sd = str(self.sd.resolve())
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
            if args[:4] == ["findmnt", "-n", "-o", "TARGET"]:
                value = sd
            elif args[:4] == ["findmnt", "-n", "-o", "SOURCE"]:
                value = "/dev/sdb1"
            elif args[0] == "lsblk" and "PKNAME" in args:
                value = "sdb"
            elif args[0] == "lsblk":
                value = "1 usb"
            else:
                value = "done"
            return subprocess.CompletedProcess(args, 0, value, "")
        with patch.object(u, "mac_card_info", return_value=None), patch.object(u.os, "sync"):
            u.eject_sd_card(self.sd, runner=runner, platform="linux")
        self.assertEqual(calls[-2:], [["udisksctl", "unmount", "-b", "/dev/sdb1"],
                                      ["udisksctl", "power-off", "-b", "/dev/sdb"]])


if __name__ == "__main__":
    unittest.main()
