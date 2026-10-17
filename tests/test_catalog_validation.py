# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Update_Most contributors
"""Synthetic tests for the offline catalog provenance validator.

Developed with OpenAI ChatGPT assistance.
"""
import copy
import tempfile
import unittest
from pathlib import Path

import validate_catalog as validator
import update_most


class TestCatalogProvenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live_catalog = update_most.load_catalog(str(Path(__file__).parents[1] / "catalog.json"))

    def test_real_catalog_has_no_validation_errors(self):
        errors, warnings = validator.validate_records(self.live_catalog)
        self.assertEqual(errors, [])
        self.assertTrue(warnings)  # Sources with an unresolved upstream license are disclosed.

    def test_real_catalog_strict_license_mode_rejects_unverified(self):
        errors, warnings = validator.validate_records(self.live_catalog, True)
        self.assertTrue(any("not independently verified" in e for e in errors))
        self.assertFalse(warnings)

    def test_missing_attribution_rejected(self):
        doc = copy.deepcopy(self.live_catalog)
        del doc["cores"][0]["upstream"]
        errors, _ = validator.validate_records(doc)
        self.assertTrue(any("attribution" in e for e in errors))

    def test_blank_author_rejected(self):
        doc = copy.deepcopy(self.live_catalog)
        doc["cores"][0]["upstream"]["author"] = " "
        errors, _ = validator.validate_records(doc)
        self.assertTrue(any("upstream.author" in e for e in errors))

    def test_non_reference_only_rejected(self):
        doc = copy.deepcopy(self.live_catalog)
        doc["cores"][0]["upstream"]["reference_only"] = False
        errors, _ = validator.validate_records(doc)
        self.assertTrue(any("reference_only" in e for e in errors))

    def test_invalid_hardware_rejected(self):
        doc = copy.deepcopy(self.live_catalog)
        doc["cores"][0]["hardware"] = ["gamebub_rev4", "malicious_board"]
        errors, _ = validator.validate_records(doc)
        self.assertTrue(any("hardware" in e for e in errors))

    def test_duplicate_hardware_rejected(self):
        doc = copy.deepcopy(self.live_catalog)
        doc["cores"][0]["hardware"] = ["gamebub_rev4", "gamebub_rev4"]
        errors, _ = validator.validate_records(doc)
        self.assertTrue(any("hardware" in e for e in errors))

    def test_redirected_homepage_rejected(self):
        doc = copy.deepcopy(self.live_catalog)
        doc["cores"][0]["homepage"] = "https://example.org/elsewhere"
        errors, _ = validator.validate_records(doc)
        self.assertTrue(any("homepage" in e for e in errors))

    def test_missing_category_rejected(self):
        doc = copy.deepcopy(self.live_catalog)
        doc["cores"][0].pop("category")
        errors, _ = validator.validate_records(doc)
        self.assertTrue(any("category" in e for e in errors))

    def test_validator_refuses_remote_catalog(self):
        self.assertNotEqual(0, validator.main(["--catalog", "https://example.com/catalog.json"]))


if __name__ == "__main__":
    unittest.main()
