# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Update_Most contributors
"""Synthetic MCR file mapping tests. AI-assisted (OpenAI ChatGPT).

Fixtures reconstruct the relevant required fields from a user-provided MCR
files.json and published v0.6.0 core.json. No copyrighted PROM or game data.
"""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest import mock

import update_most as u
import validate_catalog as v


def mcr_core():
    return {"metadata":{"id":"alanswx.MCR","name":"MCR","author":"Alan Steremberg"},
            "bitstreams":[{"target":"gamebub_rev4","filename":"MCR3-gamebub_rev4.bit"}]}


def mcr_files():
    return {"files":[
        {"id":0,"label":"MCR ROM","extensions":["rom"],"user_selected":True,
         "optional":False,"read_only":True,"address":"0x10000000","max_size":"0x80000"},
        {"id":1,"label":"SSIO Timing PROM","filename":"ssio.prom","optional":False,
         "read_only":True,"address":"0x100F0000","exact_size":"0x20"}]}


class TestArcadeMCRProm(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sd = Path(self.tmp.name) / "sd"
        self.root = self.sd / "cores" / "alanswx.MCR"
        self.root.mkdir(parents=True)
        self.bios_dir = Path(self.tmp.name) / "bios"
        self.bios_dir.mkdir()
        self.catalog = u.load_catalog(str(Path(__file__).resolve().parents[1] / "catalog.json"))
        self.item = next(x for x in self.catalog["bios"] if x["id"] == "mcr-ssio-prom")
        self.write_meta()

    def write_meta(self, core=None, files=None):
        (self.root / "core.json").write_text(json.dumps(core or mcr_core()))
        (self.root / "files.json").write_text(json.dumps(files or mcr_files()))

    def check(self):
        return u.confirmed_core_bios_destination(self.sd,self.item)

    def test_catalog_declares_correct_required_prom(self):
        self.assertEqual(self.item["size"],32)
        self.assertTrue(self.item["required"])
        self.assertEqual(self.item["sha256"],
            "4962a47f67ce0cebc655026efed495eb17fc29e7072650ecab2cecc4f16c06dc")
        self.assertEqual(self.item["destination"],"cores/alanswx.MCR/ssio.prom")
        self.assertEqual(self.item["redistribution"],"user_supplied")
        self.assertNotIn("source",self.item)
        self.assertEqual(self.check(),"cores/alanswx.MCR/ssio.prom")

    def test_mcr_game_image_is_manual_and_not_prom(self):
        mcr = next(c for c in self.catalog["cores"] if c["id"]=="alanswx.MCR")
        self.assertEqual(mcr["arcade_media"]["extensions"],["rom"])
        self.assertEqual(mcr["arcade_media"]["max_size"],0x80000)
        self.assertTrue(mcr["arcade_media"]["user_selected"])
        self.assertEqual(v.validate_records(self.catalog)[0],[])

    def test_wrong_prom_size_rejected(self):
        meta = mcr_files()
        meta["files"][1]["exact_size"]="0x40"
        self.write_meta(files=meta)
        self.assertIsNone(self.check())

    def test_prom_marked_optional_cannot_satisfy_required(self):
        meta=mcr_files()
        meta["files"][1]["optional"]=True
        self.write_meta(files=meta)
        self.assertIsNone(self.check())

    def test_selected_prom_cannot_satisfy_required(self):
        meta=mcr_files()
        meta["files"][1]["user_selected"]=True
        self.write_meta(files=meta)
        self.assertIsNone(self.check())

    def test_wrong_filename_rejected(self):
        meta=mcr_files()
        meta["files"][1]["filename"]="another.prom"
        self.write_meta(files=meta)
        self.assertIsNone(self.check())

    def test_wrong_core_id_rejected(self):
        core=mcr_core()
        core["metadata"]["id"]="Other.MCR"
        self.write_meta(core=core)
        with self.assertRaises(u.UpdaterError):
            self.check()

    def test_wrong_bitstream_rejected(self):
        core=mcr_core()
        core["bitstreams"][0]["filename"]="wrong.bit"
        self.write_meta(core=core)
        with self.assertRaises(u.UpdaterError):
            self.check()

    def test_missing_files_json_prevents_prom_install(self):
        (self.root/"files.json").unlink()
        (self.bios_dir/"ssio.prom").write_bytes(b"x"*32)
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            r=u.manage_bios(self.sd,{"bios":[self.item]},self.bios_dir,False,
                            fetcher=lambda *_: self.fail("network must not be accessed"))
        self.assertEqual(r,(0,0,1))
        self.assertFalse((self.root/"ssio.prom").exists())

    def test_synthetic_prom_import_keeps_game_data(self):
        # A mocked content validator permits a *synthetic* 32-byte input.
        # This is not a valid arcade PROM and is never distributed.
        (self.bios_dir/"ssio.prom").write_bytes(b"x"*32)
        roms=self.sd/"roms"/"MCR"
        roms.mkdir(parents=True)
        existing=roms/"synthetic-game.rom"
        existing.write_bytes(b"dummy game bytes - synthetic only")
        with mock.patch.object(u,"bios_content_valid",side_effect=lambda blob,item:len(blob)==32):
            with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                r=u.manage_bios(self.sd,{"bios":[self.item]},self.bios_dir,False,
                                fetcher=lambda *_: self.fail("no remote downloads"))
        self.assertEqual(r,(1,0,0))
        self.assertEqual((self.root/"ssio.prom").read_bytes(),b"x"*32)
        self.assertEqual(existing.read_bytes(),b"dummy game bytes - synthetic only")

    def test_nonobject_target_core_rejected_cleanly(self):
        doc=copy.deepcopy(self.catalog)
        item=next(x for x in doc["bios"] if x["id"]=="mcr-ssio-prom")
        item["target_core"]="not an object"
        with self.assertRaises(u.UpdaterError):
            u.validate_bios_catalog(doc)

    def test_executable_bios_target_rejected(self):
        doc=copy.deepcopy(self.catalog)
        item=next(x for x in doc["bios"] if x["id"]=="mcr-ssio-prom")
        item["target_core"]["filename"]="payload.exe"
        with self.assertRaises(u.UpdaterError):
            u.validate_bios_catalog(doc)

    def test_invalid_arcade_input_rejected_by_validator(self):
        doc=copy.deepcopy(self.catalog)
        core=next(x for x in doc["cores"] if x["id"]=="alanswx.MCR")
        core["arcade_media"]["max_size"]=-1
        errors,_=v.validate_records(doc)
        self.assertTrue(any("arcade_media" in x for x in errors))


if __name__=="__main__":
    unittest.main()
