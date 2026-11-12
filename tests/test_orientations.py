"""Tests for orientation generation."""
from app.packing import orientations


def test_any_six_orientations_for_cuboid():
    # all edges distinct -> exactly 6 unique oriented sizes
    result = orientations(10, 20, 30, "any")
    assert len(result) == 6
    sizes = {s for s, _ in result}
    assert sizes == {
        (10, 20, 30), (10, 30, 20), (20, 10, 30),
        (20, 30, 10), (30, 10, 20), (30, 20, 10),
    }


def test_upright_keeps_height_axis_vertical():
    result = orientations(10, 20, 30, "upright")
    assert len(result) == 2
    for size, perm in result:
        assert perm[2] == 2          # original axis 2 (h=30) stays on z
        assert size[2] == 30
    assert {s for s, _ in result} == {(10, 20, 30), (20, 10, 30)}


def test_cube_collapses_to_single_orientation():
    result = orientations(10, 10, 10, "any")
    assert len(result) == 1


def test_square_base_dedup():
    result = orientations(10, 10, 20, "any")
    assert len(result) == 3
