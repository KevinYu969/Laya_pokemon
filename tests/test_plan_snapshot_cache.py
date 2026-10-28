"""Six focused checks; all mutations remain in this private staging folder."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import unittest

import pytest
from laya_pokemon import campaign
from laya_pokemon.plan_snapshot_cache import make_cached_snapshot_loader

FIXTURES = None
LOAD, SHA, BASELINE = campaign.load_plan, campaign.sha256_file, campaign.load_plan_snapshot

@pytest.fixture(autouse=True)
def temporary_files(tmp_path, monkeypatch):
    monkeypatch.setitem(globals(), 'FIXTURES', tmp_path)


def valid(identifier='a'):
    return {'steps': [{'id': identifier, 'kind': 'move', 'map_id': 1,
                       'target': [2, 3], 'via': [[1, 2]]}],
            'note': '\ud800'}


def write(path, plan):
    path.write_text(json.dumps(plan), encoding='utf-8')


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.path = FIXTURES / (self._testMethodName + '.json')
        write(self.path, valid())
        self.calls = {'load': 0, 'sha': 0}

        def counted_load(path):
            self.calls['load'] += 1
            return LOAD(path)

        def counted_sha(path):
            self.calls['sha'] += 1
            return SHA(path)

        self.cached = make_cached_snapshot_loader(counted_load, counted_sha)

    def test_fresh_dict_and_nested_mutation(self):
        expected = BASELINE(self.path)
        first = self.cached(self.path)
        second = self.cached(self.path)
        self.assertEqual(second, expected)
        self.assertIsNot(first[0], second[0])
        self.assertIsNot(first[0]['steps'], second[0]['steps'])
        first[0]['steps'][0]['target'][0] = 999
        second[0]['steps'][0]['via'][0][0] = 999
        third = self.cached(self.path)
        self.assertEqual(third, expected)
        self.assertEqual(self.calls, {'load': 1, 'sha': 1})

    def test_inplace_change_and_same_size_atomic_replace(self):
        self.cached(self.path)
        write(self.path, valid('b'))
        self.assertEqual(self.cached(self.path), BASELINE(self.path))
        previous = self.path.stat()
        replacement = self.path.with_suffix('.replacement')
        write(replacement, valid('c'))
        self.assertEqual(replacement.stat().st_size, previous.st_size)
        os.utime(replacement, ns=(previous.st_atime_ns, previous.st_mtime_ns))
        replacement.replace(self.path)
        self.assertNotEqual(self.path.stat().st_ino, previous.st_ino)
        self.assertEqual(self.cached(self.path), BASELINE(self.path))
        self.assertEqual(self.cached(self.path)[0]['steps'][0]['id'], 'c')
        self.assertEqual(self.calls, {'load': 3, 'sha': 3})

    @unittest.skipUnless(os.name == 'nt', 'real Windows sharing lock')
    @unittest.skipUnless(os.name == 'nt', 'Windows sharing semantics')
    def test_windows_sharing_lock_cold_and_warm(self):
        self.cached(self.path)
        create = ctypes.windll.kernel32.CreateFileW
        create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                           wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                           wintypes.HANDLE]
        create.restype = wintypes.HANDLE
        close = ctypes.windll.kernel32.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        handle = create(str(self.path), 0x80000000, 0, None, 3, 0x80, None)
        self.assertNotEqual(handle, wintypes.HANDLE(-1).value)
        try:
            self.assertIsNone(BASELINE(self.path))
            self.assertIsNone(self.cached(self.path))
            cold = make_cached_snapshot_loader(LOAD, SHA)
            self.assertIsNone(cold(self.path))
        finally:
            close(handle)
        self.assertEqual(self.cached(self.path), BASELINE(self.path))
        self.assertEqual(self.calls, {'load': 2, 'sha': 2})

    def test_torn_miss_and_hit_clear_cache(self):
        changed = False

        def changing_sha(path):
            nonlocal changed
            if not changed:
                write(path, valid('changed-during-hash'))
                changed = True
            return SHA(path)

        loader = make_cached_snapshot_loader(LOAD, changing_sha)
        self.assertIsNone(loader(self.path))
        self.assertEqual(loader(self.path), BASELINE(self.path))
        self.cached(self.path)
        actual = self.path

        class ReplacingOnSecondStat:
            calls = 0

            def __fspath__(self):
                return os.fspath(actual)

            def stat(self):
                self.calls += 1
                if self.calls == 2:
                    temp = actual.with_suffix('.torn-replacement')
                    write(temp, valid('changed-during-hit'))
                    temp.replace(actual)
                return actual.stat()

            def open(self, *args, **kwargs):
                return actual.open(*args, **kwargs)

        self.assertIsNone(self.cached(ReplacingOnSecondStat()))
        self.assertEqual(self.cached(actual), BASELINE(actual))
        self.assertEqual(self.calls, {'load': 2, 'sha': 2})

    def test_original_invalid_and_missing_errors_propagate(self):
        for value, error in [(b'{"steps": [', ValueError),
                             (b'{"steps": []}', ValueError),
                             (b'\xff\xfe\xff', UnicodeError)]:
            write(self.path, valid())
            self.cached(self.path)
            self.path.write_bytes(value)
            with self.assertRaises(error):
                self.cached(self.path)
            with self.assertRaises(error):
                BASELINE(self.path)
            write(self.path, valid('recovered'))
            self.assertEqual(self.cached(self.path), BASELINE(self.path))
        missing = self.path.with_suffix('.missing')
        with self.assertRaises(FileNotFoundError):
            self.cached(missing)
        self.assertEqual(self.cached(self.path), BASELINE(self.path))

    def test_retains_only_one_file(self):
        other = self.path.with_suffix('.other')
        write(other, valid('other'))
        self.cached(self.path)
        self.cached(self.path)
        self.cached(other)
        self.cached(other)
        self.cached(self.path)
        self.assertEqual(self.calls, {'load': 3, 'sha': 3})
        self.assertEqual(self.cached(self.path), BASELINE(self.path))


if __name__ == '__main__':
    unittest.main(verbosity=2)
