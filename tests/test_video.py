from laya_pokemon.video import recording_smoke


def test_mp4_contains_expected_frames_and_dimensions(tmp_path):
    import imageio.v2 as imageio
    target = tmp_path / "test.mp4"
    result = recording_smoke(target)
    assert result["frames"] == 60 and result["playback_seconds"] == 2
    reader = imageio.get_reader(str(target))
    try:
        assert reader.count_frames() == 60
        assert reader.get_data(0).shape == (432, 480, 3)
        assert round(reader.get_meta_data()["fps"]) == 30
    finally:
        reader.close()

