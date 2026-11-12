"""Tests for the packing engine: geometry, weight limits, multi-box search."""
import pytest

from app.packing import (
    Item, item_fits_box_alone, pack_sequential, search_packings,
)


def make_box(inner, outer=None, weight=200, fee=1.0, max_gross=100000, code="BX", bid=1):
    l, w, h = inner
    if outer is None:
        outer = (l + 10, w + 10, h + 10)
    return {
        "id": bid, "code": code, "inner_l": l, "inner_w": w, "inner_h": h,
        "outer_l": outer[0], "outer_w": outer[1], "outer_h": outer[2],
        "box_weight_g": weight, "box_fee": fee, "max_gross_g": max_gross,
        "active": True, "name": "",
    }


def test_single_item_fits_exactly():
    spec = make_box((100, 100, 100))
    items = [Item("A", 100, 100, 100, 500, "any", qty=1)]
    packings, infeasible = search_packings(items, [spec], max_boxes=2)
    assert infeasible == []
    assert packings
    for packing in packings:
        assert sum(len(b.placed) for b in packing) == 1
    box = packings[0][0]
    assert len(box.placed) == 1
    p = box.placed[0]
    assert (p.x, p.y, p.z) == (0, 0, 0)
    assert (p.dx, p.dy, p.dz) == (100, 100, 100)


def test_oversize_item_marked_infeasible():
    spec = make_box((100, 100, 100))
    items = [Item("BIG", 200, 50, 50, 100, "any", qty=1)]
    packings, infeasible = search_packings(items, [spec], max_boxes=2)
    assert packings == []
    assert len(infeasible) == 1
    assert infeasible[0].sku == "BIG"


def test_upright_item_cannot_lie_down():
    # item 60x60x200 upright: height 200 > box height 100, cannot lie down
    spec = make_box((200, 200, 100))
    item = Item("U", 60, 60, 200, 100, "upright", qty=1)
    assert not item_fits_box_alone(item, spec)
    # same item with "any" can lie down
    item_any = Item("U", 60, 60, 200, 100, "any", qty=1)
    assert item_fits_box_alone(item_any, spec)


def test_gross_weight_limit_blocks_packing():
    spec = make_box((1000, 1000, 1000), weight=100, max_gross=600)
    items = [Item("H", 100, 100, 100, 500, "any", qty=2)]
    packings, infeasible = search_packings(items, [spec], max_boxes=3)
    # each item alone: 500 + 100 = 600 OK, so not "proven infeasible"
    assert infeasible == []
    # needs 2 boxes because one box can hold only one unit (600 cap)
    assert len(packings) >= 1
    for packing in packings:
        for b in packing:
            assert b.item_weight_g + b.box_weight_g <= b.max_gross_g


def test_multi_box_spill():
    small = make_box((100, 100, 100), code="S", bid=1)
    items = [Item("A", 60, 60, 60, 100, "any", qty=4)]  # volume 864k vs box 1m
    packings, _ = search_packings(items, [small], max_boxes=4)
    assert packings, "should find a multi-box packing"
    # every returned packing must contain exactly the 4 units, no empty boxes
    for packing in packings:
        assert sum(len(b.placed) for b in packing) == 4
        assert all(b.placed for b in packing)
    # a single box cannot fit 4 cubes of 60 (60*2 > 100 along every axis),
    # so every feasible packing uses 4 boxes
    assert all(len(p) == 4 for p in packings)


def test_two_box_types_chooses_combos():
    s = make_box((100, 100, 100), code="S", bid=1, fee=1.0)
    l = make_box((200, 200, 200), code="L", bid=2, fee=3.0)
    items = [Item("A", 80, 80, 80, 100, "any", qty=5)]
    packings, _ = search_packings(items, [s, l], max_boxes=5)
    assert packings
    for packing in packings:
        assert sum(len(b.placed) for b in packing) == 5
        assert all(b.placed for b in packing)


def test_two_equal_cubes_pack_side_by_side():
    # regression for extreme-point projection: two 150 cubes must pack into
    # a 310 box (150*2 < 310) instead of spilling into a second box
    spec = make_box((310, 310, 310))
    items = [Item("A", 150, 150, 150, 100, "any", qty=2)]
    packings, _ = search_packings(items, [spec], max_boxes=2)
    assert any(len(p) == 1 and len(p[0].placed) == 2 for p in packings)


def test_sequential_pack_no_overlap_on_tight_case():
    spec = make_box((300, 200, 150))
    items = [Item(f"A{i}", 90 + i * 5, 80, 70, 100, "any", qty=3) for i in range(3)]
    instances = [ins for it in items for ins in it.expand()]
    boxes = pack_sequential(instances, [spec])
    assert boxes is not None
    b = boxes[0]
    # pairwise disjoint check
    for i, a in enumerate(b.placed):
        for c in b.placed[i + 1:]:
            assert (
                a.x + a.dx <= c.x or c.x + c.dx <= a.x
                or a.y + a.dy <= c.y or c.y + c.dy <= a.y
                or a.z + a.dz <= c.z or c.z + c.dz <= a.z
            )
