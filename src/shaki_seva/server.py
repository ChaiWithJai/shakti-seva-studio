"""Loopback web server and WebSocket interface."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .data import CaseService, DataError, SocrataClient
from .hermes import HermesError, HermesRuntime
from .trace import TraceLedger, sha256_json


ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"
FIXTURE = ROOT / "fixtures" / "synthetic-case.json"
TRACES = ROOT / "traces"


def create_app(
    *,
    root: Path = ROOT,
    traces: Path = TRACES,
    fixture: Path = FIXTURE,
    hermes: HermesRuntime | None = None,
) -> FastAPI:
    app = FastAPI(title="Shaki Seva Studio", docs_url="/api/docs", redoc_url=None)
    app.state.root = root
    app.state.traces = traces
    app.state.fixture = fixture
    app.state.hermes = hermes or HermesRuntime()
    static = root / "static"
    app.mount("/assets", StaticFiles(directory=static), name="assets")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(static / "index.html")

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "transport": "websocket",
            "loopback_only": True,
            "hermes": app.state.hermes.inspect().as_dict(),
        }

    @app.websocket("/ws")
    async def websocket_endpoint(socket: WebSocket) -> None:
        host = socket.headers.get("host", "")
        origin = socket.headers.get("origin")
        allowed_origins = {f"http://{host}", f"https://{host}"}
        if not host or origin not in allowed_origins:
            await socket.close(code=1008, reason="same-origin WebSocket required")
            return
        await socket.accept()
        await socket.send_json({"type": "connection", "status": "ready", "transport": "websocket"})
        cases: dict[str, tuple[dict[str, Any], TraceLedger]] = {}
        try:
            while True:
                request = await socket.receive_json()
                request_type = request.get("type")
                if request_type == "fixture":
                    ledger = TraceLedger(app.state.traces)
                    await socket.send_json({"type": "progress", "stage": "curating", "trace_id": ledger.trace_id})
                    service = CaseService(SocrataClient(), ledger)
                    case = service.build_from_fixture(app.state.fixture)
                    cases[ledger.trace_id] = (case, ledger)
                    await socket.send_json({"type": "case", "case": case, "trace": ledger.events})
                elif request_type == "case":
                    ledger = TraceLedger(app.state.traces)
                    payload = request.get("payload") or {}
                    ledger.append("case.requested", {"input_hash": sha256_json(payload), "fields": sorted(payload)})
                    await socket.send_json({"type": "progress", "stage": "resolving", "trace_id": ledger.trace_id})
                    service = CaseService(SocrataClient(), ledger)
                    buildings = await asyncio.to_thread(
                        service.resolve_building,
                        str(payload.get("borough", "")),
                        str(payload.get("house_number", "")),
                        str(payload.get("street_name", "")),
                    )
                    if len(buildings) != 1:
                        ledger.append("case.failed", {"reason": "building_candidate_count", "count": len(buildings)})
                        await socket.send_json(
                            {
                                "type": "candidates",
                                "candidates": buildings,
                                "trace_id": ledger.trace_id,
                                "message": "Confirm one building before records are joined.",
                                "trace": ledger.events,
                            }
                        )
                        continue
                    case = await asyncio.to_thread(service.build_for_building, buildings[0])
                    cases[ledger.trace_id] = (case, ledger)
                    await socket.send_json({"type": "case", "case": case, "trace": ledger.events})
                elif request_type == "hermes":
                    trace_id = str(request.get("trace_id", ""))
                    if trace_id not in cases:
                        await socket.send_json({"type": "error", "message": "Load a case before asking Hermes."})
                        continue
                    case, ledger = cases[trace_id]
                    await socket.send_json({"type": "progress", "stage": "hermes", "trace_id": trace_id})
                    explanation = await asyncio.to_thread(app.state.hermes.run_case, case, ledger, app.state.root)
                    await socket.send_json(
                        {"type": "hermes", "explanation": explanation, "trace_id": trace_id, "trace": ledger.events}
                    )
                else:
                    await socket.send_json({"type": "error", "message": "Unknown socket message type."})
        except WebSocketDisconnect:
            return
        except (DataError, HermesError, json.JSONDecodeError) as exc:
            await socket.send_json({"type": "error", "message": str(exc)})

    return app


app = create_app()
