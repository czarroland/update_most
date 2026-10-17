"""Kitrinx BIOS routing using independently written synthetic metadata.

These tests include no upstream core files or proprietary BIOS images.
"""
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import update_most as u


ROOT = pathlib.Path(__file__).resolve().parent

# Generated test stand-ins for the public Kitrinx metadata requirements.
# Do not publish source core.json/files.json obtained from the developer.
CORE_BITS = {
    "Kitrinx.NGPC": "NgpcCore-gamebub_rev4.bit",
    "Kitrinx.GameCom": "GameComCore-gamebub_rev4.bit",
}

def synthetic_metadata(core_id):
    core = {"metadata": {"id": core_id},
            "bitstreams": [{"target": "gamebub_rev4", "filename": CORE_BITS[core_id]}]}
    if core_id == "Kitrinx.NGPC":
        entries = [("boot0.rom", 65536, False), ("boot1.rom", 65536, True)]
    else:
        entries = [("boot.rom", 262144, False)]
    files = {"files": [{"id": n+2, "label": "Synthetic BIOS", "filename": name,
                        "optional": optional, "read_only": True,
                        "exact_size": hex(size)}
                       for n, (name, size, optional) in enumerate(entries)]}
    return core, files
SPECS = [
    ('ngpc-color-boot', 'Kitrinx.NGPC', 'boot0.rom', 65536, True, b'C'),
    ('ngpc-mono-boot', 'Kitrinx.NGPC', 'boot1.rom', 65536, False, b'M'),
    ('gamecom-boot', 'Kitrinx.GameCom', 'boot.rom', 262144, True, b'G'),
]


class TestVerifiedKitrinxBios(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.sd = pathlib.Path(self.temp.name) / 'card'
        (self.sd / 'cores').mkdir(parents=True)
        self.catalog = u.load_catalog(str(ROOT.parent / 'catalog.json'))
        self.manifest = {row['id']: row for row in self.catalog['bios']}
        self.items = []
        self.blobs = {}
        self.downloads = []
        for id, cid, name, length, required, byte in SPECS:
            data = byte * length
            item = dict(self.manifest[id])
            item['md5'] = hashlib.md5(data).hexdigest()
            self.items.append(item)
            self.blobs[item['source']['path']] = data
        self.mister_url = u.MISTER_BIOS_ARCHIVE + 'synthetic/'

    def install_metadata(self, core='all'):
        core_ids = ['Kitrinx.NGPC', 'Kitrinx.GameCom'] if core == 'all' else [core]
        for cid in core_ids:
            folder = self.sd / 'cores' / cid
            folder.mkdir(parents=True, exist_ok=True)
            core_doc, files_doc = synthetic_metadata(cid)
            (folder / 'core.json').write_text(json.dumps(core_doc))
            (folder / 'files.json').write_text(json.dumps(files_doc))
            bit = core_doc['bitstreams'][0]['filename']
            (folder / bit).write_bytes(b'synthetic FPGA bitstream placeholder')

    def fetch(self, url, max_bytes):
        self.downloads.append(url)
        if url == u.MISTER_BIOS_CSV:
            header = 'Path,URL,Size in bytes (optional but recommended),MD5 Hash (optional but recommended),Filter Terms (optional),Overwrite (optional),Comments (optional)\n'
            lines = []
            for path, data in self.blobs.items():
                lines.append(','.join([path, self.mister_url + path.replace('/', '-'), str(len(data)), hashlib.md5(data).hexdigest(), 'bios', 'overwrite:false', '']))
            return (header + '\n'.join(lines)).encode()
        for path, data in self.blobs.items():
            if url == self.mister_url + path.replace('/', '-'):
                return data
        raise AssertionError(f'Unexpected synthetic URL: {url}')

    def test_synthetic_metadata_matches_documented_requirements(self):
        for id, cid, name, length, required, byte in SPECS:
            _, original = synthetic_metadata(cid)
            matches = [row for row in original['files'] if row.get('filename') == name]
            self.assertEqual(len(matches), 1)
            self.assertEqual(int(matches[0]['exact_size'], 0), length)
            self.assertEqual(not matches[0].get('optional'), required)
            self.assertTrue(matches[0]['read_only'])
            cat = self.manifest[id]
            self.assertEqual(cat['core_id'], cid)
            self.assertEqual(cat['destination'], f'cores/{cid}/{name}')
            self.assertEqual(cat['required'], required)
            self.assertEqual(cat['size'], length)
            self.assertEqual(cat['source']['path'].split('/')[-1], name)

    def test_all_three_auto_fetch_one_index_and_no_game_data_changed(self):
        self.install_metadata()
        ngpc = self.sd / 'cores' / 'Kitrinx.NGPC'
        gamecom = self.sd / 'cores' / 'Kitrinx.GameCom'
        (ngpc / 'save.sav').write_bytes(b'KEEP_NGPC_SAVE')
        (gamecom / 'nvram.sav').write_bytes(b'KEEP_GAMECOM_NVRAM')
        result = u.manage_bios(self.sd, {'bios': self.items}, None, False, fetcher=self.fetch, allow_mister_bios=True)
        self.assertEqual(result, (3, 0, 0))
        self.assertEqual(self.downloads.count(u.MISTER_BIOS_CSV), 1)
        for item in self.items:
            self.assertEqual((self.sd / item['destination']).read_bytes(), self.blobs[item['source']['path']])
        self.assertEqual((ngpc / 'save.sav').read_bytes(), b'KEEP_NGPC_SAVE')
        self.assertEqual((gamecom / 'nvram.sav').read_bytes(), b'KEEP_GAMECOM_NVRAM')
        self.assertFalse((self.sd / 'system').exists())
        self.downloads.clear()
        self.assertEqual(u.manage_bios(self.sd, {'bios': self.items}, None, False, fetcher=self.fetch, allow_mister_bios=True), (3, 0, 0))
        self.assertEqual(self.downloads, [])

    def test_offline_migration_from_v05_staging_by_pinned_hash(self):
        self.install_metadata()
        for item in self.items:
            old = self.sd / item['legacy_destinations'][0]
            old.parent.mkdir(parents=True, exist_ok=True)
            old.write_bytes(self.blobs[item['source']['path']])
        self.assertEqual(u.manage_bios(self.sd, {'bios': self.items}, None, False, fetcher=lambda *_: self.fail('No network expected')),(3,0,0))
        for item in self.items:
            self.assertEqual((self.sd / item['destination']).read_bytes(), self.blobs[item['source']['path']])
            self.assertEqual((self.sd / item['legacy_destinations'][0]).read_bytes(), self.blobs[item['source']['path']])

    def test_missing_files_json_blocks_downloading_and_placement(self):
        self.install_metadata('Kitrinx.NGPC')
        (self.sd / 'cores' / 'Kitrinx.NGPC' / 'files.json').unlink()
        self.assertEqual(u.manage_bios(self.sd, {'bios': self.items[:2]}, None, False, fetcher=self.fetch, allow_mister_bios=True), (0,0,2))
        self.assertEqual(self.downloads, [])
        self.assertFalse((self.sd / 'cores' / 'Kitrinx.NGPC' / 'boot0.rom').exists())
        self.assertFalse((self.sd / 'system').exists())

    def test_wrong_installed_bios_metadata_blocks_download(self):
        self.install_metadata('Kitrinx.NGPC')
        files = self.sd / 'cores' / 'Kitrinx.NGPC' / 'files.json'
        data = json.loads(files.read_text()); data['files'][0]['exact_size'] = '0x20000'
        files.write_text(json.dumps(data))
        self.assertEqual(u.manage_bios(self.sd, {'bios': self.items[:1]}, None, False, fetcher=self.fetch, allow_mister_bios=True), (0,0,1))
        self.assertEqual(self.downloads, [])

    def test_absent_kitrinx_core_skips_bios_not_stage(self):
        self.assertEqual(u.manage_bios(self.sd, {'bios': self.items}, None, False, fetcher=self.fetch, allow_mister_bios=True), (0,0,0))
        self.assertEqual(self.downloads, [])
        self.assertFalse((self.sd / 'system').exists())

    def test_existing_conflicting_bios_and_nvram_are_preserved(self):
        self.install_metadata('Kitrinx.GameCom')
        core = self.sd / 'cores' / 'Kitrinx.GameCom'
        (core / 'boot.rom').write_bytes(b'not same bytes')
        (core / 'nvram.sav').write_bytes(b'user data')
        self.assertEqual(u.manage_bios(self.sd, {'bios': self.items[2:]}, None, False, fetcher=self.fetch, allow_mister_bios=True), (0,0,1))
        self.assertEqual((core / 'boot.rom').read_bytes(), b'not same bytes')
        self.assertEqual((core / 'nvram.sav').read_bytes(), b'user data')
        self.assertEqual(self.downloads, [])

    def test_wrong_legacy_hash_cannot_be_migrated(self):
        self.install_metadata('Kitrinx.NGPC')
        item = self.items[0]
        legacy = self.sd / item['legacy_destinations'][0]
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b'X' * item['size'])  # right length, wrong hash
        self.assertEqual(u.manage_bios(self.sd, {'bios':[item]}, None, False,
                           fetcher=lambda *_: self.fail('no download expected'), allow_mister_bios=False),(0,1,0))
        self.assertFalse((self.sd / item['destination']).exists())
        self.assertEqual(legacy.read_bytes(), b'X' * item['size'])

    def test_no_community_download_with_explicit_opt_out(self):
        self.install_metadata('Kitrinx.GameCom')
        item = self.items[2]
        self.assertEqual(u.manage_bios(self.sd, {'bios':[item]}, None, False,
                           fetcher=lambda *_: self.fail('no download expected'), allow_mister_bios=False),(0,1,0))
        self.assertFalse((self.sd / item['destination']).exists())

    def test_missing_optional_mono_does_not_fail_required_color(self):
        self.install_metadata('Kitrinx.NGPC')
        color = self.items[0]
        local = pathlib.Path(self.temp.name) / 'personal'
        local.mkdir()
        (local / 'boot0.rom').write_bytes(self.blobs[color['source']['path']])
        self.assertEqual(u.manage_bios(self.sd, {'bios':self.items[:2]}, local, False,
                          fetcher=lambda *_: self.fail('no download expected'), allow_mister_bios=False),(1,0,0))
        self.assertTrue((self.sd / color['destination']).exists())
        self.assertFalse((self.sd / self.items[1]['destination']).exists())

    def test_legacy_paths_cannot_escape_system(self):
        entry = dict(self.items[0]); entry['legacy_destinations']=['../escape/boot0.rom']
        with self.assertRaises(u.UpdaterError):
            u.validate_bios_catalog({'bios':[entry]})
        entry['legacy_destinations']=['cores/Bad.Core/boot0.rom']
        with self.assertRaises(u.UpdaterError):
            u.validate_bios_catalog({'bios':[entry]})

    def test_direct_core_metadata_must_match_catalog_id_and_filename(self):
        entry = dict(self.items[0]); entry['destination']='cores/Kitrinx.GameCom/boot0.rom'
        with self.assertRaises(u.UpdaterError):
            u.validate_bios_catalog({'bios':[entry]})
        entry['destination']='cores/Kitrinx.NGPC/boot0.rom'
        entry['target_core'] = dict(entry['target_core'], filename='boot1.rom')
        with self.assertRaises(u.UpdaterError):
            u.validate_bios_catalog({'bios':[entry]})


if __name__=='__main__':
    unittest.main()