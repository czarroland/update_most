import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import arcade_auto as a
import update_most as u


class TestArcadeAuto(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sd = self.root / "card"
        self.sd.mkdir()
        self.data_dir = self.root / "data"
        self.data_dir.mkdir()
        chip = b"synthetic chip"
        self.image = chip + b"\x00\xff" * 2
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("chips/original.bin", chip)
        self.source = buf.getvalue()
        self.recipe = {"system": "universal", "key": "demo", "size": len(self.image),
                       "crc32": f"{zlib.crc32(self.image):08x}", "archive_verified": True,
                       "zips": ["demo.zip"], "parts": [
                           {"name": "original.bin", "crc": f"{zlib.crc32(chip):08x}",
                            "size": len(chip), "offset": 0, "length": len(chip), "repeat": 1},
                           {"fill": "00ff", "repeat": 2}]}
        self._write("arcade_recipes.json", {"schema": 1, "recipes": [self.recipe]})
        self._write("arcade_sources.json", {"schema": 1,
            "base_url": "https://archive.org/download/test/", "files": {"demo.zip": {
                "size": len(self.source), "sha1": hashlib.sha1(self.source).hexdigest()}}})
        self._write("arcade_images.json", {"schema": 1, "images": [{
            "system": "universal", "key": "demo", "filename": "Demo.rom",
            "size": len(self.image), "sha256": hashlib.sha256(self.image).hexdigest()}]})

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, name, value):
        (self.data_dir / name).write_text(json.dumps(value))

    def fetcher(self, url, limit, hosts):
        self.assertEqual(url, "https://archive.org/download/test/demo.zip")
        self.assertEqual(hosts, {"archive.org"})
        return self.source

    def test_assembles_and_installs_only_verified_output(self):
        self.assertEqual(a.assemble(self.recipe, {"demo.zip": self.source}), self.image)
        args = ("universal", self.sd, self.fetcher, u.import_arcade_images)
        self.assertEqual(a.prepare(*args, dry_run=True, data_dir=self.data_dir), (1, 0, 0))
        self.assertFalse((self.sd / "roms").exists())
        self.assertEqual(a.prepare(*args, data_dir=self.data_dir), (1, 0, 0))
        self.assertEqual((self.sd / "roms/Universal/Demo.rom").read_bytes(), self.image)
        self.assertEqual(a.prepare(*args, data_dir=self.data_dir), (0, 1, 0))

    def test_rejects_source_hash_mismatch_and_preserves_card(self):
        with self.assertRaisesRegex(a.ArcadeError, "SHA-1"):
            a.source_zip("demo.zip", a.catalogs(self.data_dir)[1], lambda *_: b"bad")
        self.assertEqual(a.prepare("universal", self.sd, lambda *_: b"bad",
                                   u.import_arcade_images, data_dir=self.data_dir), (0, 0, 1))
        self.assertFalse((self.sd / "roms").exists())

    def test_pinned_second_collection_url(self):
        source = a.catalogs(self.data_dir)[1]
        source["files"]["demo.zip"]["url"] = "https://archive.org/download/second/demo.zip"
        requested = []
        def fetch(url, limit, hosts):
            requested.append(url)
            return self.source
        self.assertEqual(a.source_zip("demo.zip", source, fetch), self.source)
        self.assertEqual(requested, ["https://archive.org/download/second/demo.zip"])
        source["files"]["demo.zip"]["url"] = "https://example.org/demo.zip"
        with self.assertRaisesRegex(a.ArcadeError, "Archive.org HTTPS"):
            a.source_zip("demo.zip", source, fetch)

    def test_rejects_missing_chip_and_modified_existing_image(self):
        with self.assertRaisesRegex(a.ArcadeError, "Missing chip"):
            a.assemble(self.recipe, {})
        target = self.sd / "roms/Universal/Demo.rom"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"user data")
        with self.assertRaisesRegex(u.UpdaterError, "preserving"):
            a.prepare("universal", self.sd, self.fetcher, u.import_arcade_images,
                      data_dir=self.data_dir)
        self.assertEqual(target.read_bytes(), b"user data")


if __name__ == "__main__":
    unittest.main()
