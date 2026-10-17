"""User-provided Kitrinx core.json confirms identities but not files.json.

These tests supply synthetic files.json, never a copyrighted BIOS or ROM.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import update_most as u


class TestKitrinxRouting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sd = Path(self.tmp.name) / 'card'
        (self.sd / 'cores').mkdir(parents=True)
        self.target = {
            'id': 'Kitrinx.NGPC',
            'bitstream': 'NgpcCore-gamebub_rev4.bit',
            'filename': 'boot1.rom',
        }
        self.bios = b'K' * 64
        self.item = {
            'id': 'ngpc-boot', 'name': 'Test synthetic NGPC firmware',
            'destination': 'system/ngpc.boot1.rom',
            'size': len(self.bios), 'md5': hashlib.md5(self.bios).hexdigest(),
            'redistribution': 'community_unverified',
            'source': {'type': 'mister_bios_db', 'path': 'games/NGPC/boot1.rom'},
            'target_core': self.target,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def core_files(self, filename='boot1.rom', size=64, core_id='Kitrinx.NGPC', bitstream=None):
        path = self.sd / 'cores' / core_id
        path.mkdir(parents=True, exist_ok=True)
        (path / 'core.json').write_text(json.dumps({
            'metadata': {'id': core_id},
            'bitstreams': [{'target':'gamebub_rev4',
                            'filename': bitstream or self.target['bitstream']}] }))
        (path / 'files.json').write_text(json.dumps({
            'files':[{'id':1,'filename':filename,'read_only':True,
                      'exact_size':hex(size), 'optional':False}]}))
        return path

    def test_shipped_manifest_has_authoritative_core_locations(self):
        catalog=u.load_catalog(str(Path(u.__file__).with_name('catalog.json')))
        arr={x['id']:x for x in catalog['bios']}
        self.assertEqual(arr['ngpc-color-boot']['destination'], 'cores/Kitrinx.NGPC/boot0.rom')
        self.assertEqual(arr['ngpc-mono-boot']['destination'], 'cores/Kitrinx.NGPC/boot1.rom')
        self.assertEqual(arr['gamecom-boot']['destination'], 'cores/Kitrinx.GameCom/boot.rom')
        self.assertTrue(arr['ngpc-color-boot']['required'])
        self.assertFalse(arr['ngpc-mono-boot']['required'])
        self.assertTrue(arr['gamecom-boot']['required'])
        self.assertEqual(arr['ngpc-color-boot']['source']['path'], 'games/NGPC/boot0.rom')
        self.assertEqual(arr['ngpc-mono-boot']['source']['path'], 'games/NGPC/boot1.rom')
        for item in (arr[k] for k in ('ngpc-color-boot','ngpc-mono-boot','gamecom-boot')):
            self.assertEqual(item['core_id'], item['target_core']['id'])
            self.assertEqual(item['destination'].rsplit('/',1)[1], item['target_core']['filename'])
            self.assertEqual(len(item['legacy_destinations']), 1)

    def test_no_files_json_never_guesses_bios_destination(self):
        root = self.sd/'cores'/'Kitrinx.NGPC'
        root.mkdir()
        (root/'core.json').write_text(json.dumps({'metadata':{'id':'Kitrinx.NGPC'},
                              'bitstreams':[{'target':'gamebub_rev4','filename':self.target['bitstream']}]}))
        self.assertIsNone(u.confirmed_core_bios_destination(self.sd,self.item))
        src=self.sd.parent/'incoming'
        src.mkdir()
        (src/'ngpc.boot1.rom').write_bytes(self.bios)
        self.assertEqual(u.manage_bios(self.sd,{'bios':[self.item]},src,False),(1,0,0))
        self.assertEqual((self.sd/'system'/'ngpc.boot1.rom').read_bytes(),self.bios)
        self.assertFalse((root/'boot1.rom').exists())

    def test_confirmed_filename_download_goes_to_core(self):
        root=self.core_files()
        self.assertEqual(u.confirmed_core_bios_destination(self.sd,self.item),
                         'cores/Kitrinx.NGPC/boot1.rom')
        src=self.sd.parent/'bios'
        src.mkdir()
        (src/'ngpc.boot1.rom').write_bytes(self.bios)
        self.assertEqual(u.manage_bios(self.sd, {'bios':[self.item]}, src, False), (1,0,0))
        self.assertEqual((root/'boot1.rom').read_bytes(),self.bios)
        self.assertFalse((self.sd/'system').exists())

    def test_offline_migrates_staged_bios_preserves_staged_copy(self):
        provisional=self.sd/'system'/'ngpc.boot1.rom'
        provisional.parent.mkdir()
        provisional.write_bytes(self.bios)
        root=self.core_files()
        self.assertEqual(u.manage_bios(self.sd,{'bios':[self.item]},None,False),(1,0,0))
        self.assertEqual((root/'boot1.rom').read_bytes(),self.bios)
        self.assertEqual(provisional.read_bytes(),self.bios)
        self.assertEqual(u.manage_bios(self.sd,{'bios':[self.item]},None,False),(1,0,0))

    def test_unknown_name_or_size_remains_staged(self):
        for kwargs in ({'filename':'unknown.bin'}, {'size':16}):
            root=self.core_files(**kwargs)
            self.assertIsNone(u.confirmed_core_bios_destination(self.sd,self.item))
        root=self.core_files(filename='boot1.rom',size=64)
        file_doc=json.loads((root/'files.json').read_text())
        file_doc['files'][0]['read_only']=False
        (root/'files.json').write_text(json.dumps(file_doc))
        self.assertIsNone(u.confirmed_core_bios_destination(self.sd,self.item))

    def test_protect_existing_core_firmware(self):
        root=self.core_files()
        (root/'boot1.rom').write_bytes(b'OTHER')
        (self.sd/'system').mkdir()
        (self.sd/'system'/'ngpc.boot1.rom').write_bytes(self.bios)
        self.assertEqual(u.manage_bios(self.sd,{'bios':[self.item]},None,False),(0,0,1))
        self.assertEqual((root/'boot1.rom').read_bytes(),b'OTHER')

    def test_wrong_bitstream_refuses_placing_into_core(self):
        root=self.core_files(bitstream='other.bit')
        with self.assertRaisesRegex(u.UpdaterError, 'expected rev4 bitstream'):
            u.confirmed_core_bios_destination(self.sd,self.item)
        self.assertFalse((root/'boot1.rom').exists())

    def test_unexpected_core_id_cannot_hijack_destination(self):
        root=self.core_files()
        (root/'core.json').write_text(json.dumps({'metadata':{'id':'Unrelated.Core'},
                        'bitstreams':[{'target':'gamebub_rev4','filename':self.target['bitstream']}]}))
        with self.assertRaisesRegex(u.UpdaterError, 'core ID does not match'):
            u.confirmed_core_bios_destination(self.sd,self.item)

    def test_gamecom_core_boot_filename_route(self):
        item=copy.deepcopy(self.item)
        item['target_core']={ 'id':'Kitrinx.GameCom',
                    'bitstream':'GameComCore-gamebub_rev4.bit','filename':'boot.rom'}
        item['destination']='system/gamecom.boot.rom'
        root=self.core_files(filename='boot.rom',core_id='Kitrinx.GameCom',bitstream='GameComCore-gamebub_rev4.bit')
        self.assertEqual(u.confirmed_core_bios_destination(self.sd,item),'cores/Kitrinx.GameCom/boot.rom')

    def test_bad_catalog_target_rejected(self):
        for bad in ({'id':'../evil','bitstream':'x.bit','filename':'boot.rom'},
                    {'id':'Kitrinx.NGPC','bitstream':'x.bit','filename':'../bad.rom'},
                    {'id':'Kitrinx.NGPC','bitstream':'x.bit'}):
            entry=copy.deepcopy(self.item)
            entry['target_core']=bad
            with self.assertRaises(u.UpdaterError):
                u.validate_bios_catalog({'bios':[entry]})


if __name__ == '__main__':
    unittest.main()