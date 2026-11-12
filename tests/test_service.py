"""End-to-end service + independent validator tests."""
import pytest

from app.models import ItemSpec, SolveRequest
from app.service import solve
from app.validator import validate_solution


BOXES = [
    {"id": 1, "code": "S", "name": "", "inner_l": 200, "inner_w": 150, "inner_h": 120,
     "outer_l": 210, "outer_w": 160, "outer_h": 130, "box_weight_g": 180,
     "box_fee": 1.2, "max_gross_g": 3000, "active": True},
    {"id": 2, "code": "M", "name": "", "inner_l": 300, "inner_w": 220, "inner_h": 200,
     "outer_l": 312, "outer_w": 232, "outer_h": 212, "box_weight_g": 320,
     "box_fee": 2.0, "max_gross_g": 8000, "active": True},
]
PLANS = [
    {"id": 1, "code": "STD", "name": "", "vol_divisor": 6000, "unit": "g",
     "billing_step_g": 1000, "price_per_step": 8.0, "active": True},
    {"id": 2, "code": "AIR", "name": "", "vol_divisor": 5000, "unit": "g",
     "billing_step_g": 500, "price_per_step": 5.0, "active": True},
]


@pytest.fixture(autouse=True)
def _catalog(monkeypatch):
    monkeypatch.setattr("app.service.db.list_boxes", lambda active_only=True: BOXES)
    monkeypatch.setattr("app.service.db.get_boxes", lambda ids: BOXES)
    monkeypatch.setattr("app.service.db.list_plans", lambda active_only=True: PLANS)
    monkeypatch.setattr("app.service.db.get_plans", lambda ids: PLANS)
    monkeypatch.setattr("app.service.db.save_run", lambda *a, **k: None)


def _req(specs):
    return SolveRequest(items=[ItemSpec(**s) for s in specs])


def test_happy_path_validates_clean():
    req = _req([
        {"sku": "A", "l": 120, "w": 100, "h": 80, "weight_g": 700,
         "orientation": "any", "qty": 3},
        {"sku": "B", "l": 60, "w": 60, "h": 60, "weight_g": 300,
         "orientation": "upright", "qty": 5},
    ])
    res = solve(req)
    assert res["validator_passed"], res["validator_errors"]
    assert res["unpacked"] == []
    assert len(res["quotes"]) == 2
    # quantity check inside validator already; explicitly count placements
    counts = {"A": 0, "B": 0}
    for q in res["quotes"]:
        for b in q["boxes"]:
            for p in b["placements"]:
                counts[p["sku"]] += 1
        break
    assert counts == {"A": 3, "B": 5}


def test_proven_infeasible_distinguished_from_no_solution():
    req = _req([
        {"sku": "HUGE", "l": 900, "w": 900, "h": 900, "weight_g": 100,
         "orientation": "any", "qty": 1},
    ])
    res = solve(req)
    assert res["feasible"] is False
    assert len(res["unpacked"]) == 1
    u = res["unpacked"][0]
    assert u["reason"] == "exceeds_all_boxes"


def test_upright_rotation_never_sideways():
    req = _req([
        {"sku": "U", "l": 80, "w": 80, "h": 190, "weight_g": 200,
         "orientation": "upright", "qty": 2},
    ])
    res = solve(req)
    assert res["validator_passed"], res["validator_errors"]
    for q in res["quotes"][:1]:
        for b in q["boxes"]:
            for p in b["placements"]:
                assert p["rotation"][2] == 2
                assert p["dz"] == 190


def test_split_packing_can_be_cheaper_and_is_explained(monkeypatch):
    boxes = [
        {"id": 1, "code": "S", "name": "", "inner_l": 200, "inner_w": 200, "inner_h": 200,
         "outer_l": 220, "outer_w": 220, "outer_h": 220, "box_weight_g": 150,
         "box_fee": 1.5, "max_gross_g": 20000, "active": True},
        {"id": 3, "code": "L", "name": "", "inner_l": 310, "inner_w": 310, "inner_h": 310,
         "outer_l": 330, "outer_w": 330, "outer_h": 330, "box_weight_g": 200,
         "box_fee": 2.0, "max_gross_g": 20000, "active": True},
    ]
    plans = [
        {"id": 1, "code": "STD", "name": "", "vol_divisor": 6000, "unit": "g",
         "billing_step_g": 1000, "price_per_step": 8.0, "active": True},
    ]
    monkeypatch.setattr("app.service.db.list_boxes", lambda active_only=True: boxes)
    monkeypatch.setattr("app.service.db.get_boxes", lambda ids: boxes)
    monkeypatch.setattr("app.service.db.list_plans", lambda active_only=True: plans)
    monkeypatch.setattr("app.service.db.get_plans", lambda ids: plans)
    monkeypatch.setattr("app.service.db.save_run", lambda *a, **k: None)

    req = _req([{"sku": "A", "l": 150, "w": 150, "h": 150, "weight_g": 300,
                 "orientation": "any", "qty": 2}])
    res = solve(req)
    assert res["validator_passed"], res["validator_errors"]
    fees = {tuple(p["box_codes"]): p["plan_total_fees"]["STD"] for p in res["packings"]}
    assert fees[("L",)] == 50.0
    assert fees[("S", "S")] == 35.0
    assert any("拆成 2 箱" in w and "便宜" in w for w in res["warnings"])
    # solver returns distinct multisets only
    keys = [tuple(p["box_codes"]) for p in res["packings"]]
    assert len(keys) == len(set(keys))


def test_validator_catches_overlap():
    request = {"items": [
        {"sku": "A", "l": 100, "w": 100, "h": 100, "weight_g": 100,
         "orientation": "any", "qty": 2},
    ]}
    response = {
        "quotes": [{
            "freight_plan_id": 1, "freight_plan_code": "STD",
            "total_freight": 16.0, "total_box_fee": 1.2, "total_fee": 17.2,
            "boxes": [{
                "box_type_id": 1, "box_code": "S",
                "gross_weight_g": 380,
                "outer_volume_mm3": 210 * 160 * 130,
                "volumetric_weight_g": -(-(210 * 160 * 130) // 6000),
                "chargeable_weight_g": 1000,
                "freight_fee": 8.0, "box_fee": 1.2, "total_fee": 9.2,
                "placements": [
                    {"sku": "A", "box_index": 0, "dx": 100, "dy": 100, "dz": 100,
                     "x": 0, "y": 0, "z": 0, "rotation": [0, 1, 2]},
                    {"sku": "A", "box_index": 0, "dx": 100, "dy": 100, "dz": 100,
                     "x": 50, "y": 0, "z": 0, "rotation": [0, 1, 2]},
                ],
            }],
        }],
        "unpacked": [],
    }
    errors = validate_solution(request, response, BOXES, PLANS)
    assert any("overlap" in e for e in errors)


def test_validator_catches_wrong_quantity_and_fee():
    request = {"items": [
        {"sku": "A", "l": 100, "w": 100, "h": 100, "weight_g": 100,
         "orientation": "any", "qty": 3},
    ]}
    response = {
        "quotes": [{
            "freight_plan_id": 1, "freight_plan_code": "STD",
            "total_freight": 99.0, "total_box_fee": 1.2, "total_fee": 100.2,
            "boxes": [{
                "box_type_id": 1, "box_code": "S",
                "gross_weight_g": 280,
                "outer_volume_mm3": 210 * 160 * 130,
                "volumetric_weight_g": -(-(210 * 160 * 130) // 6000),
                "chargeable_weight_g": 1000,
                "freight_fee": 8.0, "box_fee": 1.2, "total_fee": 9.2,
                "placements": [
                    {"sku": "A", "box_index": 0, "dx": 100, "dy": 100, "dz": 100,
                     "x": 0, "y": 0, "z": 0, "rotation": [0, 1, 2]},
                ],
            }],
        }],
        "unpacked": [],
    }
    errors = validate_solution(request, response, BOXES, PLANS)
    assert any("requested 3" in e for e in errors)
    assert any("total mismatch" in e for e in errors)
