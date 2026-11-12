"""Independent validator.

This module deliberately re-derives every check from the raw response data
instead of importing solver internals, so a bug shared between the solver and
the validator cannot hide.  It verifies:

1. item quantities (sum of placements == requested qty);
2. every placement is inside the box's inner dimensions;
3. no two placements overlap (strict axis-aligned AABB test);
4. rotations are legal for the item's orientation policy;
5. gross weight does not exceed the box's max gross weight;
6. volumetric weight, chargeable weight, fees and totals are arithmetically
   correct for every freight plan.

``unpacked`` entries are checked for consistency with the request as well.
"""
from __future__ import annotations

import math
from typing import Any

_AXES = {0, 1, 2}


def _ceildiv(a: int, b: int) -> int:
    return -((-a) // b)


def validate_solution(request: dict, response: dict, box_types: list[dict], plans: list[dict]) -> list[str]:
    errors: list[str] = []
    box_by_id = {b["id"]: b for b in box_types}
    plan_by_id = {p["id"]: p for p in plans}

    req_items = {i["sku"]: i for i in request["items"]}

    # ---- gather placements across every quote (they share one packing set) --
    # Each quote has its own boxes; all quotes must describe the same geometry.
    quote_geometries: list[list[dict]] = []
    for quote in response.get("quotes", []):
        qboxes = quote.get("boxes", [])
        quote_geometries.append([
            {
                "box_type_id": b["box_type_id"],
                "placements": b["placements"],
                "gross_weight_g": b["gross_weight_g"],
            }
            for b in qboxes
        ])

    if not quote_geometries:
        errors.append("response contains no freight quotes")
        return errors

    def _geo_sig(geo: list[dict]) -> list:
        return [
            (b["box_type_id"], sorted(
                (p["sku"], p["x"], p["y"], p["z"], p["dx"], p["dy"], p["dz"])
                for p in b["placements"]
            ))
            for b in geo
        ]

    sig0 = _geo_sig(quote_geometries[0])
    for k, geo in enumerate(quote_geometries[1:], start=1):
        if _geo_sig(geo) != sig0:
            errors.append(f"quote {k} geometry differs from quote 0")

    # ---- per-box checks -----------------------------------------------------
    placed_counts: dict[str, int] = {sku: 0 for sku in req_items}
    for box in response["quotes"][0]["boxes"]:
        bt = box_by_id.get(box["box_type_id"])
        if bt is None:
            errors.append(f"unknown box type id {box['box_type_id']}")
            continue
        placements = box["placements"]

        # weight
        item_w = sum(
            req_items[p["sku"]]["weight_g"] for p in placements
            if p["sku"] in req_items
        )
        gross = item_w + bt["box_weight_g"]
        if gross > bt["max_gross_g"]:
            errors.append(
                f"box {bt['code']}: gross {gross}g exceeds max {bt['max_gross_g']}g"
            )
        if gross != box["gross_weight_g"]:
            errors.append(
                f"box {bt['code']}: reported gross {box['gross_weight_g']}g "
                f"!= computed {gross}g"
            )

        # containment + rotation legality
        for idx, p in enumerate(placements):
            tag = f"box {bt['code']} placement {idx} ({p['sku']})"
            if p["x"] < 0 or p["y"] < 0 or p["z"] < 0:
                errors.append(f"{tag}: negative coordinate")
            if p["x"] + p["dx"] > bt["inner_l"] or p["y"] + p["dy"] > bt["inner_w"] \
               or p["z"] + p["dz"] > bt["inner_h"]:
                errors.append(f"{tag}: exceeds inner dimensions of {bt['code']}")
            if p["dx"] <= 0 or p["dy"] <= 0 or p["dz"] <= 0:
                errors.append(f"{tag}: non-positive size")
            ri = req_items.get(p["sku"])
            if ri is None:
                errors.append(f"{tag}: unknown sku {p['sku']}")
                continue
            placed_counts[p["sku"]] = placed_counts.get(p["sku"], 0) + 1
            rot = p.get("rotation")
            if (
                not isinstance(rot, list) or len(rot) != 3
                or set(rot) != _AXES
            ):
                errors.append(f"{tag}: invalid rotation {rot}")
            else:
                dims = (ri["l"], ri["w"], ri["h"])
                expect = (dims[rot[0]], dims[rot[1]], dims[rot[2]])
                if expect != (p["dx"], p["dy"], p["dz"]):
                    errors.append(
                        f"{tag}: oriented size {p['dx'],p['dy'],p['dz']} "
                        f"inconsistent with rotation {rot}"
                    )
                if ri["orientation"] == "upright" and rot[2] != 2:
                    errors.append(f"{tag}: upright item rotated onto its side ({rot})")

        # pairwise overlap (closed boxes are allowed to touch, not overlap)
        for i in range(len(placements)):
            a = placements[i]
            for j in range(i + 1, len(placements)):
                b = placements[j]
                overlap = not (
                    a["x"] + a["dx"] <= b["x"] or b["x"] + b["dx"] <= a["x"]
                    or a["y"] + a["dy"] <= b["y"] or b["y"] + b["dy"] <= a["y"]
                    or a["z"] + a["dz"] <= b["z"] or b["z"] + b["dz"] <= a["z"]
                )
                if overlap:
                    errors.append(
                        f"box {bt['code']}: placements {i} and {j} overlap"
                    )

    # ---- quantities ---------------------------------------------------------
    for sku, ri in req_items.items():
        n = placed_counts.get(sku, 0)
        unpacked_n = sum(u["qty"] for u in response.get("unpacked", []) if u["sku"] == sku)
        if n + unpacked_n != ri["qty"]:
            errors.append(
                f"sku {sku}: placed {n} + unpacked {unpacked_n} "
                f"!= requested {ri['qty']}"
            )

    for u in response.get("unpacked", []):
        if u["sku"] not in req_items:
            errors.append(f"unpacked references unknown sku {u['sku']}")
        if u["reason"] not in ("exceeds_all_boxes", "no_solution_found"):
            errors.append(f"unpacked {u['sku']}: invalid reason {u['reason']}")

    # ---- freight arithmetic, recomputed independently -----------------------
    for quote in response.get("quotes", []):
        plan = plan_by_id.get(quote["freight_plan_id"])
        if plan is None:
            errors.append(f"quote uses unknown freight plan {quote['freight_plan_id']}")
            continue
        sum_freight = 0.0
        sum_box = 0.0
        for box in quote["boxes"]:
            bt = box_by_id[box["box_type_id"]]
            outer_vol = bt["outer_l"] * bt["outer_w"] * bt["outer_h"]
            vol_w = _ceildiv(outer_vol, plan["vol_divisor"])
            gross = box["gross_weight_g"]
            raw = max(vol_w, gross)
            step = plan["billing_step_g"]
            chargeable = _ceildiv(raw, step) * step
            freight = round(chargeable // step * plan["price_per_step"], 4)
            total = round(freight + bt["box_fee"], 4)
            if outer_vol != box["outer_volume_mm3"]:
                errors.append(f"{plan['code']}/{bt['code']}: outer volume mismatch")
            if vol_w != box["volumetric_weight_g"]:
                errors.append(f"{plan['code']}/{bt['code']}: volumetric weight mismatch")
            if chargeable != box["chargeable_weight_g"]:
                errors.append(
                    f"{plan['code']}/{bt['code']}: chargeable weight "
                    f"{box['chargeable_weight_g']} != {chargeable}"
                )
            if abs(freight - box["freight_fee"]) > 1e-6:
                errors.append(f"{plan['code']}/{bt['code']}: freight fee mismatch")
            if abs(total - box["total_fee"]) > 1e-6:
                errors.append(f"{plan['code']}/{bt['code']}: total fee mismatch")
            sum_freight += freight
            sum_box += bt["box_fee"]
        sum_freight = round(sum_freight, 4)
        sum_total = round(sum_freight + sum_box, 4)
        if abs(sum_freight - quote["total_freight"]) > 1e-6:
            errors.append(f"{plan['code']}: quote freight total mismatch")
        if abs(round(sum_box, 4) - quote["total_box_fee"]) > 1e-6:
            errors.append(f"{plan['code']}: quote box fee total mismatch")
        if abs(sum_total - quote["total_fee"]) > 1e-6:
            errors.append(f"{plan['code']}: quote total fee mismatch")

    return errors
