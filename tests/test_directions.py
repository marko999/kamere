from src.config import CAMERAS, get_cameras_for_crossing, CROSSINGS


def test_every_mup_crossing_has_both_directions():
    for name in CROSSINGS:
        cams = get_cameras_for_crossing(name)
        mup = [c for c in cams if c["source_type"] == "mup"]
        if not mup:
            continue
        dirs = {c["direction"] for c in mup}
        assert "entrance" in dirs and "exit" in dirs, (
            f"Crossing {name!r} missing a direction: got {dirs}"
        )


def test_camera_directions_valid():
    for cam in CAMERAS:
        assert cam["direction"] in ("entrance", "exit"), (
            f"Camera {cam['id']!r} has invalid direction: {cam['direction']!r}"
        )
