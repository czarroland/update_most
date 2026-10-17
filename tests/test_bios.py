"""Portable offline BIOS path, import, security, and catalog tests."""
import hashlib
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


class TestBios(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sd = self.root / 'card'
        (self.sd / 'cores' / 'Demo.Core').mkdir(parents=True)
        (self.sd / 'cores' / 'Demo.Core' / 'core.json').write_text('{}')
        self.src = self.root / 'private-bios'
        self.src.mkdir()
        self.item = dict(id='demo-bios', name='Demo boot ROM', core_id='Demo.Core',
                         destination='cores/Demo.Core/boot.rom', size=8,
                         required=True, redistribution='user_supplied')

    def tearDown(self):
        self.temp.cleanup()

    def cat(self, items=None):
        return {'schema': 1, 'cores': [], 'bios': items if items is not None else [self.item]}

    def test_catalog_validates_requirements(self):
        u.validate_bios_catalog(self.cat())
        bad = dict(self.item, destination='../danger.txt')
        with self.assertRaises(u.UpdaterError):
            u.validate_bios_catalog(self.cat([bad]))
        bad = dict(self.item, destination='cores/Demo.Core/core.json')
        with self.assertRaisesRegex(u.UpdaterError, 'BIOS/ROM extension'):
            u.validate_bios_catalog(self.cat([bad]))
        bad = dict(self.item, destination='system/not-core-file.bin')
        with self.assertRaisesRegex(u.UpdaterError, 'inside'):
            u.validate_bios_catalog(self.cat([bad]))

    def test_remote_license_and_sha_required(self):
        entry = dict(self.item, source=dict(type='url', url='https://example.org/test.bin', sha256='e'*64))
        with self.assertRaisesRegex(u.UpdaterError, 'redistributable'):
            u.validate_bios_catalog(self.cat([entry]))
        entry['redistribution'] = 'redistributable'
        u.validate_bios_catalog(self.cat([entry]))
        entry['source']['sha256'] = 'abc'
        with self.assertRaisesRegex(u.UpdaterError, 'sha256'):
            u.validate_bios_catalog(self.cat([entry]))

    def test_local_import_and_idempotent_preservation(self):
        (self.src / 'boot.rom').write_bytes(b'12345678')
        results = u.manage_bios(self.sd, self.cat(), self.src, False)
        self.assertEqual(results, (1, 0, 0))
        target = self.sd / 'cores' / 'Demo.Core' / 'boot.rom'
        self.assertEqual(target.read_bytes(), b'12345678')
        (self.src / 'boot.rom').write_bytes(b'abcdefgh')
        self.assertEqual(u.manage_bios(self.sd, self.cat(), self.src, False), (1, 0, 0))
        self.assertEqual(target.read_bytes(), b'12345678')

    def test_alias_matching_and_size_reject(self):
        self.item['aliases'] = ['original.bin']
        (self.src / 'boot.rom').write_bytes(b'short')
        (self.src / 'original.bin').write_bytes(b'ABCDEFGH')
        self.assertEqual(u.manage_bios(self.sd, self.cat(), self.src, False), (1, 0, 0))
        self.assertEqual((self.sd / 'cores' / 'Demo.Core' / 'boot.rom').read_bytes(), b'ABCDEFGH')

    def test_existing_wrong_size_not_overwritten(self):
        target = self.sd / 'cores' / 'Demo.Core' / 'boot.rom'
        target.write_bytes(b'incorrect-size')
        (self.src / 'boot.rom').write_bytes(b'12345678')
        self.assertEqual(u.manage_bios(self.sd, self.cat(), self.src, False), (0, 0, 1))
        self.assertEqual(target.read_bytes(), b'incorrect-size')

    def test_dry_run_does_not_create_bios(self):
        (self.src / 'boot.rom').write_bytes(b'12345678')
        self.assertEqual(u.manage_bios(self.sd, self.cat(), self.src, True), (1, 0, 0))
        self.assertFalse((self.sd / 'cores' / 'Demo.Core' / 'boot.rom').exists())

    def test_missing_required_and_unused_core_skipped(self):
        self.assertEqual(u.manage_bios(self.sd, self.cat(), None, False), (0, 1, 0))
        self.assertEqual(u.manage_bios(self.sd, self.cat(), None, False,
                                       selected_core_ids={"Other.Core"}), (0, 0, 0))
        (self.sd / 'cores' / 'Demo.Core' / 'core.json').unlink()
        self.assertEqual(u.manage_bios(self.sd, self.cat(), None, False), (0, 0, 0))

    def test_optional_bios_not_required(self):
        entry = dict(id='gb-bios', name='GB', destination='system/gameboy.bios-dmg.bin',
                     size=256, required=False, sha1=hashlib.sha1(b'Z'*256).hexdigest())
        self.assertEqual(u.manage_bios(self.sd, self.cat([entry]), None, False), (0, 0, 0))
        (self.src / 'gameboy.bios-dmg.bin').write_bytes(b'Z'*256)
        self.assertEqual(u.manage_bios(self.sd, self.cat([entry]), self.src, False), (1, 0, 0))
        self.assertTrue((self.sd/'system'/'gameboy.bios-dmg.bin').exists())

    def test_alternative_rom_group(self):
        first = dict(self.item, id='rom01', name='ROM 01', required=False, one_of='boot', size=8)
        second = dict(self.item, id='rom3', name='ROM 3', required=False, one_of='boot', size=16,
                      destination='cores/Demo.Core/rom3.rom')
        cat = self.cat([first, second])
        self.assertEqual(u.manage_bios(self.sd, cat, None, False), (0, 1, 0))
        (self.src / 'rom3.rom').write_bytes(b'B'*16)
        self.assertEqual(u.manage_bios(self.sd, cat, self.src, False), (1, 0, 0))

    def test_sha_rejected_before_install(self):
        entry = dict(self.item, sha256='e'*64)
        (self.src / 'boot.rom').write_bytes(b'12345678')
        self.assertEqual(u.manage_bios(self.sd, self.cat([entry]), self.src, False), (0, 1, 0))
        self.assertFalse((self.sd / 'cores' / 'Demo.Core' / 'boot.rom').exists())

    def test_remote_raw_fetch_and_hash(self):
        data = b'12345678'
        remote = dict(type='url', url='https://example.org/boot.rom', sha256=u.sha256(data))
        entry = dict(self.item, redistribution='redistributable', source=remote)
        u.validate_bios_catalog(self.cat([entry]))
        fetch_calls = []
        def mock_fetch(url, limit):
            fetch_calls.append(url)
            return data
        self.assertEqual(u.manage_bios(self.sd, self.cat([entry]), None, False, fetcher=mock_fetch), (1, 0, 0))
        self.assertEqual(fetch_calls, [remote['url']])
        self.assertEqual((self.sd/'cores'/'Demo.Core'/'boot.rom').read_bytes(), data)

    def test_remote_zip_and_path_validation(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as z:
            z.writestr('roms/bios.rom', b'12345678')
        archive = buffer.getvalue()
        source = dict(type='url', url='https://example.org/bios.zip',sha256=u.sha256(archive),archive_member='roms/bios.rom')
        entry = dict(self.item, redistribution='redistributable',source=source)
        u.validate_bios_catalog(self.cat([entry]))
        self.assertEqual(u.manage_bios(self.sd, self.cat([entry]), None, False, fetcher=lambda *a:archive), (1, 0, 0))
        self.assertEqual((self.sd/'cores'/'Demo.Core'/'boot.rom').read_bytes(), b'12345678')
        source['archive_member'] = '../escape'
        with self.assertRaises(u.UpdaterError):
            u.validate_bios_catalog(self.cat([entry]))

    def test_remote_sha_mismatch_rejected(self):
        entry = dict(self.item, redistribution='redistributable', source=dict(type='url',url='https://example.org/boot',sha256='a'*64))
        self.assertEqual(u.manage_bios(self.sd,self.cat([entry]),None,False,fetcher=lambda *a:b'12345678'),(0,0,1))
        self.assertFalse((self.sd/'cores'/'Demo.Core'/'boot.rom').exists())

    def test_existing_symlink_rejected(self):
        destination=self.sd/'cores'/'Demo.Core'/'boot.rom'
        destination.symlink_to(self.src/'boot.rom')
        self.assertEqual(u.manage_bios(self.sd,self.cat(),self.src,False),(0,0,1))

    def test_cli_bios_only_local_import(self):
        self.item['aliases'] = ['original.rom']
        (self.src / 'original.rom').write_bytes(b'12345678')
        catalog_path = self.root / 'catalog.json'
        catalog_path.write_text(json.dumps(self.cat()))
        rc = u.main(['--sd',str(self.sd),'--catalog',str(catalog_path),'--bios-only','--bios-dir',str(self.src)])
        self.assertEqual(rc,0)
        self.assertEqual((self.sd/'cores'/'Demo.Core'/'boot.rom').read_bytes(),b'12345678')

    def test_mister_layout_import_renames_correctly(self):
        source = self.src / 'games' / 'Apple-IIgs'
        source.mkdir(parents=True)
        (source / 'boot1.rom').write_bytes(b'R' * 8)
        item=dict(self.item, import_paths=['games/Apple-IIgs/boot1.rom'], aliases=[])
        self.assertEqual(u.manage_bios(self.sd,self.cat([item]),self.src,False),(1,0,0))
        self.assertEqual((self.sd/'cores'/'Demo.Core'/'boot.rom').read_bytes(),b'R'*8)

    def test_catalog_import_path_traversal_rejected(self):
        item=dict(self.item,import_paths=['../wrong-folder/file.rom'])
        with self.assertRaises(u.UpdaterError):
            u.validate_bios_catalog(self.cat([item]))

    def test_single_run_installs_core_then_imports_bios(self):
        metadata={"metadata":{"id":"Demo.Core","name":"Demo","author":"Test"},
                  "bitstreams":[{"target":"gamebub_rev4","filename":"demo.bit"}]}
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:
            z.writestr('cores/Demo.Core/core.json',json.dumps(metadata))
            z.writestr('cores/Demo.Core/demo.bit',b'BIT')
        bundle=buf.getvalue()
        (self.sd/'cores'/'Demo.Core'/'core.json').unlink()
        (self.src/'boot.rom').write_bytes(b'12345678')
        cat=self.cat()
        cat['cores']=[dict(id='Demo.Core',name='Demo',source=dict(
            type='url',url='https://example.org/core.zip',version='1',sha256=u.sha256(bundle)))]
        cat_file=self.root/'combo.json'
        cat_file.write_text(json.dumps(cat))
        with patch.object(u,'fetch',return_value=bundle):
            code=u.main(['--sd',str(self.sd),'--catalog',str(cat_file),'--bios-dir',str(self.src)])
        self.assertEqual(code,0)
        self.assertEqual((self.sd/'cores'/'Demo.Core'/'demo.bit').read_bytes(),b'BIT')
        self.assertEqual((self.sd/'cores'/'Demo.Core'/'boot.rom').read_bytes(),b'12345678')

    def test_shipped_manifest_matches_verified_cores(self):
        catalog=u.load_catalog(str(Path(u.__file__).with_name('catalog.json')))
        bios={e['id']:e for e in catalog['bios']}
        self.assertEqual(bios['coleco-os7']['destination'],'cores/alanswx.ColecoVision/coleco.rom')
        self.assertEqual(bios['mcr-ssio-prom']['size'], 32)
        self.assertEqual(bios['macintosh-lc-rom']['size'], 524288)
        self.assertEqual(bios['apple-iigs-rom01']['size'], 131072)
        self.assertEqual(bios['apple-iigs-rom3']['size'], 262144)
        self.assertEqual(bios['ngpc-color-boot']['source']['path'], 'games/NGPC/boot0.rom')
        self.assertEqual(bios['ngpc-mono-boot']['source']['path'], 'games/NGPC/boot1.rom')
        self.assertEqual(bios['gamecom-boot']['source']['path'], 'games/GameCom/boot.rom')
        self.assertEqual(bios['ngpc-color-boot']['size'], 65536)
        self.assertEqual(bios['ngpc-mono-boot']['size'], 65536)
        self.assertEqual(bios['gamecom-boot']['size'], 262144)
        self.assertTrue(all(bios[k]['redistribution'] == 'community_unverified' for k in
                       ('ngpc-color-boot', 'ngpc-mono-boot', 'gamecom-boot')))

if __name__ == '__main__':
    unittest.main()
