"""FastAPI application: catalog CRUD + solve endpoint + static frontend."""
from __future__ import annotations

import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .models import (
    BoxTypeIn, BoxTypeOut, FreightPlanIn, FreightPlanOut,
    SolveRequest, SolveResponse,
)
from .service import solve as run_solve

app = FastAPI(title="装箱运费规划器", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DIST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


# ---------------------------------------------------------------------------
# Catalog endpoints
# ---------------------------------------------------------------------------


@app.get("/api/box-types", response_model=list[BoxTypeOut])
def get_box_types() -> list[dict]:
    return db.list_boxes(active_only=False)


@app.post("/api/box-types", response_model=BoxTypeOut, status_code=201)
def create_box_type(data: BoxTypeIn) -> dict:
    try:
        return db.insert_box(data.model_dump())
    except Exception as exc:  # sqlite IntegrityError etc.
        raise HTTPException(status_code=400, detail=f"箱型保存失败: {exc}") from exc


@app.get("/api/freight-plans", response_model=list[FreightPlanOut])
def get_freight_plans() -> list[dict]:
    return db.list_plans(active_only=False)


@app.post("/api/freight-plans", response_model=FreightPlanOut, status_code=201)
def create_freight_plan(data: FreightPlanIn) -> dict:
    try:
        return db.insert_plan(data.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"运费方案保存失败: {exc}") from exc


# ---------------------------------------------------------------------------
# Solve
# ---------------------------------------------------------------------------


@app.post("/api/solve", response_model=SolveResponse)
def solve_endpoint(req: SolveRequest) -> dict:
    try:
        result = run_solve(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        db.save_run(
            json.dumps(req.model_dump(), ensure_ascii=False),
            json.dumps(result, ensure_ascii=False),
            ok=result["validator_passed"],
        )
    except Exception:
        pass  # logging failure must not break the response
    return result


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Static frontend (production build)
# ---------------------------------------------------------------------------

if os.path.isdir(DIST_DIR):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(DIST_DIR, "assets")),
        name="assets",
    )

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(os.path.join(DIST_DIR, "index.html"))

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        # never shadow /api routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        target = os.path.join(DIST_DIR, full_path)
        if os.path.isfile(target):
            return FileResponse(target)
        return FileResponse(os.path.join(DIST_DIR, "index.html"))
