"""Three focused installer checks; fake finder is always restored by patch."""
import ast
import hashlib
import importlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import pytest
from laya_pokemon import plan_snapshot_cache_install as installer

FROZEN=None
@pytest.fixture(autouse=True)
def synthetic_plan(tmp_path,monkeypatch):
    path=tmp_path/'plan.json'
    path.write_text(json.dumps({'steps':[{'id':'a','kind':'move','map_id':1,'target':[2,3]}]}),encoding='utf-8')
    monkeypatch.setitem(globals(),'FROZEN',path)


def private_namespace():
    root = installer.ROOT
    campaign = {'__file__': str(installer.CAMPAIGN_PATH)}
    for path, name in [(installer.PLAN_PATH, 'load_plan'),
                       (installer.CORE_PATH, 'sha256_file'),
                       (installer.CAMPAIGN_PATH, 'load_plan_snapshot')]:
        namespace = campaign if path == installer.CAMPAIGN_PATH else {
            '__file__': str(path), 'json': json, 'hashlib': hashlib, 'Path': Path}
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        node = next(n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == name)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
        campaign[name] = namespace[name]
    return campaign


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.saved_registry = installer._REGISTRY
        installer._REGISTRY = {}

    def tearDown(self):
        for record in installer._REGISTRY.values():
            namespace = record['globals']
            if namespace.get('load_plan_snapshot') is record['cached']:
                namespace['load_plan_snapshot'] = record['original']
        installer._REGISTRY = self.saved_registry

    def test_regular_unit_call_has_no_matching_main(self):
        self.assertIsNone(installer.install_for_owned_campaign(object()))
        self.assertEqual(installer._REGISTRY, {})

    def test_install_reload_fast_path_and_explicit_rollback(self):
        native = object()
        namespace = private_namespace()
        original = namespace['load_plan_snapshot']
        with patch.object(installer, '_find_owned_main_globals', return_value=namespace):
            self.assertIs(installer.install_for_owned_campaign(native), True)
        cached = namespace['load_plan_snapshot']
        self.assertIsNot(cached, original)
        frozen = FROZEN
        self.assertEqual(cached(frozen), original(frozen))
        registry = installer._REGISTRY
        importlib.reload(installer)
        self.assertIs(installer._REGISTRY, registry)
        with patch.object(installer, '_find_owned_main_globals', side_effect=AssertionError('stack scan')):
            self.assertIs(installer.install_for_owned_campaign(native), True)
            self.assertIs(installer.rollback(native), True)
            self.assertIs(namespace['load_plan_snapshot'], original)
            self.assertIs(installer.install_for_owned_campaign(native), False)

    def test_validation_rejection_and_rollback_never_overwrite_other_edit(self):
        native = object()
        namespace = private_namespace()
        original = namespace['load_plan_snapshot']
        with patch.object(installer, '_find_owned_main_globals', return_value=namespace):
            with patch.object(installer, 'SNAPSHOT_SOURCE_SHA', '0'*64):
                self.assertIs(installer.install_for_owned_campaign(native), False)
            self.assertIs(namespace['load_plan_snapshot'], original)
            with patch.object(installer, 'CACHE_FILE_SHA', '0'*64):
                self.assertIs(installer.install_for_owned_campaign(native), False)
            self.assertIs(namespace['load_plan_snapshot'], original)
            self.assertIs(installer.install_for_owned_campaign(native), True)
        replacement = lambda path: None
        namespace['load_plan_snapshot'] = replacement
        self.assertIs(installer.rollback(native), False)
        self.assertIs(namespace['load_plan_snapshot'], replacement)


if __name__ == '__main__':
    unittest.main(verbosity=2)
