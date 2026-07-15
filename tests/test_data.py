from pathlib import Path
from urllib.error import HTTPError

import pytest

from shakti_seva.data import (
    DATASETS,
    CaseService,
    DataError,
    QueryReceipt,
    SocrataClient,
    deterministic_route,
    normalize_street_name,
    normalize_text,
    treat_public_description,
)
from shakti_seva.trace import TraceLedger, sha256_json


class FakeClient:
    rows = {
        DATASETS["complaints"]: [
            {
                "complaint_id": "1",
                "building_id": "99",
                "major_category": "HEAT/HOT WATER",
                "complaint_status": "CLOSE",
                "apartment": "4A",
            }
        ],
        DATASETS["violations"]: [
            {
                "violationid": "2",
                "buildingid": "99",
                "class": "C",
                "violationstatus": "Open",
                "novdescription": "Provide adequate heat LOCATED AT APT 4A, 4th STORY, 2nd APARTMENT FROM NORTH",
                "apartment": "4A",
            }
        ],
        DATASETS["aep"]: [],
    }

    def query(self, dataset_id, fields, predicate, *, order=None, limit=25):
        rows = self.rows.get(dataset_id, [])
        receipt = QueryReceipt(
            dataset_id=dataset_id,
            fetched_at="2026-07-14T00:00:00Z",
            fields=fields,
            predicate_hash=sha256_json({"predicate": predicate}),
            row_count=len(rows),
            response_hash=sha256_json(rows),
        )
        return rows, receipt


class RecordingFakeClient(FakeClient):
    def __init__(self) -> None:
        self.calls = []

    def query(self, dataset_id, fields, predicate, *, order=None, limit=25):
        self.calls.append((dataset_id, fields, predicate))
        return super().query(dataset_id, fields, predicate, order=order, limit=limit)


def test_case_service_drops_apartment_and_routes_class_c(tmp_path: Path) -> None:
    ledger = TraceLedger(tmp_path)
    service = CaseService(FakeClient(), ledger)
    case = service.build_for_building(
        {"buildingid": "99", "boro": "QUEENS", "housenumber": "10", "streetname": "SAMPLE STREET", "apartment": "4A"}
    )

    assert case["next_step"]["code"] == "urgent_hpd_follow_up"
    assert "apartment" not in case["building"]
    assert "apartment" not in case["complaints"][0]
    assert "apartment" not in case["violations"][0]
    assert case["violations"][0]["novdescription"] == "Provide adequate heat [PRIVATE LOCATION REDACTED]"
    assert {source["dataset_id"] for source in case["sources"]} == {
        DATASETS["complaints"], DATASETS["violations"], DATASETS["aep"]
    }
    assert all(source["url"].startswith("https://data.cityofnewyork.us/d/") for source in case["sources"])
    assert [event["kind"] for event in ledger.events].count("query.completed") == 3


def test_route_does_not_treat_missing_records_as_repaired() -> None:
    route = deterministic_route({"complaints": [], "violations": [], "aep": []})
    assert route["code"] == "start_311"
    assert "No matching" in route["reason"]


def test_address_normalization_is_bounded() -> None:
    assert normalize_text("  sample   street ", field="street") == "SAMPLE STREET"
    assert normalize_street_name("Parsons Blvd") == "PARSONS BOULEVARD"
    assert normalize_street_name("31st Street") == "31ST STREET"
    with pytest.raises(DataError):
        normalize_text("street; DROP TABLE", field="street")


def test_building_search_can_span_all_boroughs(tmp_path: Path) -> None:
    client = RecordingFakeClient()
    service = CaseService(client, TraceLedger(tmp_path))
    service.resolve_building("", "900", "East 9th Street")
    predicate = client.calls[0][2]
    assert "upper(housenumber)='900'" in predicate
    assert "upper(streetname)='EAST 9TH STREET'" in predicate
    assert "upper(boro)" not in predicate


def test_building_search_can_use_geosearch_bin(tmp_path: Path) -> None:
    client = RecordingFakeClient()
    service = CaseService(client, TraceLedger(tmp_path))
    service.resolve_building_by_bin("1001026")
    assert client.calls[0][2] == "bin='1001026'"


def test_embedded_unit_identifiers_are_treated() -> None:
    assert treat_public_description("Repair sink AT APT. 6S") == "Repair sink AT [UNIT REDACTED]"
    assert treat_public_description("Repair sink located at apartment 12-B, second floor") == (
        "Repair sink [PRIVATE LOCATION REDACTED]"
    )


def test_socrata_retries_a_temporary_server_error(monkeypatch) -> None:
    calls = 0

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *unused):
            return False

        def read(self):
            return b"[]"

    def urlopen(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HTTPError(request.full_url, 500, "Server Error", {}, None)
        return Response()

    monkeypatch.setattr("shakti_seva.data.urllib.request.urlopen", urlopen)
    monkeypatch.setattr("shakti_seva.data.time.sleep", lambda unused: None)

    rows, receipt = SocrataClient().query(DATASETS["buildings"], ("buildingid",), "buildingid=1", limit=1)

    assert rows == []
    assert receipt.row_count == 0
    assert calls == 2
