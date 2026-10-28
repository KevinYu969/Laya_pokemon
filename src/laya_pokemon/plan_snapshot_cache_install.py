"""Optional staged installer. Parent must establish native ownership first.

No campaign import/reload, frame locals dump, emulator action, or file write.
Only install_for_owned_campaign(native) or rollback(native) changes one global.
"""
import hashlib
import inspect
from pathlib import Path
from types import FunctionType, ModuleType

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN_PATH = ROOT / 'src/laya_pokemon/campaign.py'
PLAN_PATH = ROOT / 'src/laya_pokemon/campaign_plan.py'
CORE_PATH = ROOT / 'src/laya_pokemon/core.py'
CACHE_PATH = ROOT / 'src/laya_pokemon/plan_snapshot_cache.py'
SNAPSHOT_SOURCE_SHA = '98aea4384880bd173f1a0f1e82e74ee74e7621f095f6ba57c3d3c786b0a294cf'
CACHE_FILE_SHA = '7ecc6b78c1da063a1dc48aa6768c38c8458317bc2b7ab1b85fcaee6e02e7d9c8'
# Same-module reload must retain the originals needed for explicit rollback.
_REGISTRY = globals().get('_REGISTRY', {})


def _is_path(value, expected):
    return isinstance(value, str) and Path(value).resolve() == expected


def _find_owned_main_globals(native):
    frame = inspect.currentframe()
    try:
        for _ in range(32):
            frame = frame.f_back
            if frame is None:
                return None
            code = frame.f_code
            if code.co_name != 'main' or not _is_path(code.co_filename, CAMPAIGN_PATH):
                continue
            namespace = frame.f_globals
            main = namespace.get('main')
            if (frame.f_locals.get('emulator') is native
                    and isinstance(main, FunctionType)
                    and main.__code__ is code
                    and main.__globals__ is namespace
                    and _is_path(namespace.get('__file__'), CAMPAIGN_PATH)):
                return namespace
        return None
    finally:
        del frame


def _function_from(function, expected_path, namespace=None):
    return (isinstance(function, FunctionType)
            and _is_path(function.__code__.co_filename, expected_path)
            and _is_path(function.__globals__.get('__file__'), expected_path)
            and (namespace is None or function.__globals__ is namespace))


def _verified_factory():
    raw = CACHE_PATH.read_bytes().replace(b'\r\n', b'\n')
    if hashlib.sha256(raw).hexdigest() != CACHE_FILE_SHA:
        return None
    module = ModuleType('_staged_verified_plan_snapshot_cache')
    module.__file__ = str(CACHE_PATH)
    # Execute the exact bytes hashed above; do not reopen between check and exec.
    exec(compile(raw, str(CACHE_PATH), 'exec'), module.__dict__)
    factory = module.__dict__.get('make_cached_snapshot_loader')
    return factory if _function_from(factory, CACHE_PATH, module.__dict__) else None


def install_for_owned_campaign(native):
    """True=installed, None=no matching main frame, False=optional check failed.

    Parent must already verify native/owner. Existing records use only object
    identities. An explicit rollback stays rolled back on subsequent calls.
    """
    record = _REGISTRY.get(id(native))
    if record is not None and record['native'] is native:
        return record['globals'].get('load_plan_snapshot') is record['cached']
    try:
        namespace = _find_owned_main_globals(native)
        if namespace is None:
            return None
        if not isinstance(namespace, dict) or not _is_path(namespace.get('__file__'), CAMPAIGN_PATH):
            return False
        original = namespace.get('load_plan_snapshot')
        load_plan = namespace.get('load_plan')
        sha256_file = namespace.get('sha256_file')
        if not _function_from(original, CAMPAIGN_PATH, namespace):
            return False
        code = original.__code__
        if (code.co_argcount != 1 or code.co_kwonlyargcount != 0
                or code.co_flags & 0x0C or code.co_firstlineno != 43):
            return False
        lines, first_line = inspect.getsourcelines(original)
        if (first_line != 43 or hashlib.sha256(''.join(lines).encode('utf-8')).hexdigest()
                != SNAPSHOT_SOURCE_SHA):
            return False
        if not (_function_from(load_plan, PLAN_PATH)
                and _function_from(sha256_file, CORE_PATH)):
            return False
        factory = _verified_factory()
        if factory is None:
            return False
        cached = factory(load_plan, sha256_file)
        record = {'native': native, 'globals': namespace,
                  'original': original, 'cached': cached}
        namespace['load_plan_snapshot'] = cached
        _REGISTRY[id(native)] = record
        return True
    except Exception:
        # Optional speed optimization must never pause or terminate campaign.
        return False


def rollback(native):
    """Restore only our still-installed callable; never replace another edit."""
    record = _REGISTRY.get(id(native))
    if record is None or record['native'] is not native:
        return False
    namespace = record['globals']
    if namespace.get('load_plan_snapshot') is not record['cached']:
        return False
    namespace['load_plan_snapshot'] = record['original']
    return True
