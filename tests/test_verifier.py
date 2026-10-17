import contextlib
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
import verify_all as v

HERE = Path(__file__).resolve().parents[1]


class TestVerifier(unittest.TestCase):
    def test_all_curated_entries_can_be_staged_from_valid_synthetic_packages(self):
        """Exercises all 10 IDs with simulated binaries, NOT the live GitHub ZIPs."""
        catalog = u.load_catalog(str(HERE / "catalog.json"))
        snapshot = json.loads((HERE / "audit/verification_snapshot.json").read_text())
        specs = {e["id"]: e for e in snapshot["entries"]}
        assert len(specs) == len(catalog["cores"]) == 10
        packages = {}
        for c in catalog["cores"]:
            x = specs[c["id"]]
            metadata = {"metadata": {"id": c["id"], "name": c["name"], "author": "Audit fixture"},
                        "bitstreams": [{"target": "gamebub_rev4", "filename": x["bitstream"]}]}
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
                path = "download/cores/" + c["id"] + "/"
                zipf.writestr(path + "core.json", json.dumps(metadata))
                zipf.writestr(path + x["bitstream"], b"MOCK BITSTREAM not intended for hardware")
            packages[c["source"]["repo"]] = (metadata, buf.getvalue())
        def resolve(src):
            meta, package = packages[src["repo"]]
            tag = specs[meta["metadata"]["id"]]["tag"] + "-testfixture"
            return tag, "https://github.com/" + src["repo"] + "/releases/download/test/mock.zip", u.sha256(package), src["repo"]
        def fetch(url, limit=u.MAX_DOWNLOAD, hosts=None):
            for repo, (meta, package) in packages.items():
                if repo in url:
                    return json.dumps(meta).encode() if url.startswith("https://raw.githubusercontent.com/") else package
            raise Exception("Unknown mocked URL " + url)
        with tempfile.TemporaryDirectory() as d:
            report = Path(d) / "verified.json"
            with patch.object(u, "resolve_release", side_effect=resolve), patch.object(u, "fetch", side_effect=fetch):
                with contextlib.redirect_stdout(io.StringIO()):
                    result = v.run(["--channel", "beta", "--report", str(report)])
            self.assertEqual(result, 0)
            data = json.loads(report.read_text())
            self.assertEqual(data["passed"], 10)
            self.assertTrue(all(x["simulated_install_verified"] for x in data["entries"]))
            self.assertTrue(all(not x["hardware_verified"] for x in data["entries"]))


if __name__ == "__main__":
    unittest.main()