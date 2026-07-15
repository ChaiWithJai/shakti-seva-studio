"""Check common forms of one reviewed address against live NYC GeoSearch."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from shakti_seva.server import geosearch_suggestions


ROOT = Path(__file__).resolve().parents[1]
LOCAL_REPORT = ROOT / "output" / "evals" / "live-address-variants.json"
PUBLIC_REPORT = ROOT / "evals" / "baseline" / "address-input-variants.json"
EXPECTED_BIN = "1004529"
VARIANTS = (
    ("abbreviated", "700 E 9th St"),
    ("full_city_state_zip", "700 East 9th Street, New York, NY 10009"),
    ("punctuated_with_borough", "700 E. 9th St., Manhattan"),
    ("city_record_style", "700 EAST 9 STREET"),
)


def run() -> dict:
    results: list[dict] = []
    for form, entered in VARIANTS:
        suggestions = geosearch_suggestions(entered)
        match = next((item for item in suggestions if item.get("bin") == EXPECTED_BIN), None)
        results.append(
            {
                "form": form,
                "entered": entered,
                "passed": match is not None,
                "matched_rank": suggestions.index(match) + 1 if match else None,
                "label": match.get("label") if match else None,
                "bin": match.get("bin") if match else None,
                "borough": match.get("borough") if match else None,
                "zip": match.get("zip") if match else None,
            }
        )
    return {
        "schema_version": "1.0",
        "kind": "live_geosearch_address_form_acceptance",
        "observed_at": datetime.now(UTC).date().isoformat(),
        "provider": "NYC GeoSearch",
        "expected_bin": EXPECTED_BIN,
        "passed": all(item["passed"] for item in results),
        "variants": results,
        "limits": [
            "This is a dated observation of a changing City service.",
            "It verifies four forms of one address, not all New York City addresses.",
            "Apartment suffix treatment is covered by private automated tests and is not published as lived-address evidence.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=LOCAL_REPORT)
    parser.add_argument("--publish", action="store_true", help="replace the reviewed public baseline")
    args = parser.parse_args()
    report = run()
    output = PUBLIC_REPORT if args.publish else args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
