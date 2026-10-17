"""MiSTer BiosDB integration tests; fake remote bytes, never download real BIOS."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import update_most as u


class TestMisterBiosDatabase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sd = self.root / 'card'
        (self.sd / 'cores').mkdir(parents=True)
        self.samples = {
            'games/NGPC/boot0.rom': b'B' * 8,
            'games/NGPC/boot1.rom': b'C' * 16,
            'games/GameCom/boot.rom': b'G' * 24,
        }
        self.urls = {path: u.MISTER_BIOS_ARCHIVE + ('ngp0.rom' if 'boot0' in path else 'ngpc1.rom' if 'boot1' in path else 'gamecom.rom') for path in self.samples}
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def index(self, tamper=None, extra=''):
        rows = ['Path,URL,Size in bytes (optional but recommended),MD5 Hash (optional but recommended),Filter Terms (optional),Overwrite (optional),Comments (optional)']
        for path, blob in self.samples.items():
            digest = hashlib.md5(blob).hexdigest()
            size = len(blob)
            url = self.urls[path]
            if tamper and path == tamper.get('path'):
                size = tamper.get('size', size)
                digest = tamper.get('md5', digest)
                url = tamper.get('url', url)
            rows.append(f'{path},{url},{size},{digest},bios,overwrite:false,')
        if extra:
            rows.append(extra)
        return ('\n\n'.join(rows) + '\n').encode()

    def entries(self):
        result = []
        for i, (path, blob) in enumerate(self.samples.items()):
            result.append({
                'id': ['ngp', 'ngpc', 'gamecom'][i],
                'name': ['Mono Pocket', 'Color Pocket', 'Game.com'][i],
                'destination': ['system/ngpc.boot0.rom','system/ngpc.boot1.rom','system/gamecom.boot.rom'][i],
                'size': len(blob),
                'md5': hashlib.md5(blob).hexdigest(),
                'redistribution': 'community_unverified',
                'source': {'type':'mister_bios_db', 'path':path},
            })
        return result

    def fetch(self, url, max_bytes):
        self.calls.append(url)
        if url == u.MISTER_BIOS_CSV:
            return self.index()
        for path, src in self.urls.items():
            if url == src:
                return self.samples[path]
        raise AssertionError('unexpected URL ' + url)

    def test_all_three_autofetch_cached_database_and_idempotent(self):
        entries = self.entries()
        u.validate_bios_catalog({'bios': entries})
        result = u.manage_bios(self.sd, {'bios':entries}, None, False, fetcher=self.fetch, allow_mister_bios=True)
        self.assertEqual(result, (3,0,0))
        self.assertEqual(self.calls.count(u.MISTER_BIOS_CSV), 1)
        for item in entries:
            target = self.sd / item['destination']
            self.assertEqual(target.read_bytes(), self.samples[item['source']['path']])
        self.calls.clear()
        self.assertEqual(u.manage_bios(self.sd, {'bios':entries}, None, False, fetcher=self.fetch, allow_mister_bios=True), (3,0,0))
        self.assertEqual(self.calls, [])

    def test_default_fetches_community_database_bios(self):
        entries = self.entries()
        result = u.manage_bios(self.sd, {'bios':entries}, None, False, fetcher=self.fetch)
        self.assertEqual(result,(3,0,0))
        self.assertEqual(self.calls.count(u.MISTER_BIOS_CSV), 1)
        self.assertTrue((self.sd/'system'/'gamecom.boot.rom').exists())

    def test_explicit_opt_out_does_not_fetch_community_bios(self):
        entries = self.entries()
        result = u.manage_bios(self.sd, {'bios':entries}, None, False,
                               fetcher=self.fetch, allow_mister_bios=False)
        self.assertEqual(result,(0,0,0))
        self.assertEqual(self.calls, [])
        self.assertFalse((self.sd/'system').exists())

    def test_local_import_is_preferred_to_online_lookup_by_default(self):
        entries = self.entries()
        source = self.root / 'local'
        source.mkdir()
        for item in entries:
            (source / Path(item['destination']).name).write_bytes(self.samples[item['source']['path']])
        result = u.manage_bios(self.sd, {'bios':entries}, source, False,
                               fetcher=lambda *_: self.fail('Matching local BIOS must avoid the network'))
        self.assertEqual(result, (3,0,0))
        for item in entries:
            self.assertEqual((self.sd / item['destination']).read_bytes(), self.samples[item['source']['path']])

    def test_local_import_still_works_when_community_fetch_disabled(self):
        entries = self.entries()
        source = self.root / 'local'
        source.mkdir()
        for item in entries:
            (source / Path(item['destination']).name).write_bytes(self.samples[item['source']['path']])
        result = u.manage_bios(self.sd, {'bios':entries}, source, False,
                               fetcher=lambda *_: self.fail('No fetch in local-only mode'),
                               allow_mister_bios=False)
        self.assertEqual(result, (3,0,0))

    def test_mismatched_catalog_pin_rejected_before_download(self):
        entries = self.entries()
        entries[0]['md5'] = 'f'*32
        result = u.manage_bios(self.sd, {'bios':entries[:1]}, None, False, fetcher=self.fetch, allow_mister_bios=True)
        self.assertEqual(result,(0,0,1))
        self.assertEqual(self.calls,[u.MISTER_BIOS_CSV])
        self.assertFalse((self.sd/'system'/'ngpc.boot0.rom').exists())

    def test_bad_download_rejected(self):
        entries = self.entries()[:1]
        def tampered_fetch(url, limit):
            return self.index() if url==u.MISTER_BIOS_CSV else b'X'*8
        result = u.manage_bios(self.sd, {'bios':entries}, None, False, fetcher=tampered_fetch, allow_mister_bios=True)
        self.assertEqual(result,(0,0,1))
        self.assertFalse((self.sd/'system'/'ngpc.boot0.rom').exists())

    def test_reject_csv_url_injected_by_community(self):
        entries = self.entries()[:1]
        def poisoned(url, limit):
            return self.index(tamper={'path':'games/NGPC/boot0.rom','url':'https://attacker.example/payload.rom'})
        self.assertEqual(u.manage_bios(self.sd, {'bios':entries}, None, False, fetcher=poisoned, allow_mister_bios=True),(0,0,1))
        self.assertFalse((self.sd/'system'/'ngpc.boot0.rom').exists())

    def test_duplicates_only_in_selected_rows_rejected(self):
        duplicate_unrelated='games/Other/boot.rom,https://archive.org/download/mister_bios_db/foo.rom,8,deadbeefdeadbeefdeadbeefdeadbeef,bios,overwrite:false,'
        def with_duplicate(url, limit):
            return self.index(extra=duplicate_unrelated + '\n' + duplicate_unrelated)
        records=u.load_mister_bios_index({'games/NGPC/boot0.rom'}, fetcher=with_duplicate)
        self.assertIn('games/NGPC/boot0.rom',records)
        duplicate_selected='games/NGPC/boot0.rom,https://archive.org/download/mister_bios_db/foo.rom,8,deadbeefdeadbeefdeadbeefdeadbeef,bios,overwrite:false,'
        with self.assertRaisesRegex(u.UpdaterError,'Duplicate'):
            u.load_mister_bios_index({'games/NGPC/boot0.rom'},fetcher=lambda url,limit:self.index(extra=duplicate_selected))

    def test_invalid_catalog_source_and_md5(self):
        entry=self.entries()[0]
        entry['source']['path']='../foo'
        with self.assertRaisesRegex(u.UpdaterError,'exact games'):
            u.validate_bios_catalog({'bios':[entry]})
        entry['source']['path']='games/NGPC/boot0.rom'
        entry['md5']='BAD'
        with self.assertRaises(u.UpdaterError):
            u.validate_bios_catalog({'bios':[entry]})
        entry['md5']=hashlib.md5(b'B'*8).hexdigest()
        entry['redistribution']='redistributable'
        with self.assertRaisesRegex(u.UpdaterError,'community_unverified'):
            u.validate_bios_catalog({'bios':[entry]})

    def test_cli_bios_only_mister_bios_flag(self):
        catalog=self.root/'catalog.json'
        catalog.write_text(json.dumps({'schema':1,'cores':[],'bios':self.entries()}))
        with patch.object(u,'fetch',side_effect=self.fetch):
            result=u.main(['--sd',str(self.sd),'--catalog',str(catalog),'--bios-only','--mister-bios'])
        self.assertEqual(result,0)
        self.assertTrue((self.sd/'system'/'gamecom.boot.rom').exists())

    def test_cli_default_run_fetches_without_flag(self):
        catalog = self.root / 'catalog.json'
        catalog.write_text(json.dumps({'schema':1, 'cores':[], 'bios':self.entries()}))
        with patch.object(u, 'fetch', side_effect=self.fetch):
            result = u.main(['--sd', str(self.sd), '--catalog', str(catalog)])
        self.assertEqual(result, 0)
        self.assertEqual(self.calls.count(u.MISTER_BIOS_CSV), 1)
        self.assertEqual((self.sd/'system'/'gamecom.boot.rom').read_bytes(), self.samples['games/GameCom/boot.rom'])

    def test_cli_no_mister_bios_opt_out(self):
        catalog = self.root / 'catalog.json'
        catalog.write_text(json.dumps({'schema':1, 'cores':[], 'bios':self.entries()}))
        with patch.object(u, 'fetch', side_effect=lambda *_: self.fail('No network expected')):
            result = u.main(['--sd', str(self.sd), '--catalog', str(catalog), '--bios-only', '--no-mister-bios'])
        self.assertEqual(result, 0)
        self.assertFalse((self.sd/'system').exists())

    def test_cli_skip_bios_suppresses_default_downloads(self):
        catalog = self.root / 'catalog.json'
        catalog.write_text(json.dumps({'schema':1, 'cores':[], 'bios':self.entries()}))
        with patch.object(u, 'fetch', side_effect=lambda *_: self.fail('No network expected')):
            result = u.main(['--sd', str(self.sd), '--catalog', str(catalog), '--skip-bios'])
        self.assertEqual(result, 0)
        self.assertFalse((self.sd/'system').exists())

    def test_dry_run_fetches_and_verifies_but_does_not_write(self):
        entries=self.entries()
        self.assertEqual(u.manage_bios(self.sd, {'bios':entries}, None, True, fetcher=self.fetch, allow_mister_bios=True),(3,0,0))
        self.assertFalse((self.sd/'system').exists())


if __name__=='__main__':
    unittest.main()