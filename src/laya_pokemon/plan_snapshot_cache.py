"""Staged, single-file snapshot cache; importing this module installs nothing.

Interface: make_cached_snapshot_loader(original_load_plan, original_sha256_file)
returns a callable with the same one-path argument and result as
campaign.load_plan_snapshot. Use one instance only from the campaign thread.
"""
import json
import os


def _signature(stat):
    return (stat.st_dev, stat.st_ino, stat.st_size,
            stat.st_mtime_ns, stat.st_ctime_ns)


def make_cached_snapshot_loader(load_plan, sha256_file):
    """Cache validated JSON bytes, SHA, and stat identity; never cache a dict.

    Metadata stability is the cache's consistency contract. A writer that can
    change bytes while preserving every identity/size/time field is outside
    that contract, just as an undetectable filesystem metadata change is.
    PermissionError clears the cache and returns None. Other original errors
    clear the cache and propagate. This factory does not import campaign.
    """
    cache = None

    def cached_snapshot(path):
        nonlocal cache
        try:
            key = os.path.normcase(os.path.abspath(os.fspath(path)))
            before = _signature(path.stat())
            if cache is not None and cache[0] == key and cache[1] == before:
                # A stat alone can succeed under Windows sharing locks. Probe
                # read access without reading file contents, and verify that
                # the opened identity is the one whose bytes were cached.
                with path.open('rb') as stream:
                    opened = _signature(os.fstat(stream.fileno()))
                if opened != before:
                    cache = None
                    return None
                candidate = json.loads(cache[2])
                after = _signature(path.stat())
                if after != before:
                    cache = None
                    return None
                return candidate, cache[3]

            # Clearing before a miss also guarantees this instance retains at
            # most one file and never reuses a previous snapshot after errors.
            cache = None
            candidate = load_plan(path)
            candidate_hash = sha256_file(path)
            # ASCII escaping preserves JSON strings containing lone surrogates
            # that the original decoder accepts. No live mutable object stays.
            encoded = json.dumps(candidate, ensure_ascii=True,
                                 separators=(',', ':')).encode('ascii')
            after = _signature(path.stat())
            if after != before:
                return None
            cache = (key, after, encoded, candidate_hash)
            return candidate, candidate_hash
        except PermissionError:
            cache = None
            return None
        except Exception:
            cache = None
            raise

    return cached_snapshot
