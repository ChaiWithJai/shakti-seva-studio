"""Run a deterministic five borough smoke sample against live public data.

The public report contains rounded map points and aggregate trace results. Raw
case packets and hash chained traces stay under output/ and are not published.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shakti_seva.data import BUILDING_FIELDS, CaseService, DataError, SocrataClient
from shakti_seva.trace import TraceLedger, canonical_json, sha256_json


ROOT = Path(__file__).resolve().parents[1]
BUILDINGS_DATASET = "kj4p-ruqc"
ADDRESS_POINTS_DATASET = "uf93-f8nk"
BUILDING_POINTS_DATASET = "u9wf-3gbt"
BOUNDARIES_DATASET = "gthc-hcne"
BOROUGHS = ("BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "STATEN ISLAND")
RUN_DIR = ROOT / "output" / "five-borough"
TRACE_DIR = RUN_DIR / "traces"
LOCAL_REPORT = RUN_DIR / "five-borough.json"
PUBLIC_REPORT = ROOT / "evals" / "baseline" / "five-borough.json"
PUBLIC_MAP = ROOT / "docs" / "assets" / "five-borough-eval-map.svg"
USER_AGENT = "ShaktiSevaStudioFiveBoroughEval/0.1"
UNIT_PATTERNS = (
    re.compile(r"\bAPT\.?\s*[A-Z0-9-]+\b", re.IGNORECASE),
    re.compile(r"\bUNIT\s*[#.]?\s*(?!REDACTED\b)[A-Z0-9-]+\b", re.IGNORECASE),
    re.compile(r"LOCATED\s+AT\s+(?:APT|APARTMENT|UNIT)\b", re.IGNORECASE),
)


def fetch(dataset_id: str, params: dict[str, str], *, suffix: str = "json", timeout: float = 30) -> Any:
    query = urllib.parse.urlencode(params)
    url = f"https://data.cityofnewyork.us/resource/{dataset_id}.{suffix}?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except Exception as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"NYC Open Data request failed after four attempts: {last_error}")


def building_predicate(borough: str) -> str:
    escaped = borough.replace("'", "''")
    return (
        f"upper(boro)='{escaped}' AND recordstatus='Active' AND bin IS NOT NULL "
        "AND housenumber!='0' AND streetname!='0'"
    )


def select_buildings() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    receipts: dict[str, Any] = {}
    for borough in BOROUGHS:
        predicate = building_predicate(borough)
        count_rows = fetch(
            BUILDINGS_DATASET,
            {"$select": "count(*) as count", "$where": predicate},
        )
        count = int(count_rows[0]["count"])
        offsets = [round((count - 6) * index / 4) for index in range(5)]
        borough_rows: list[dict[str, Any]] = []
        window_hashes: list[str] = []
        for offset in offsets:
            rows = fetch(
                BUILDINGS_DATASET,
                {
                    "$select": ",".join(BUILDING_FIELDS),
                    "$where": predicate,
                    "$order": "buildingid ASC",
                    "$limit": "6",
                    "$offset": str(offset),
                },
            )
            borough_rows.extend(rows)
            window_hashes.append(sha256_json(rows))
        unique = {str(row["buildingid"]): row for row in borough_rows}
        if len(unique) != 30:
            raise RuntimeError(f"{borough} produced {len(unique)} unique samples instead of 30")
        selected.extend(unique.values())
        receipts[borough] = {
            "eligible_buildings": count,
            "offsets": offsets,
            "window_response_hashes": window_hashes,
        }
    return selected, receipts


def fetch_points(buildings: list[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    bins = sorted({str(row["bin"]) for row in buildings if str(row.get("bin", "")).isdigit()})
    points: dict[str, tuple[float, float]] = {}
    for start in range(0, len(bins), 35):
        chunk = bins[start : start + 35]
        predicate = "bin in (" + ",".join(chunk) + ")"
        rows = fetch(
            ADDRESS_POINTS_DATASET,
            {
                "$select": "bin,the_geom",
                "$where": predicate,
                "$order": "bin ASC",
                "$limit": "500",
            },
        )
        for row in rows:
            coordinates = row.get("the_geom", {}).get("coordinates", [])
            if len(coordinates) == 2 and str(row.get("bin", "")) not in points:
                points[str(row["bin"])] = (float(coordinates[0]), float(coordinates[1]))
    missing = [bin_value for bin_value in bins if bin_value not in points]
    for start in range(0, len(missing), 35):
        chunk = missing[start : start + 35]
        predicate = "bin in (" + ",".join(chunk) + ")"
        rows = fetch(
            BUILDING_POINTS_DATASET,
            {
                "$select": "bin,the_geom",
                "$where": predicate,
                "$order": "bin ASC",
                "$limit": "500",
            },
        )
        for row in rows:
            coordinates = row.get("the_geom", {}).get("coordinates", [])
            if len(coordinates) == 2 and str(row.get("bin", "")) not in points:
                points[str(row["bin"])] = (float(coordinates[0]), float(coordinates[1]))
    return points


def run_case(index: int, building: dict[str, Any], point: tuple[float, float] | None) -> dict[str, Any]:
    ledger = TraceLedger(TRACE_DIR)
    service = CaseService(SocrataClient(timeout=25), ledger)
    borough = str(building.get("boro", ""))
    building_id = str(building.get("buildingid", ""))
    sample_id = hashlib.sha256(f"{borough}:{building_id}".encode()).hexdigest()[:12]
    started = time.monotonic()
    try:
        case = service.build_for_building(building)
        case_text = canonical_json(case)
        redaction_applied = "[UNIT REDACTED]" in case_text or "[PRIVATE LOCATION REDACTED]" in case_text
        if any(pattern.search(case_text) for pattern in UNIT_PATTERNS):
            raise RuntimeError("curated case contains a unit identifier")
        valid, verify_message = TraceLedger.verify(ledger.path)
        if not valid:
            raise RuntimeError(verify_message)
        final_event = ledger.events[-1]
        normalization = next(event["payload"] for event in ledger.events if event["kind"] == "normalization.completed")
        return {
            "sample_id": sample_id,
            "borough": borough,
            "status": "pass",
            "route": case["next_step"]["code"],
            "trace_verified": True,
            "privacy_scan_passed": True,
            "redaction_applied": redaction_applied,
            "trace_events": len(ledger.events),
            "trace_final_hash": final_event["event_hash"],
            "complaints": normalization["complaints"],
            "open_violations": normalization["open_violations"],
            "packet_chars": normalization["packet_chars"],
            "truncated": any(case["truncated"].values()),
            "point": list(point) if point else None,
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
        }
    except (DataError, RuntimeError) as exc:
        return {
            "sample_id": sample_id,
            "borough": borough,
            "status": "fail",
            "error": str(exc),
            "trace_verified": False,
            "trace_events": len(ledger.events),
            "point": list(point) if point else None,
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
        }


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    passed = [sample for sample in samples if sample["status"] == "pass"]
    return {
        "sampled": len(samples),
        "passed": len(passed),
        "failed": len(samples) - len(passed),
        "traces_verified": sum(bool(sample.get("trace_verified")) for sample in samples),
        "privacy_scans_passed": sum(bool(sample.get("privacy_scan_passed")) for sample in samples),
        "cases_with_redaction": sum(bool(sample.get("redaction_applied")) for sample in samples),
        "map_points": sum(sample.get("point") is not None for sample in samples),
        "truncated_cases": sum(bool(sample.get("truncated")) for sample in passed),
        "route_counts": dict(sorted(Counter(str(sample["route"]) for sample in passed).items())),
        "borough_counts": dict(sorted(Counter(str(sample["borough"]) for sample in samples).items())),
        "packet_chars": {
            "minimum": min((int(sample["packet_chars"]) for sample in passed), default=0),
            "maximum": max((int(sample["packet_chars"]) for sample in passed), default=0),
            "mean": round(sum(int(sample["packet_chars"]) for sample in passed) / len(passed), 1) if passed else 0,
        },
    }


def public_sample(sample: dict[str, Any]) -> dict[str, Any]:
    result = {
        "sample_id": sample["sample_id"],
        "borough": sample["borough"],
        "status": sample["status"],
        "trace_verified": sample["trace_verified"],
        "privacy_scan_passed": sample.get("privacy_scan_passed", False),
        "redaction_applied": sample.get("redaction_applied", False),
        "trace_events": sample["trace_events"],
    }
    if sample.get("point"):
        result["point"] = [round(float(value), 3) for value in sample["point"]]
    if sample["status"] == "pass":
        result.update(
            route=sample["route"],
            truncated=sample["truncated"],
            trace_final_hash=sample["trace_final_hash"],
        )
    else:
        result["error"] = sample["error"]
    return result


def project(point: list[float], width: int = 820, height: int = 760) -> tuple[float, float]:
    west, east, south, north = -74.27, -73.67, 40.47, 40.93
    longitude, latitude = point
    x = 40 + (longitude - west) / (east - west) * (width - 80)
    mercator = math.log(math.tan(math.pi / 4 + math.radians(latitude) / 2))
    mercator_south = math.log(math.tan(math.pi / 4 + math.radians(south) / 2))
    mercator_north = math.log(math.tan(math.pi / 4 + math.radians(north) / 2))
    y = height - 40 - (mercator - mercator_south) / (mercator_north - mercator_south) * (height - 80)
    return x, y


def polygon_path(coordinates: list[Any]) -> str:
    commands: list[str] = []
    for ring in coordinates:
        for index, point in enumerate(ring):
            x, y = project(point)
            commands.append(("M" if index == 0 else "L") + f"{x:.1f},{y:.1f}")
        commands.append("Z")
    return " ".join(commands)


def render_map(report: dict[str, Any]) -> str:
    boundaries = fetch(BOUNDARIES_DATASET, {"$select": "boroname,the_geom", "$limit": "5"}, suffix="geojson")
    paths: list[str] = []
    for feature in boundaries.get("features", []):
        geometry = feature.get("geometry", {})
        polygons = geometry.get("coordinates", [])
        for polygon in polygons:
            paths.append(f'<path d="{polygon_path(polygon)}" fill="#efe2da" stroke="#b99582" stroke-width="1.2"/>')
    pins: list[str] = []
    for sample in report["samples"]:
        if not sample.get("point"):
            continue
        x, y = project(sample["point"])
        color = "#2f9d70" if sample["status"] == "pass" else "#c94262"
        pins.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.4" fill="{color}" stroke="#fff" stroke-width="1.4"/>')
    summary = report["summary"]
    route_lines = []
    labels = {
        "urgent_hpd_follow_up": "Open Class C route",
        "hpd_follow_up": "Open violation route",
        "track_complaint": "Complaint route",
        "start_311": "No matched record route",
    }
    for index, (route, count) in enumerate(summary["route_counts"].items()):
        route_lines.append(
            f'<text x="870" y="{470 + index * 42}" class="route"><tspan class="number">{count}</tspan> {labels.get(route, route)}</text>'
        )
    generated = report["generated_at"][:10]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="900" viewBox="0 0 1400 900">
<rect width="1400" height="900" fill="#faf6f2"/>
<style>
  text {{ font-family: Inter, Avenir Next, system-ui, sans-serif; fill: #251d1b; }}
  .eyebrow {{ font-size: 20px; font-weight: 700; letter-spacing: 3px; fill: #c94262; }}
  .title {{ font-size: 54px; font-weight: 800; letter-spacing: -2px; }}
  .body {{ font-size: 23px; fill: #795342; }}
  .metric {{ font-size: 50px; font-weight: 800; }}
  .label {{ font-size: 20px; fill: #795342; }}
  .route {{ font-size: 23px; }}
  .number {{ font-weight: 800; fill: #28664b; }}
</style>
<text x="62" y="58" class="eyebrow">FIVE BOROUGH LIVE DATA SMOKE EVAL</text>
<text x="62" y="122" class="title">150 building level cases. 30 per borough.</text>
<text x="62" y="163" class="body">Deterministic public data sample run {generated}. Pins are rounded to protect exact locations.</text>
<g transform="translate(20 100)">{''.join(paths)}{''.join(pins)}</g>
<rect x="835" y="215" width="505" height="580" rx="24" fill="#fff" stroke="#e4d5cd" stroke-width="2"/>
<text x="870" y="278" class="metric">{summary['passed']}/{summary['sampled']}</text>
<text x="870" y="312" class="label">live cases completed</text>
<text x="1135" y="278" class="metric">{summary['traces_verified']}</text>
<text x="1135" y="312" class="label">trace chains verified</text>
<text x="870" y="382" class="metric">{summary['map_points']}</text>
<text x="870" y="416" class="label">map points resolved</text>
<text x="870" y="458" class="eyebrow">WHAT THE CODE SELECTED</text>
{''.join(route_lines)}
<line x1="870" y1="675" x2="1305" y2="675" stroke="#e4d5cd" stroke-width="2"/>
<text x="870" y="718" class="body">This proves data path coverage.</text>
<text x="870" y="752" class="body">It does not prove advocate usability.</text>
<text x="870" y="786" class="body">Observed user sessions are the next loop.</text>
</svg>'''


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the five borough live data smoke evaluation")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--publish", action="store_true", help="Write the sanitized baseline and map used in the docs")
    parser.add_argument("--map-only", action="store_true", help="Refresh map points for the completed local report")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.workers <= 8:
        raise SystemExit("workers must be between 1 and 8")
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    buildings, sampling_receipts = select_buildings()
    points = fetch_points(buildings)
    if args.map_only:
        report = json.loads(LOCAL_REPORT.read_text(encoding="utf-8"))
        report["sources"]["building_points_fallback"] = BUILDING_POINTS_DATASET
        report["sampling"]["receipts"] = sampling_receipts
        point_by_sample = {
            hashlib.sha256(f"{building['boro']}:{building['buildingid']}".encode()).hexdigest()[:12]: points.get(str(building.get("bin", "")))
            for building in buildings
        }
        for sample in report["samples"]:
            point = point_by_sample.get(sample["sample_id"])
            sample["point"] = list(point) if point else None
        report["summary"] = summarize(report["samples"])
        LOCAL_REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if args.publish:
            public_report = {**report, "samples": [public_sample(sample) for sample in report["samples"]]}
            public_report["local_report_hash"] = sha256_json(report)
            PUBLIC_REPORT.write_text(json.dumps(public_report, indent=2) + "\n", encoding="utf-8")
            PUBLIC_MAP.write_text(render_map(public_report), encoding="utf-8")
        print(json.dumps(report["summary"], indent=2))
        return 0 if report["summary"]["map_points"] == 150 else 1
    samples: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(run_case, index, building, points.get(str(building.get("bin", "")))): index
            for index, building in enumerate(buildings)
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            sample = future.result()
            samples.append(sample)
            print(f"{completed:03d}/150 {sample['borough']}: {sample['status']}")
    samples.sort(key=lambda item: (BOROUGHS.index(item["borough"]), item["sample_id"]))
    report = {
        "schema_version": "1.0",
        "suite": "five_borough_live_smoke",
        "generated_at": datetime.now(UTC).isoformat(),
        "claim": "A deterministic smoke sample, not a representative sample or usability study.",
        "sources": {
            "buildings": BUILDINGS_DATASET,
            "address_points": ADDRESS_POINTS_DATASET,
            "building_points_fallback": BUILDING_POINTS_DATASET,
            "borough_boundaries": BOUNDARIES_DATASET,
        },
        "sampling": {
            "method": "Six active HPD buildings from each of five evenly spaced Building ID windows in each borough.",
            "per_borough": 30,
            "receipts": sampling_receipts,
        },
        "summary": summarize(samples),
        "samples": samples,
    }
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.publish:
        public_report = {**report, "samples": [public_sample(sample) for sample in samples]}
        public_report["local_report_hash"] = sha256_json(report)
        PUBLIC_REPORT.write_text(json.dumps(public_report, indent=2) + "\n", encoding="utf-8")
        PUBLIC_MAP.write_text(render_map(public_report), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"local report: {LOCAL_REPORT}")
    return 0 if report["summary"]["passed"] == 150 and report["summary"]["traces_verified"] == 150 else 1


if __name__ == "__main__":
    raise SystemExit(main())
