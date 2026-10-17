# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Update_Most contributors
"""Cross-platform tests for Windows SD drive-letter root guards.

OpenAI ChatGPT-assisted implementation. All paths here are synthetic.
"""
import tempfile
import unittest
from pathlib import Path
import update_most as u


class TestDriveRootSafety(unittest.TestCase):
    def test_nonsystem_drive_root_allowed(self):
        self.assertFalse(u.protected_windows_drive_root(
            "E:", system_drive="C:", home_drive="C:", python_drive="C:", windows_drive="C:"))

    def test_system_drive_rejected(self):
        self.assertTrue(u.protected_windows_drive_root(
            "D:", system_drive="D:", home_drive="C:", python_drive="C:"))

    def test_home_drive_rejected(self):
        self.assertTrue(u.protected_windows_drive_root(
            "E:", system_drive="C:", home_drive="E:", python_drive="C:"))

    def test_python_drive_rejected(self):
        self.assertTrue(u.protected_windows_drive_root(
            "D:", system_drive="C:", python_drive="D:"))

    def test_windows_directory_drive_rejected(self):
        self.assertTrue(u.protected_windows_drive_root(
            "E:", system_drive="C:", home_drive="C:", windows_drive="E:"))

    def test_unc_and_malformed_root_rejected(self):
        for bad in ("", "C", "/", "\\\\host\\share", "C:\\", "x:y", None):
            with self.subTest(root=bad):
                self.assertTrue(u.protected_windows_drive_root(bad, system_drive="C:"))

    def test_nonroot_path_requires_init(self):
        with tempfile.TemporaryDirectory() as tmp:
            sd=Path(tmp)/"gamebub_card"
            sd.mkdir()
            with self.assertRaises(u.UpdaterError):
                u.ensure_safe_root(sd, False, False)
            self.assertEqual(u.ensure_safe_root(sd, True, True),sd.resolve())

    def test_unix_root_rejected(self):
        if Path("/").anchor == "/":
            with self.assertRaisesRegex(u.UpdaterError,"Refusing"):
                u.ensure_safe_root(Path("/"), True, True)


if __name__ == "__main__":
    unittest.main()
