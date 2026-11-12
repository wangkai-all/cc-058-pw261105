"""3D bin-packing engine (heuristic) and freight calculation.

Only axis-aligned placement of rectangular cuboids is supported:

* ``orientation="upright"``  -> the original height axis stays vertical,
  only the two horizontal 90-degree turns are allowed.
* ``orientation="any"``      -> all six axis permutations are allowed.

The placement heuristic is an extreme-point / deepest-bottom-left greedy
search.  It is *heuristic*: failure to find a packing does NOT prove that no
packing exists.  Callers must distinguish "proven infeasible" (an item does
not fit in any single box even alone, or violates gross-weight limits) from
"no solution found by this algorithm".
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import permutations
from typing import Optional

# ---------------------------------------------------------------------------
# Orientations
# ---------------------------------------------------------------------------


def orientations(l: int, w: int, h: int, mode: str) -> list[tuple[tuple[int, int, int], tuple[int, int, int]]]:
    """Return unique oriented sizes + axis permutations for one product."""
    dims = (l, w, h)
    out: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    for p in set(permutations((0, 1, 2))):
        if mode == "upright" and p[2] != 2:
            # original height axis (index 2) must remain on the z axis
            continue
        oriented = (dims[p[0]], dims[p[1]], dims[p[2]])
        if oriented not in out:
            out[oriented] = p
    # prefer orientations that keep a low profile (small dz first)
    return sorted(out.items(), key=lambda kv: (kv[0][2], kv[0][1], kv[0][0]))


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Item:
    sku: str
    l: int
    w: int
    h: int
    weight_g: int
    orientation: str  # "any" | "upright"
    qty: int = 1

    def expand(self) -> list["ItemInstance"]:
        return [
            ItemInstance(self.sku, self.l, self.w, self.h, self.weight_g, self.orientation)
            for _ in range(self.qty)
        ]


@dataclass
class ItemInstance:
    sku: str
    l: int
    w: int
    h: int
    weight_g: int
    orientation: str
    uid: int = -1


@dataclass
class Placed:
    item: ItemInstance
    x: int
    y: int
    z: int
    dx: int
    dy: int
    dz: int
    rotation: tuple[int, int, int]


@dataclass
class Box:
    box_type_id: int
    box_code: str
    inner: tuple[int, int, int]
    outer: tuple[int, int, int]
    box_weight_g: int
    box_fee: float
    max_gross_g: int
    placed: list[Placed] = field(default_factory=list)
    eps: list[tuple[int, int, int]] = field(default_factory=lambda: [(0, 0, 0)])
    item_weight_g: int = 0

    @property
    def used_volume(self) -> int:
        return sum(p.dx * p.dy * p.dz for p in self.placed)

    @property
    def inner_volume(self) -> int:
        return self.inner[0] * self.inner[1] * self.inner[2]


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _overlaps(a: Placed, x: int, y: int, z: int, dx: int, dy: int, dz: int) -> bool:
    if x + dx <= a.x or a.x + a.dx <= x:
        return False
    if y + dy <= a.y or a.y + a.dy <= y:
        return False
    if z + dz <= a.z or a.z + a.dz <= z:
        return False
    return True


def _fits(box: Box, x: int, y: int, z: int, dx: int, dy: int, dz: int) -> bool:
    bl, bw, bh = box.inner
    if x < 0 or y < 0 or z < 0:
        return False
    if x + dx > bl or y + dy > bw or z + dz > bh:
        return False
    return not any(_overlaps(p, x, y, z, dx, dy, dz) for p in box.placed)


def _prune_eps(box: Box) -> None:
    """Drop extreme points outside the box or dominated by another point."""
    bl, bw, bh = box.inner
    pts = [p for p in set(box.eps) if p[0] <= bl and p[1] <= bw and p[2] <= bh]
    kept: list[tuple[int, int, int]] = []
    for i, p in enumerate(pts):
        dominated = False
        for j, q in enumerate(pts):
            if i == j:
                continue
            if q[0] <= p[0] and q[1] <= p[1] and q[2] <= p[2] and q != p:
                dominated = True
                break
        if not dominated:
            kept.append(p)
    # deepest-bottom-left order
    kept.sort(key=lambda p: (p[2], p[1], p[0]))
    box.eps = kept


def _project_eps(box: Box, new: Placed) -> None:
    """Generate new extreme points after placing ``new``.

    Uses the projection rule from Crainic et al. (2008): the three naive
    corner points are pushed along their projection axis until they clear
    every already-placed item, instead of being left inside an occupied
    region.  Without this, two 150mm cubes cannot pack into a 280mm box
    although 2*150 < 280.
    """
    nx, ny, nz = new.x, new.y, new.z
    candidates = [
        (nx + new.dx, ny, nz, "x"),
        (nx, ny + new.dy, nz, "y"),
        (nx, ny, nz + new.dz, "z"),
    ]
    for px, py, pz, axis in candidates:
        for p in box.placed:
            if p is new:
                continue
            if axis == "x":
                if (p.x <= px < p.x + p.dx and p.y <= py < p.y + p.dy
                        and p.z <= pz < p.z + p.dz):
                    px = p.x + p.dx
            elif axis == "y":
                if (p.x <= px < p.x + p.dx and p.y <= py < p.y + p.dy
                        and p.z <= pz < p.z + p.dz):
                    py = p.y + p.dy
            else:
                if (p.x <= px < p.x + p.dx and p.y <= py < p.y + p.dy
                        and p.z <= pz < p.z + p.dz):
                    pz = p.z + p.dz
        box.eps.append((px, py, pz))
    _prune_eps(box)


def _try_place(box: Box, inst: ItemInstance) -> Optional[Placed]:
    """Try to place one instance into the box at the best available point."""
    if box.item_weight_g + inst.weight_g + box.box_weight_g > box.max_gross_g:
        return None
    best: Optional[tuple] = None  # (score, ep, oriented size, rotation)
    for (dx, dy, dz), rotation in orientations(inst.l, inst.w, inst.h, inst.orientation):
        for ep in box.eps:
            x, y, z = ep
            if _fits(box, x, y, z, dx, dy, dz):
                # prefer lowest z, then deepest-bottom-left, then small footprint
                score = (z, y, x, dx * dy * dz)
                if best is None or score < best[0]:
                    best = (score, ep, (dx, dy, dz), rotation)
                break  # first (deepest) EP that works for this orientation
    if best is None:
        return None
    _, ep, (dx, dy, dz), rotation = best
    x, y, z = ep
    p = Placed(inst, x, y, z, dx, dy, dz, rotation)
    box.placed.append(p)
    box.item_weight_g += inst.weight_g
    box.eps.remove(ep)
    _project_eps(box, p)
    return p


# ---------------------------------------------------------------------------
# Single-box and multi-box greedy packing
# ---------------------------------------------------------------------------


def _sort_instances(instances: list[ItemInstance], key: str) -> list[ItemInstance]:
    if key == "longest":
        return sorted(
            instances,
            key=lambda i: (max(i.l, i.w, i.h), i.l * i.w * i.h, i.weight_g),
            reverse=True,
        )
    # default: volume descending, then longest edge
    return sorted(
        instances,
        key=lambda i: (i.l * i.w * i.h, max(i.l, i.w, i.h), i.weight_g),
        reverse=True,
    )


def pack_sequential(
    instances: list[ItemInstance], box_specs: list[dict], sort_key: str = "volume"
) -> Optional[list[Box]]:
    """Fill boxes one after another; leftovers spill into the next box."""
    boxes = [_make_box(spec) for spec in box_specs]
    remaining = _sort_instances(list(instances), sort_key)
    for box in boxes:
        if not remaining:
            break
        still: list[ItemInstance] = []
        for inst in remaining:
            if _try_place(box, inst) is None:
                still.append(inst)
        remaining = still
    if remaining:
        return None
    return [b for b in boxes if b.placed]


def pack_best_fit(
    instances: list[ItemInstance], box_specs: list[dict], sort_key: str = "volume"
) -> Optional[list[Box]]:
    """Every item goes into the box where it currently fits tightest."""
    boxes = [_make_box(spec) for spec in box_specs]
    for inst in _sort_instances(list(instances), sort_key):
        snapshots = [_snapshot(b) for b in boxes]
        candidates: list[tuple[tuple, int]] = []  # (tightness score, box idx)
        for idx, box in enumerate(boxes):
            p = _try_place(box, inst)
            if p is not None:
                score = (box.inner_volume - box.used_volume, box.item_weight_g)
                candidates.append((score, idx))
        if not candidates:
            # nothing accepted this instance: packing fails
            return None
        # restore all boxes to their pre-item state, place only in the winner
        for b, snap in zip(boxes, snapshots):
            _restore(b, snap)
        winner_idx = min(candidates, key=lambda c: c[0])[1]
        if _try_place(boxes[winner_idx], inst) is None:
            return None  # defensive: a placement that worked once must work again
    non_empty = [b for b in boxes if b.placed]
    return non_empty if non_empty else None


def _snapshot(box: Box) -> tuple[list[Placed], list[tuple[int, int, int]], int]:
    return ([p for p in box.placed], list(box.eps), box.item_weight_g)


def _restore(box: Box, snap: tuple) -> None:
    box.placed, box.eps, box.item_weight_g = snap[0], list(snap[1]), snap[2]


def _make_box(spec: dict) -> Box:
    return Box(
        box_type_id=spec["id"],
        box_code=spec["code"],
        inner=(spec["inner_l"], spec["inner_w"], spec["inner_h"]),
        outer=(spec["outer_l"], spec["outer_w"], spec["outer_h"]),
        box_weight_g=spec["box_weight_g"],
        box_fee=spec["box_fee"],
        max_gross_g=spec["max_gross_g"],
    )


# ---------------------------------------------------------------------------
# Feasibility and multi-box search
# ---------------------------------------------------------------------------


def item_fits_box_alone(inst: Item, spec: dict) -> bool:
    """Definite check: can one unit of this item fit in this box at all?"""
    if inst.weight_g + spec["box_weight_g"] > spec["max_gross_g"]:
        return False
    for (dx, dy, dz), _ in orientations(inst.l, inst.w, inst.h, inst.orientation):
        if dx <= spec["inner_l"] and dy <= spec["inner_w"] and dz <= spec["inner_h"]:
            return True
    return False


def _multiset_key(specs: list[dict]) -> tuple:
    counts: dict[int, int] = {}
    for s in specs:
        counts[s["id"]] = counts.get(s["id"], 0) + 1
    return tuple(sorted(counts.items()))


def enumerate_box_combos(
    items: list[Item], box_specs: list[dict], max_boxes: int, candidate_limit: int
) -> list[list[dict]]:
    """Enumerate box-type multisets that pass necessary volume/weight bounds."""
    total_vol = sum(i.l * i.w * i.h * i.qty for i in items)
    total_item_w = sum(i.weight_g * i.qty for i in items)

    n_types = len(box_specs)
    combos: list[list[dict]] = []

    def gen(start: int, remaining: int, acc: list[dict]) -> None:
        if len(combos) >= candidate_limit:
            return
        if remaining == 0:
            cap_vol = sum(s["inner_l"] * s["inner_w"] * s["inner_h"] for s in acc)
            cap_w = sum(max(0, s["max_gross_g"] - s["box_weight_g"]) for s in acc)
            if cap_vol >= total_vol and cap_w >= total_item_w:
                combos.append(list(acc))
            return
        for idx in range(start, n_types):
            acc.append(box_specs[idx])
            gen(idx, remaining - 1, acc)
            acc.pop()

    # cheapest necessary-condition lower bound on number of boxes
    max_vol = max(s["inner_l"] * s["inner_w"] * s["inner_h"] for s in box_specs)
    max_cap = max(max(0, s["max_gross_g"] - s["box_weight_g"]) for s in box_specs)
    lb = max(
        math.ceil(total_vol / max_vol),
        math.ceil(total_item_w / max_cap) if max_cap else max_boxes + 1,
        1,
    )
    for k in range(lb, max_boxes + 1):
        gen(0, k, [])
        if len(combos) >= candidate_limit:
            break
    # fewer / smaller boxes first
    combos.sort(key=lambda c: (len(c), sum(s["inner_l"] * s["inner_w"] * s["inner_h"] for s in c)))
    return combos


def search_packings(
    items: list[Item],
    box_specs: list[dict],
    max_boxes: int = 12,
    candidate_limit: int = 40,
) -> tuple[list[list[Box]], list[Item]]:
    """Return feasible packings (deduplicated by box multiset) and items that
    provably fit no box at all."""
    infeasible: list[Item] = []
    solvable: list[Item] = []
    for it in items:
        if any(item_fits_box_alone(it, s) for s in box_specs):
            solvable.append(it)
        else:
            infeasible.append(it)

    instances: list[ItemInstance] = []
    uid = 0
    for it in solvable:
        for inst in it.expand():
            inst.uid = uid
            uid += 1
            instances.append(inst)

    found: dict[tuple, list[Box]] = {}
    for combo in enumerate_box_combos(solvable, box_specs, max_boxes, candidate_limit):
        key = _multiset_key(combo)
        if key in found:
            continue
        packing: Optional[list[Box]] = None
        for strategy, sort_key in (
            (pack_sequential, "volume"),
            (pack_sequential, "longest"),
            (pack_best_fit, "volume"),
            (pack_best_fit, "longest"),
        ):
            packing = strategy(instances, combo, sort_key)
            if packing:
                break
        if packing:
            found[key] = packing

    # All feasible multisets are retained (including larger box counts): the
    # service layer compares them per freight plan, because step-rounded
    # volumetric charging can make a split packing cheaper overall.
    return list(found.values()), infeasible


# ---------------------------------------------------------------------------
# Freight
# ---------------------------------------------------------------------------


def ceil_div(a: int, b: int) -> int:
    return -((-a) // b)


def quote_box(box: Box, plan: dict) -> dict:
    """Compute volumetric / chargeable weight and fees for one packed box."""
    ol, ow, oh = box.outer
    outer_vol = ol * ow * oh
    vol_weight = ceil_div(outer_vol, plan["vol_divisor"])
    gross = box.item_weight_g + box.box_weight_g
    raw_chargeable = max(vol_weight, gross)
    step = plan["billing_step_g"]
    chargeable = ceil_div(raw_chargeable, step) * step
    steps = chargeable // step
    freight_fee = round(steps * plan["price_per_step"], 4)
    total_fee = round(freight_fee + box.box_fee, 4)
    return {
        "outer_volume_mm3": outer_vol,
        "volumetric_weight_g": vol_weight,
        "gross_weight_g": gross,
        "raw_chargeable_g": raw_chargeable,
        "chargeable_weight_g": chargeable,
        "billing_steps": steps,
        "freight_fee": freight_fee,
        "box_fee": box.box_fee,
        "total_fee": total_fee,
    }
