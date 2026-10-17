# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Update_Most contributors
"""Synthetic CLI tests for opt-in hosted catalog selection.

Developed with assistance from OpenAI ChatGPT.
"""
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import update_most as updater


class TestCatalogTrack(unittest.TestCase):
    def setUp(self):
        self.catalog = {"schema": 1, "name": "Synthetic", "cores": []}

    def test_default_uses_bundled_local_catalog(self):
        with patch.object(updater, "load_catalog", return_value=self.catalog) as load:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(updater.main(["--list"]), 0)
        self.assertEqual(load.call_count, 1)
        self.assertTrue(load.call_args.args[0].endswith("catalog.json"))
        self.assertFalse(load.call_args.args[0].startswith("https://"))

    def test_explicit_github_track_uses_hosted_catalog(self):
        with patch.object(updater, "load_catalog", return_value=self.catalog) as load:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(updater.main(["--list", "--catalog-track", "github"]), 0)
        self.assertEqual(load.call_args.args[0], updater.COMMUNITY_CATALOG_URL)

    def test_explicit_url_overrides_track(self):
        url = "https://example.org/reviewed.json"
        with patch.object(updater, "load_catalog", return_value=self.catalog) as load:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(updater.main(["--list", "--catalog-track", "github", "--catalog", url]), 0)
        self.assertEqual(load.call_args.args[0], url)

    def test_explicit_bundled_track_uses_local(self):
        with patch.object(updater, "load_catalog", return_value=self.catalog) as load:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(updater.main(["--list", "--catalog-track", "bundled"]), 0)
        self.assertFalse(load.call_args.args[0].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
