import json
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from laya_pokemon.live_frame import LiveFramePublisher


def pixels():
    image = np.zeros((144, 160, 4), dtype=np.uint8)
    image[..., 3] = 255
    image[12, 34] = [23, 45, 67, 255]
    return image


def test_real_png_pixels_dimensions_throttle_and_forced_status(tmp_path):
    clock = [100.]
    writer = LiveFramePublisher(tmp_path, clock=lambda: clock[0])
    image = pixels()
    assert writer.publish(image, 123)
    with Image.open(tmp_path / 'live-frame.png') as decoded:
        assert decoded.format == 'PNG' and decoded.size == (160, 144)
        assert decoded.getpixel((34, 12)) == (23, 45, 67)
        assert np.array_equal(np.asarray(decoded), image[..., :3])
    clock[0] += .249
    image[12, 34, 0] = 90
    assert not writer.publish(image, 124)
    assert json.loads((tmp_path / 'live-frame.json').read_text())['frame'] == 123
    clock[0] = 100.25
    assert writer.publish(image, 125)
    writer.update_status('paused_for_review', review_reason='low_hp')
    assert writer.publish(image, 125, force=True)
    record = json.loads((tmp_path / 'live-frame.json').read_text())
    assert record['status'] == 'paused_for_review' and record['review_reason'] == 'low_hp'
    writer.update_status('running')
    assert writer.publish(image, 125, force=True)
    writer.update_status('stopped')
    assert writer.publish(image, 125, force=True)
    assert json.loads((tmp_path / 'live-frame.json').read_text())['status'] == 'stopped'


def test_only_allowlisted_summary_copied_and_no_raw_secret(tmp_path):
    writer = LiveFramePublisher(tmp_path)
    secret = 'private-token-secret-123'
    mon = {'species_name': 'SNORLAX', 'level': 30, 'hp': 141, 'max_hp': 141, 'status': 0,
           'moves': [29], 'private_path': secret}
    state = {'phase': 'battle_menu', 'location': {'map_id': 23, 'x': 10, 'y': 61, 'endpoint': secret},
             'progress': {'party': [dict(mon) for _ in range(6)], 'badges_raw': 15, 'inventory': secret},
             'rawstate': secret, 'credentials': secret, 'endpoint': secret}
    writer.update_summary(state)
    state['progress']['party'][0]['hp'] = 0
    assert writer.publish(pixels(), 42)
    raw = (tmp_path / 'live-frame.json').read_text(encoding='utf-8')
    record = json.loads(raw)
    assert secret not in raw
    assert set(record) == {'frame', 'at', 'status', 'phase', 'review_reason', 'location', 'party', 'badges_raw'}
    assert record['location'] == {'map_id': 23, 'x': 10, 'y': 61}
    assert len(record['party']) == 6 and record['party'][0]['hp'] == 141
    assert set(record['party'][0]) == {'species_name', 'level', 'hp', 'max_hp', 'status'}
    assert record['badges_raw'] == 15


@pytest.mark.parametrize('operation', ['save', 'write_text', 'image_replace', 'json_replace'])
def test_windows_permission_error_only_skips_export_then_recovers(tmp_path, monkeypatch, operation):
    clock = [1.]
    writer = LiveFramePublisher(tmp_path, clock=lambda: clock[0])
    with monkeypatch.context() as patch:
        def locked(*args, **kwargs):
            raise PermissionError('Windows sharing lock')
        if operation == 'save':
            patch.setattr(Image.Image, 'save', locked)
        elif operation == 'write_text':
            patch.setattr(Path, 'write_text', locked)
        else:
            original = Path.replace
            def replace(path, target):
                if path.name == ('live-frame.png.tmp' if operation == 'image_replace' else 'live-frame.json.tmp'):
                    raise PermissionError('Windows sharing lock')
                return original(path, target)
            patch.setattr(Path, 'replace', replace)
        assert writer.publish(pixels(), 1) is False
    clock[0] += .25
    assert writer.publish(pixels(), 2)
    assert json.loads((tmp_path / 'live-frame.json').read_text())['frame'] == 2


@pytest.mark.parametrize('error', [OSError('disk failed'), ValueError('bad encoder')])
def test_non_permission_errors_are_not_swallowed(tmp_path, monkeypatch, error):
    def failed(*args, **kwargs):
        raise error
    monkeypatch.setattr(Image.Image, 'save', failed)
    with pytest.raises(type(error), match=str(error)):
        LiveFramePublisher(tmp_path).publish(pixels(), 1)


def test_unknown_or_malformed_values_never_become_raw_metadata(tmp_path):
    writer = LiveFramePublisher(tmp_path)
    writer.update_summary({'phase': 'https://secret', 'location': {'map_id': True, 'x': [], 'y': 3},
                           'progress': {'party': [{'species_name': 'https://secret', 'level': True,
                                                   'hp': {}, 'max_hp': -1, 'status': 'secret'}],
                                        'badges_raw': False}})
    assert writer.publish(pixels(), 1)
    record = json.loads((tmp_path / 'live-frame.json').read_text())
    assert record['phase'] is None and record['badges_raw'] is None
    assert record['location'] == {'map_id': None, 'x': None, 'y': 3}
    assert all(value is None for value in record['party'][0].values())


@pytest.mark.parametrize('bad_frame', [True, -1, '12'])
def test_frame_number_cannot_be_synthetic_metadata(tmp_path, bad_frame):
    with pytest.raises(ValueError, match='frame'):
        LiveFramePublisher(tmp_path).publish(pixels(), bad_frame)


def test_wrong_shape_or_dtype_not_exported(tmp_path):
    writer = LiveFramePublisher(tmp_path)
    for bad in (np.zeros((10, 10, 3), dtype=np.uint8), np.zeros((144, 160, 3), dtype=float)):
        with pytest.raises(ValueError, match='framebuffer'):
            writer.publish(bad, 1)
    assert not (tmp_path / 'live-frame.png').exists()
