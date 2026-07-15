import assert from "node:assert/strict";
import test from "node:test";

import {
  canonicalJson,
  deterministicRoute,
  getAddressSuggestions,
  normalizeStreetName,
  normalizeText,
  treatPublicDescription,
} from "../functions/_shared/civic-data.mjs";

test("unit: address and public-description transforms stay deterministic", () => {
  assert.equal(normalizeText("  sample   street ", "street"), "SAMPLE STREET");
  assert.equal(normalizeStreetName("Parsons Blvd"), "PARSONS BOULEVARD");
  assert.equal(
    treatPublicDescription("Repair sink LOCATED AT APT 4A, fourth floor"),
    "Repair sink [PRIVATE LOCATION REDACTED]",
  );
  assert.throws(() => normalizeText("street; DROP TABLE", "street"));
  assert.equal(canonicalJson({ z: 1, a: { y: 2, b: 3 } }), '{"a":{"b":3,"y":2},"z":1}');
});

test("unit: code selects the next step without AI", () => {
  const route = deterministicRoute({
    complaints: [],
    violations: [{ class: "C", violationstatus: "Open" }],
    aep: [],
  });
  assert.equal(route.code, "urgent_hpd_follow_up");
});

test("unit: GeoSearch fallback never swaps the house number", async () => {
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    const features = calls === 1 ? [] : [
      {
        properties: { label: "212 EAST 9 STREET, Brooklyn, NY, USA", housenumber: "212", street: "EAST 9 STREET", borough: "Brooklyn" },
        geometry: { coordinates: [-73.9, 40.6] },
      },
      {
        properties: {
          label: "900 EAST 9 STREET, Brooklyn, NY, USA", housenumber: "900", street: "EAST 9 STREET",
          borough: "Brooklyn", postalcode: "11230", addendum: { pad: { bin: "3000001" } },
        },
        geometry: { coordinates: [-73.9, 40.6] },
      },
    ];
    return new Response(JSON.stringify({ features }), { status: 200 });
  };
  const suggestions = await getAddressSuggestions("900 East 9th Street", fetchImpl);
  assert.deepEqual(suggestions.map((item) => item.house_number), ["900"]);
  assert.equal(suggestions[0].bin, "3000001");
});
