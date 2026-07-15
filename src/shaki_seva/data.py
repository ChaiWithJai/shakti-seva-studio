"""Bounded NYC Open Data access and deterministic case construction."""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .trace import TraceLedger, canonical_json, sha256_json


DATASETS = {
    "buildings": "kj4p-ruqc",
    "complaints": "ygpa-z7cr",
    "violations": "wvxf-dwi5",
    "aep": "hcir-3275",
}
DATASET_NAMES = {
    "kj4p-ruqc": "HPD Buildings",
    "ygpa-z7cr": "HPD Complaints and Problems",
    "wvxf-dwi5": "Housing Maintenance Code Violations",
    "hcir-3275": "Alternative Enforcement Program Buildings",
}

BOROUGHS = {"BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "STATEN ISLAND"}
STREET_SUFFIXES = {
    "AVE": "AVENUE",
    "BLVD": "BOULEVARD",
    "CT": "COURT",
    "DR": "DRIVE",
    "HWY": "HIGHWAY",
    "LN": "LANE",
    "PKWY": "PARKWAY",
    "PL": "PLACE",
    "RD": "ROAD",
    "ST": "STREET",
    "TER": "TERRACE",
}

BUILDING_FIELDS = ("buildingid", "boro", "housenumber", "streetname", "zip", "bin", "block", "lot")
COMPLAINT_FIELDS = (
    "received_date",
    "complaint_id",
    "building_id",
    "major_category",
    "minor_category",
    "complaint_status",
    "problem_status",
    "problem_status_date",
    "status_description",
    "unique_key",
)
VIOLATION_FIELDS = (
    "violationid",
    "buildingid",
    "class",
    "inspectiondate",
    "novdescription",
    "currentstatus",
    "currentstatusdate",
    "violationstatus",
    "originalcorrectbydate",
)
AEP_FIELDS = ("building_id", "current_status", "aep_round", "discharge_date")
DESCRIPTION_FIELDS = {"novdescription", "status_description"}


class DataError(RuntimeError):
    pass


@dataclass(frozen=True)
class QueryReceipt:
    dataset_id: str
    fetched_at: str
    fields: tuple[str, ...]
    predicate_hash: str
    row_count: int
    response_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "fetched_at": self.fetched_at,
            "fields": list(self.fields),
            "predicate_hash": self.predicate_hash,
            "row_count": self.row_count,
            "response_hash": self.response_hash,
        }


class SocrataClient:
    base_url = "https://data.cityofnewyork.us/resource"

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    def query(
        self,
        dataset_id: str,
        fields: tuple[str, ...],
        predicate: str,
        *,
        order: str | None = None,
        limit: int = 25,
    ) -> tuple[list[dict[str, Any]], QueryReceipt]:
        if dataset_id not in DATASETS.values():
            raise DataError("dataset is not allowlisted")
        if not 1 <= limit <= 50:
            raise DataError("query limit must be between 1 and 50")
        params = {"$select": ",".join(fields), "$where": predicate, "$limit": str(limit)}
        if order:
            params["$order"] = order
        url = f"{self.base_url}/{dataset_id}.json?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"User-Agent": "ShakiSevaStudio/0.1"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read()
        except Exception as exc:  # urllib raises several transport-specific errors
            raise DataError(f"NYC Open Data request failed: {exc}") from exc
        try:
            rows = json.loads(body)
        except json.JSONDecodeError as exc:
            raise DataError("NYC Open Data returned invalid JSON") from exc
        if not isinstance(rows, list):
            raise DataError("NYC Open Data returned an unexpected payload")
        receipt = QueryReceipt(
            dataset_id=dataset_id,
            fetched_at=datetime.now(UTC).isoformat(),
            fields=fields,
            predicate_hash=sha256_json({"predicate": predicate}),
            row_count=len(rows),
            response_hash=sha256_json(rows),
        )
        return rows, receipt


def normalize_text(value: str, *, field: str, max_length: int = 80) -> str:
    normalized = " ".join(value.strip().upper().split())
    if not normalized or len(normalized) > max_length:
        raise DataError(f"{field} is empty or too long")
    if not re.fullmatch(r"[A-Z0-9 .'-]+", normalized):
        raise DataError(f"{field} contains unsupported characters")
    return normalized


def treat_public_description(value: str) -> str:
    """Remove unit-location details embedded in otherwise public descriptions."""
    cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", value)
    cleaned = re.sub(
        r"\s+LOCATED\s+AT\s+(?:APT|APARTMENT|UNIT)\b.*$",
        " [PRIVATE LOCATION REDACTED]",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:APT|APARTMENT|UNIT)\s*[#.]?\s*[A-Z0-9-]+\b",
        "[UNIT REDACTED]",
        cleaned,
        flags=re.IGNORECASE,
    )
    return " ".join(cleaned.split())


def keep_fields(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    kept: dict[str, Any] = {}
    for field in fields:
        value = row.get(field)
        if value in (None, ""):
            continue
        kept[field] = treat_public_description(str(value)) if field in DESCRIPTION_FIELDS else value
    return kept


def normalize_street_name(value: str) -> str:
    normalized = normalize_text(value, field="street name")
    parts = normalized.split()
    if parts and parts[-1] in STREET_SUFFIXES:
        parts[-1] = STREET_SUFFIXES[parts[-1]]
    return " ".join(parts)


def deterministic_route(case: dict[str, Any]) -> dict[str, str]:
    open_violations = [item for item in case["violations"] if str(item.get("violationstatus", "")).upper() == "OPEN"]
    immediately_hazardous = [item for item in open_violations if str(item.get("class", "")).upper() == "C"]
    if immediately_hazardous:
        return {
            "code": "urgent_hpd_follow_up",
            "label": "Follow up with HPD about the open Class C violation",
            "reason": "The public record shows at least one open immediately hazardous violation.",
        }
    if open_violations:
        return {
            "code": "hpd_follow_up",
            "label": "Follow up with HPD about the open violation",
            "reason": "The public record shows at least one open housing violation.",
        }
    if case["complaints"]:
        return {
            "code": "track_complaint",
            "label": "Check the complaint status with 311 or HPD",
            "reason": "A complaint is present, but this packet does not show an open violation.",
        }
    return {
        "code": "start_311",
        "label": "Start with an official 311 housing complaint",
        "reason": "No matching complaint or violation appears in the selected public records.",
    }


class CaseService:
    def __init__(self, client: SocrataClient, trace: TraceLedger) -> None:
        self.client = client
        self.trace = trace
        self.receipts: list[QueryReceipt] = []

    def _query(self, name: str, fields: tuple[str, ...], predicate: str, **kwargs: Any) -> list[dict[str, Any]]:
        dataset_id = DATASETS[name]
        self.trace.append("query.started", {"dataset_id": dataset_id, "predicate_hash": sha256_json({"predicate": predicate})})
        started = time.monotonic()
        rows, receipt = self.client.query(dataset_id, fields, predicate, **kwargs)
        self.receipts.append(receipt)
        self.trace.append(
            "query.completed",
            {**receipt.as_dict(), "duration_ms": round((time.monotonic() - started) * 1000, 2)},
        )
        return [keep_fields(row, fields) for row in rows]

    def resolve_building(self, borough: str, house_number: str, street_name: str) -> list[dict[str, Any]]:
        borough = normalize_text(borough, field="borough")
        if borough not in BOROUGHS:
            raise DataError("borough is not recognized")
        house_number = normalize_text(house_number, field="house number", max_length=12)
        street_name = normalize_street_name(street_name)
        escaped_house = house_number.replace("'", "''")
        escaped_street = street_name.replace("'", "''")
        escaped_borough = borough.replace("'", "''")
        predicate = (
            f"upper(boro)='{escaped_borough}' AND upper(housenumber)='{escaped_house}' "
            f"AND upper(streetname)='{escaped_street}'"
        )
        return self._query("buildings", BUILDING_FIELDS, predicate, limit=10)

    def build_for_building(self, building: dict[str, Any]) -> dict[str, Any]:
        building_id = str(building.get("buildingid", ""))
        if not building_id.isdigit():
            raise DataError("building record has no valid HPD Building ID")
        self.trace.append("case.started", {"building_id": building_id})
        complaint_rows = self._query(
            "complaints",
            COMPLAINT_FIELDS,
            f"building_id={building_id}",
            order="received_date DESC",
            limit=26,
        )
        violation_rows = self._query(
            "violations",
            VIOLATION_FIELDS,
            f"buildingid={building_id} AND violationstatus='Open'",
            order="inspectiondate DESC",
            limit=26,
        )
        complaints = complaint_rows[:25]
        violations = violation_rows[:25]
        aep = self._query("aep", AEP_FIELDS, f"building_id={building_id}", order="aep_round DESC", limit=10)
        case = {
            "schema_version": "1.0",
            "building": keep_fields(building, BUILDING_FIELDS),
            "complaints": complaints,
            "violations": violations,
            "aep": aep,
            "record_limits": {"complaints": 25, "open_violations": 25, "aep": 10},
            "truncated": {"complaints": len(complaint_rows) > 25, "open_violations": len(violation_rows) > 25},
            "sources": [{"name": DATASET_NAMES[receipt.dataset_id], **receipt.as_dict()} for receipt in self.receipts],
        }
        case["next_step"] = deterministic_route(case)
        packet_chars = len(canonical_json(case))
        if packet_chars > 40_000:
            self.trace.append("case.failed", {"reason": "packet_size", "packet_chars": packet_chars, "limit": 40_000})
            raise DataError("curated case packet exceeds the 40,000 character governance limit")
        self.trace.append(
            "normalization.completed",
            {
                "complaints": len(complaints),
                "open_violations": len(violations),
                "aep_records": len(aep),
                "packet_chars": packet_chars,
                "truncated": case["truncated"],
            },
        )
        self.trace.append("routing.completed", case["next_step"])
        self.trace.append("case.completed", {"case_hash": sha256_json(case)})
        case["trace_id"] = self.trace.trace_id
        return case

    def build_from_fixture(self, fixture_path: Path) -> dict[str, Any]:
        self.trace.append("case.started", {"mode": "synthetic_fixture"})
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        case = {
            "schema_version": "1.0",
            "building": keep_fields(raw["building"], BUILDING_FIELDS),
            "complaints": [keep_fields(row, COMPLAINT_FIELDS) for row in raw.get("complaints", [])],
            "violations": [keep_fields(row, VIOLATION_FIELDS) for row in raw.get("violations", [])],
            "aep": [keep_fields(row, AEP_FIELDS) for row in raw.get("aep", [])],
            "sources": raw["sources"],
            "fixture": True,
        }
        case["next_step"] = deterministic_route(case)
        packet_chars = len(canonical_json(case))
        if packet_chars > 40_000:
            self.trace.append("case.failed", {"reason": "packet_size", "packet_chars": packet_chars, "limit": 40_000})
            raise DataError("curated case packet exceeds the 40,000 character governance limit")
        self.trace.append(
            "normalization.completed",
            {
                "mode": "synthetic_fixture",
                "complaints": len(case["complaints"]),
                "open_violations": len(case["violations"]),
                "packet_chars": packet_chars,
            },
        )
        self.trace.append("routing.completed", case["next_step"])
        self.trace.append("case.completed", {"case_hash": sha256_json(case)})
        case["trace_id"] = self.trace.trace_id
        return case
