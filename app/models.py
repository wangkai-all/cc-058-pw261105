"""Pydantic schemas for the packing planner.

All lengths are integer millimetres, weights are grams.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Catalog: box types
# ---------------------------------------------------------------------------


class BoxTypeIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(default="", max_length=80)
    inner_l: int = Field(gt=0, le=100000)
    inner_w: int = Field(gt=0, le=100000)
    inner_h: int = Field(gt=0, le=100000)
    outer_l: int = Field(gt=0, le=100000)
    outer_w: int = Field(gt=0, le=100000)
    outer_h: int = Field(gt=0, le=100000)
    box_weight_g: int = Field(gt=0)
    box_fee: float = Field(ge=0)
    max_gross_g: int = Field(gt=0)
    active: bool = True

    @field_validator("code")
    @classmethod
    def _code_clean(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("code required")
        return v


class BoxTypeOut(BoxTypeIn):
    id: int


# ---------------------------------------------------------------------------
# Catalog: freight plans
# ---------------------------------------------------------------------------


class FreightPlanIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(default="", max_length=80)
    # volumetric weight = ceil(outer volume mm^3 / divisor) in grams
    vol_divisor: int = Field(gt=0, description="mm^3 per gram of volumetric weight")
    unit: Literal["g", "kg"] = "g"
    billing_step_g: int = Field(gt=0, description="chargeable weight step in grams")
    price_per_step: float = Field(gt=0, description="price per billing step")
    active: bool = True


class FreightPlanOut(FreightPlanIn):
    id: int


# ---------------------------------------------------------------------------
# Solve request / response
# ---------------------------------------------------------------------------


class ItemSpec(BaseModel):
    sku: str = Field(min_length=1, max_length=60)
    l: int = Field(gt=0, le=100000)
    w: int = Field(gt=0, le=100000)
    h: int = Field(gt=0, le=100000)
    weight_g: int = Field(gt=0)
    # "any"  -> all six orientations
    # "upright" -> only horizontal 90-degree turns, h stays vertical
    orientation: Literal["any", "upright"] = "any"
    qty: int = Field(gt=0, le=100000)


class SolveRequest(BaseModel):
    items: list[ItemSpec] = Field(min_length=1)
    box_type_ids: Optional[list[int]] = None
    freight_plan_ids: Optional[list[int]] = None
    # search limits
    max_boxes: int = Field(default=12, ge=1, le=60)
    candidate_limit: int = Field(default=40, ge=1, le=200)


class Placement(BaseModel):
    """One placed item inside a box. Coordinates of the min corner, mm."""

    sku: str
    box_index: int
    # oriented dimensions along the box axes
    dx: int
    dy: int
    dz: int
    x: int
    y: int
    z: int
    # permutation of the original (l, w, h) axes onto (x, y, z), e.g. (2,0,1)
    rotation: tuple[int, int, int]


class PackedBox(BaseModel):
    box_type_id: int
    box_code: str
    placements: list[Placement]
    # grams
    item_weight_g: int
    gross_weight_g: int
    outer_volume_mm3: int
    volumetric_weight_g: int
    chargeable_weight_g: int
    freight_fee: float
    box_fee: float
    total_fee: float
    # per-plan freight detail
    freight_detail: dict


class FreightQuote(BaseModel):
    freight_plan_id: int
    freight_plan_code: str
    total_freight: float
    total_box_fee: float
    total_fee: float
    boxes: list[PackedBox]


class InfeasibleItem(BaseModel):
    sku: str
    qty: int
    reason: Literal["exceeds_all_boxes", "no_solution_found"]
    detail: str


class SolveResponse(BaseModel):
    feasible: bool
    # best (lowest fee) quote per freight plan, plus the packing it uses
    quotes: list[FreightQuote]
    # cheapest quote code for convenience
    cheapest_freight_plan_code: Optional[str]
    unpacked: list[InfeasibleItem]
    # all distinct packings considered (packing key -> summary), for UI compare
    packings: list[dict]
    warnings: list[str]
    validator_passed: bool
    validator_errors: list[str]
