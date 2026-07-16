"""Loopback web server and WebSocket interface."""

from __future__ import annotations

import asyncio
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .data import CaseService, DataError, SocrataClient
from .hermes import HermesError, HermesRuntime
from .trace import TraceLedger, sha256_json


ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"
TRACES = ROOT / "traces"
GEOSEARCH_AUTOCOMPLETE = "https://geosearch.planninglabs.nyc/v2/autocomplete"
GEOSEARCH_SEARCH = "https://geosearch.planninglabs.nyc/v2/search"


def _geosearch_features(endpoint: str, query: str) -> list[dict[str, Any]]:
    url = f"{endpoint}?{urllib.parse.urlencode({'text': query, 'size': 6})}"
    request = urllib.request.Request(url, headers={"User-Agent": "Shakti-Seva-Studio/0.1"})
    with urllib.request.urlopen(request, timeout=4) as response:  # noqa: S310 - fixed HTTPS endpoints
        payload = json.load(response)
    return list(payload.get("features", []))


def _treated_geosearch_suggestions(
    features: list[dict[str, Any]], *, exact_house_number: str = ""
) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for feature in features:
        properties = feature.get("properties") or {}
        pad = (properties.get("addendum") or {}).get("pad") or {}
        house_number = str(properties.get("housenumber") or "")
        if exact_house_number and house_number.upper() != exact_house_number.upper():
            continue
        if not all((house_number, properties.get("street"), properties.get("borough"))):
            continue
        key = (str(pad.get("bin") or ""), str(properties.get("label") or ""))
        if key in seen:
            continue
        seen.add(key)
        coordinates = (feature.get("geometry") or {}).get("coordinates") or []
        suggestions.append(
            {
                "id": str(properties.get("gid") or properties.get("id") or ""),
                "label": str(properties.get("label") or "").removesuffix(", USA"),
                "borough": str(properties.get("borough") or ""),
                "house_number": house_number,
                "street_name": str(properties.get("street") or ""),
                "zip": str(properties.get("postalcode") or ""),
                "bin": str(pad.get("bin") or ""),
                "coordinates": coordinates[:2],
            }
        )
    return suggestions[:5]


def geosearch_suggestions(query: str) -> list[dict[str, Any]]:
    """Return a small, treated set of NYC GeoSearch address suggestions."""
    cleaned = " ".join(query.strip().split())[:100]
    cleaned = re.sub(r"(?:,|\s)\s*(?:APT(?:ARTMENT)?|UNIT)\.?\s*#?\s*[A-Z0-9-]+\b", "", cleaned, flags=re.I)
    if len(cleaned) < 3:
        return []
    autocomplete = _treated_geosearch_suggestions(_geosearch_features(GEOSEARCH_AUTOCOMPLETE, cleaned))
    if autocomplete:
        return autocomplete

    # GeoSearch autocomplete occasionally returns no features for a complete
    # address that its full search endpoint understands. The search endpoint
    # may also offer nearby house numbers, so only keep exact house-number
    # matches in this fallback rather than silently changing the building.
    house_match = re.match(r"^([0-9]+(?:-[0-9]+)?[A-Z]?)\b", cleaned, flags=re.I)
    if not house_match:
        return []
    return _treated_geosearch_suggestions(
        _geosearch_features(GEOSEARCH_SEARCH, cleaned), exact_house_number=house_match.group(1)
    )


def create_app(
    *,
    root: Path = ROOT,
    traces: Path = TRACES,
    hermes: HermesRuntime | None = None,
    client_factory: Callable[[], SocrataClient] = SocrataClient,
) -> FastAPI:
    app = FastAPI(title="Shakti Seva Studio", docs_url="/api/docs", redoc_url=None)
    app.state.root = root
    app.state.traces = traces
    app.state.hermes = hermes or HermesRuntime()
    app.state.client_factory = client_factory
    static = root / "static"
    app.mount("/assets", StaticFiles(directory=static), name="assets")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(static / "index.html")

    @app.get("/learn.html")
    async def learn() -> FileResponse:
        return FileResponse(static / "learn.html")

    @app.get("/guidance.html")
    async def guidance() -> FileResponse:
        return FileResponse(static / "guidance.html")

    @app.get("/api/live")
    async def live() -> dict[str, Any]:
        """Answer frequent process liveness probes without starting Hermes."""
        return {
            "status": "ok",
            "check": "liveness",
            "loopback_only": True,
        }

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "check": "readiness",
            "transport": "websocket",
            "loopback_only": True,
            "hermes": app.state.hermes.inspect().as_dict(),
        }

    @app.get("/api/address-suggestions")
    async def address_suggestions(q: str = "") -> dict[str, Any]:
        try:
            suggestions = await asyncio.to_thread(geosearch_suggestions, q)
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError):
            suggestions = []
        return {"suggestions": suggestions, "provider": "NYC GeoSearch"}

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
        pending: dict[str, tuple[list[dict[str, Any]], TraceLedger]] = {}
        try:
            while True:
                request = await socket.receive_json()
                request_type = request.get("type")
                if request_type == "ping":
                    await socket.send_json({"type": "pong"})
                elif request_type == "case":
                    ledger = TraceLedger(app.state.traces)
                    payload = request.get("payload") or {}
                    ledger.append("case.requested", {"input_hash": sha256_json(payload), "fields": sorted(payload)})
                    await socket.send_json({"type": "progress", "stage": "resolving", "trace_id": ledger.trace_id})
                    service = CaseService(app.state.client_factory(), ledger)
                    try:
                        if payload.get("bin"):
                            buildings = await asyncio.to_thread(service.resolve_building_by_bin, str(payload["bin"]))
                        else:
                            buildings = await asyncio.to_thread(
                                service.resolve_building,
                                str(payload.get("borough", "")),
                                str(payload.get("house_number", "")),
                                str(payload.get("street_name", "")),
                            )
                    except DataError:
                        ledger.append("case.failed", {"reason": "address_not_understood"})
                        await socket.send_json(
                            {
                                "type": "error",
                                "message": "We could not read that building address. Edit it and try again; borough and ZIP are optional.",
                            }
                        )
                        continue
                    if len(buildings) != 1:
                        ledger.append("building.candidates", {"count": len(buildings)})
                        pending[ledger.trace_id] = (buildings, ledger)
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
                elif request_type == "confirm":
                    trace_id = str(request.get("trace_id", ""))
                    building_id = str(request.get("building_id", ""))
                    if trace_id not in pending:
                        await socket.send_json({"type": "error", "message": "Search for the address again."})
                        continue
                    buildings, ledger = pending[trace_id]
                    building = next(
                        (item for item in buildings if str(item.get("buildingid", "")) == building_id),
                        None,
                    )
                    if building is None:
                        ledger.append("case.failed", {"reason": "invalid_building_confirmation"})
                        await socket.send_json({"type": "error", "message": "Choose a building from the search results."})
                        continue
                    ledger.append("building.confirmed", {"building_id_hash": sha256_json({"buildingid": building_id})})
                    await socket.send_json({"type": "progress", "stage": "building", "trace_id": trace_id})
                    service = CaseService(app.state.client_factory(), ledger)
                    case = await asyncio.to_thread(service.build_for_building, building)
                    cases[trace_id] = (case, ledger)
                    pending.pop(trace_id, None)
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
