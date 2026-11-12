"""Orchestration: request -> packings -> freight quotes -> validation."""
from __future__ import annotations

from typing import Any

from . import db
from .models import SolveRequest
from .packing import Box, Item, quote_box, search_packings
from .validator import validate_solution


def _items_from_req(req: SolveRequest) -> list[Item]:
    return [
        Item(
            sku=i.sku, l=i.l, w=i.w, h=i.h, weight_g=i.weight_g,
            orientation=i.orientation, qty=i.qty,
        )
        for i in req.items
    ]


def _box_to_dict(box: Box, plan: dict, box_index: int) -> dict:
    q = quote_box(box, plan)
    return {
        "box_type_id": box.box_type_id,
        "box_code": box.box_code,
        "placements": [
            {
                "sku": p.item.sku,
                "box_index": box_index,
                "dx": p.dx, "dy": p.dy, "dz": p.dz,
                "x": p.x, "y": p.y, "z": p.z,
                "rotation": list(p.rotation),
            }
            for p in box.placed
        ],
        "item_weight_g": box.item_weight_g,
        "gross_weight_g": q["gross_weight_g"],
        "outer_volume_mm3": q["outer_volume_mm3"],
        "volumetric_weight_g": q["volumetric_weight_g"],
        "chargeable_weight_g": q["chargeable_weight_g"],
        "freight_fee": q["freight_fee"],
        "box_fee": q["box_fee"],
        "total_fee": q["total_fee"],
        "freight_detail": {
            "plan_code": plan["code"],
            "raw_chargeable_g": q["raw_chargeable_g"],
            "billing_steps": q["billing_steps"],
            "volumetric_weight_g": q["volumetric_weight_g"],
            "gross_weight_g": q["gross_weight_g"],
            "billing_step_g": plan["billing_step_g"],
            "price_per_step": plan["price_per_step"],
        },
    }


def _packing_multiset_key(packing: list[Box]) -> tuple:
    counts: dict[str, int] = {}
    for b in packing:
        counts[b.box_code] = counts.get(b.box_code, 0) + 1
    return tuple(sorted(counts.items()))


def _packing_summary(packing: list[Box]) -> dict:
    return {
        "key": list(_packing_multiset_key(packing)),
        "n_boxes": len(packing),
        "box_codes": [b.box_code for b in packing],
        "total_item_weight_g": sum(b.item_weight_g for b in packing),
        "total_gross_weight_g": sum(b.item_weight_g + b.box_weight_g for b in packing),
        "total_box_fee": round(sum(b.box_fee for b in packing), 4),
        "used_volume_mm3": sum(b.used_volume for b in packing),
        "inner_volume_mm3": sum(b.inner_volume for b in packing),
    }


def solve(req: SolveRequest) -> dict[str, Any]:
    box_specs = db.get_boxes(req.box_type_ids) if req.box_type_ids else db.list_boxes()
    plans = db.get_plans(req.freight_plan_ids) if req.freight_plan_ids else db.list_plans()
    if not box_specs:
        raise ValueError("没有可用的候选箱型")
    if not plans:
        raise ValueError("没有可用的运费方案")

    items = _items_from_req(req)
    warnings: list[str] = []

    packings, infeasible_items = search_packings(
        items, box_specs, max_boxes=req.max_boxes, candidate_limit=req.candidate_limit
    )

    # ---- unpacked list ------------------------------------------------------
    unpacked: list[dict] = []
    skus_in_packings: set[str] = set()
    for packing in packings:
        for b in packing:
            for p in b.placed:
                skus_in_packings.add(p.item.sku)

    req_by_sku = {i.sku: i for i in items}
    for it in infeasible_items:
        unpacked.append({
            "sku": it.sku,
            "qty": it.qty,
            "reason": "exceeds_all_boxes",
            "detail": (
                f"{it.sku} 单件尺寸 {it.l}x{it.w}x{it.h}mm / {it.weight_g}g "
                "在允许朝向下放不进任何候选箱型，或单件即超过箱型最大毛重"
            ),
        })

    if not packings:
        # everything not proven infeasible is "algorithm found nothing"
        accounted = {u["sku"] for u in unpacked}
        for it in items:
            if it.sku not in accounted:
                unpacked.append({
                    "sku": it.sku,
                    "qty": it.qty,
                    "reason": "no_solution_found",
                    "detail": (
                        f"启发式算法未在 {req.max_boxes} 箱上限内找到可装入 "
                        f"{it.sku} 全部数量的组合，不代表数学上一定无解"
                    ),
                })
        response = {
            "feasible": False,
            "quotes": [],
            "cheapest_freight_plan_code": None,
            "packings": [],
            "unpacked": unpacked,
            "warnings": warnings,
            "validator_passed": False,
            "validator_errors": ["no feasible packing produced"],
        }
        return response

    # ---- fee matrix: every distinct packing x every plan --------------------
    # Different solver strategies can succeed on the same box multiset; keep
    # only one packing per multiset (prefer the one with fewer empty/looser
    # boxes — they all have equal length here, so first wins).
    unique_packings: dict[tuple, list[Box]] = {}
    for packing in packings:
        key = _packing_multiset_key(packing)
        if key not in unique_packings:
            unique_packings[key] = packing
    packings = list(unique_packings.values())

    fee_matrix: list[dict] = []
    for idx, packing in enumerate(packings):
        summary = _packing_summary(packing)
        row: dict[str, Any] = {
            "packing_index": idx,
            "n_boxes": summary["n_boxes"],
            "box_codes": summary["box_codes"],
            "total_gross_weight_g": summary["total_gross_weight_g"],
            "total_box_fee": summary["total_box_fee"],
            "plan_fees": {},
        }
        for plan in plans:
            total_freight = 0.0
            for b in packing:
                total_freight += quote_box(b, plan)["freight_fee"]
            row["plan_fees"][plan["code"]] = round(
                total_freight + summary["total_box_fee"], 4
            )
        fee_matrix.append(row)

    # ---- best packing per plan, build quotes --------------------------------
    quotes: list[dict] = []
    for plan in plans:
        best_row = min(fee_matrix, key=lambda r: r["plan_fees"][plan["code"]])
        packing = packings[best_row["packing_index"]]
        boxes_out = [_box_to_dict(b, plan, k) for k, b in enumerate(packing)]
        total_freight = round(sum(b["freight_fee"] for b in boxes_out), 4)
        total_box_fee = round(sum(b["box_fee"] for b in boxes_out), 4)
        quotes.append({
            "freight_plan_id": plan["id"],
            "freight_plan_code": plan["code"],
            "total_freight": total_freight,
            "total_box_fee": total_box_fee,
            "total_fee": round(total_freight + total_box_fee, 4),
            "boxes": boxes_out,
            "packing_index": best_row["packing_index"],
        })

    cheapest = min(quotes, key=lambda q: q["total_fee"])

    # ---- split-can-be-cheaper explanation -----------------------------------
    split_notes = _explain_splitting(fee_matrix, plans)
    warnings.extend(split_notes)

    # any requested item not present in the packing (partial leftover case:
    # search only returns full packings, so this is defensive)
    for it in items:
        if it.sku not in skus_in_packings and not any(u["sku"] == it.sku for u in unpacked):
            unpacked.append({
                "sku": it.sku, "qty": it.qty,
                "reason": "no_solution_found",
                "detail": "启发式算法未能为该商品找到装箱位置，不代表一定无解",
            })

    packing_summaries = []
    for row in fee_matrix:
        packing_summaries.append({
            "packing_index": row["packing_index"],
            "n_boxes": row["n_boxes"],
            "box_codes": row["box_codes"],
            "total_gross_weight_g": row["total_gross_weight_g"],
            "total_box_fee": row["total_box_fee"],
            "plan_total_fees": row["plan_fees"],
        })

    response = {
        "feasible": all(u["reason"] != "no_solution_found" for u in unpacked)
        and all(u["reason"] != "exceeds_all_boxes" for u in unpacked),
        "quotes": quotes,
        "cheapest_freight_plan_code": cheapest["freight_plan_code"],
        "packings": packing_summaries,
        "unpacked": unpacked,
        "warnings": warnings,
        "validator_passed": False,
        "validator_errors": [],
    }

    # ---- independent validation ---------------------------------------------
    request_dict = {
        "items": [i.model_dump() for i in req.items],
        "max_boxes": req.max_boxes,
    }
    errors = validate_solution(request_dict, response, box_specs, plans)
    response["validator_passed"] = not errors
    response["validator_errors"] = errors
    return response


def _explain_splitting(fee_matrix: list[dict], plans: list[dict]) -> list[str]:
    """Find plans where a packing with MORE boxes beats the fewest-box one."""
    notes: list[str] = []
    if len(fee_matrix) < 2:
        return notes
    fewest_n = min(r["n_boxes"] for r in fee_matrix)
    fewest_rows = [r for r in fee_matrix if r["n_boxes"] == fewest_n]
    for plan in plans:
        code = plan["code"]
        fewest_best = min(r["plan_fees"][code] for r in fewest_rows)
        for r in fee_matrix:
            if r["n_boxes"] > fewest_n and r["plan_fees"][code] < fewest_best - 1e-9:
                notes.append(
                    f"{code}: 拆成 {r['n_boxes']} 箱 {'+'.join(r['box_codes'])} "
                    f"总价 {r['plan_fees'][code]:.2f}，比最少 {fewest_n} 箱的 "
                    f"{fewest_best:.2f} 还便宜 —— "
                    "单箱计费重量向上取整到步长，拆箱后各箱分别取整，"
                    "体积重量与毛重的较大值可能整体下降，省下的运费可超过多出的箱费"
                )
                break
    return notes
