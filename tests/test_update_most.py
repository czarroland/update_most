import io
import json
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()