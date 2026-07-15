import assert from "node:assert/strict";
import test from "node:test";

import addressHandler from "../functions/address-suggestions.mjs";
import caseHandler from "../functions/case.mjs";
import { sha256Json } from "../functions/_shared/civic-data.mjs";

function cityFetch(url) {
  let rows = [];
  if (url.includes("kj4p-ruqc")) {
    rows = [{ buildingid: "99", boro: "MANHATTAN", housenumber: "140", streetname: "AVENUE C", zip: "10009", bin: "1004529" }];
  } else if (url.includes("ygpa-z7cr")) {
    rows = [{ complaint_id: "1", building_id: "99", major_category: "HEAT/HOT WATER", complaint_status: "CLOSE" }];
  } else if (url.includes("wvxf-dwi5")) {
    rows = [{ violationid: "2", buildingid: "99", class: "C", violationstatus: "Open", novdescription: "Repair sink LOCATED AT APT 4A" }];
  }
  return Promise.resolve(new Response(JSON.stringify(rows), { status: 200 }));
}

test("integration: Netlify HTTP boundary returns a treated, traced City case", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = cityFetch;
  try {
    const request = new Request("https://example.netlify.app/api/case", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ type: "case", payload: { bin: "1004529" } }),
    });
    const response = await caseHandler(request);
    const result = await response.json();
    assert.equal(response.status, 200);
    assert.equal(result.type, "case");
    assert.equal(result.case.building.bin, "1004529");
    assert.equal(result.case.next_step.code, "urgent_hpd_follow_up");
    assert.equal(result.case.violations[0].novdescription, "Repair sink [PRIVATE LOCATION REDACTED]");
    assert.deepEqual(result.case.sources.map((source) => source.dataset_id), [
      "kj4p-ruqc", "ygpa-z7cr", "wvxf-dwi5", "hcir-3275",
    ]);
    let previous = null;
    for (const [index, event] of result.trace.entries()) {
      assert.equal(event.sequence, index + 1);
      assert.equal(event.previous_hash, previous);
      const { event_hash: claimed, ...body } = event;
      assert.equal(claimed, sha256Json(body));
      previous = claimed;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("integration: function refuses oversized and non-POST requests", async () => {
  const getResponse = await caseHandler(new Request("https://example.netlify.app/api/case"));
  assert.equal(getResponse.status, 405);
  const largeResponse = await caseHandler(new Request("https://example.netlify.app/api/case", {
    method: "POST",
    headers: { "content-type": "application/json", "content-length": "5000" },
    body: "{}",
  }));
  assert.equal(largeResponse.status, 413);
});

test("integration: autocomplete accepts a POST body and refuses query-string GET", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ features: [{
    properties: {
      gid: "one", label: "700 EAST 9 STREET, New York, NY, USA", housenumber: "700",
      street: "EAST 9 STREET", borough: "Manhattan", postalcode: "10009", addendum: { pad: { bin: "1004529" } },
    },
    geometry: { coordinates: [-73.977823, 40.725071] },
  }] }), { status: 200 });
  try {
    const post = await addressHandler(new Request("https://example.netlify.app/api/address-suggestions", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ q: "700 E 9th St" }),
    }));
    const payload = await post.json();
    assert.equal(post.status, 200);
    assert.equal(payload.suggestions[0].bin, "1004529");
    const get = await addressHandler(new Request("https://example.netlify.app/api/address-suggestions?q=700%20E%209th%20St"));
    assert.equal(get.status, 405);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
