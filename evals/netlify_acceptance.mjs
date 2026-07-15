// Run the AI-free hosted critical path against a deployed Netlify URL.

import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

import { sha256Json } from "../netlify/functions/_shared/civic-data.mjs";

const root = resolve(import.meta.dirname, "..");
const baseIndex = process.argv.indexOf("--base-url");
const outputIndex = process.argv.indexOf("--output");
const baseUrl = (baseIndex >= 0 ? process.argv[baseIndex + 1] : "https://shakti-seva-studio.netlify.app").replace(/\/$/, "");
const output = resolve(outputIndex >= 0 ? process.argv[outputIndex + 1] : resolve(root, "output/evals/netlify-acceptance.json"));

function requireValue(condition, message) {
  if (!condition) throw new Error(message);
}

const started = performance.now();
const healthResponse = await fetch(`${baseUrl}/api/health`);
const health = await healthResponse.json();
requireValue(healthResponse.ok, "health endpoint failed");
requireValue(health.runtime === "netlify-functions" && health.transport === "https", "unexpected hosted runtime");
requireValue(health.ai?.enabled === false && health.hermes === null, "hosted runtime did not prove the no-AI boundary");

const suggestionResponse = await fetch(`${baseUrl}/api/address-suggestions`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ q: "700 E 9th St" }),
});
const suggestionPayload = await suggestionResponse.json();
requireValue(suggestionResponse.ok, "address suggestions failed");
requireValue(suggestionPayload.suggestions?.[0]?.bin === "1004529", "lived address did not resolve first to BIN 1004529");
requireValue(suggestionResponse.headers.get("cache-control")?.includes("no-store"), "suggestion response was cacheable");

const refusedGet = await fetch(`${baseUrl}/api/address-suggestions?q=700%20E%209th%20St`);
requireValue(refusedGet.status === 405, "query-string autocomplete was not refused");

const caseResponse = await fetch(`${baseUrl}/api/case`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ type: "case", payload: { bin: "1004529" } }),
});
const result = await caseResponse.json();
requireValue(caseResponse.ok && result.type === "case", "hosted case construction failed");
requireValue(result.case?.building?.buildingid === "6533", "hosted case did not join HPD Building 6533");
requireValue(caseResponse.headers.get("cache-control")?.includes("no-store"), "case response was cacheable");
const sourceIds = result.case.sources.map((source) => source.dataset_id).sort();
requireValue(
  JSON.stringify(sourceIds) === JSON.stringify(["hcir-3275", "kj4p-ruqc", "wvxf-dwi5", "ygpa-z7cr"]),
  "hosted case did not contain all four City sources",
);
const packetText = JSON.stringify(result.case);
const privacyText = packetText
  .replaceAll("[UNIT REDACTED]", "")
  .replaceAll("[PRIVATE LOCATION REDACTED]", "");
const unitPatterns = [
  /\bAPT\.?\s*[A-Z0-9-]+\b/i,
  /\bUNIT\s*[#.]?\s*[A-Z0-9-]+\b/i,
  /LOCATED\s+AT\s+(?:APT|APARTMENT|UNIT)\b/i,
];
requireValue(!unitPatterns.some((pattern) => pattern.test(privacyText)), "hosted case exposed a unit identifier");
let previous = null;
for (const [index, event] of result.trace.entries()) {
  requireValue(event.sequence === index + 1, "hosted trace sequence failed");
  requireValue(event.previous_hash === previous, "hosted trace previous hash failed");
  const { event_hash: claimed, ...body } = event;
  requireValue(claimed === sha256Json(body), "hosted trace event hash failed");
  previous = claimed;
}
requireValue(result.trace[0]?.payload?.runtime === "netlify-functions", "hosted trace did not name its runtime");
requireValue(!result.trace.some((event) => event.kind.startsWith("hermes.") || event.kind.startsWith("model.")), "hosted trace contained a model event");

const report = {
  schema_version: "1.0",
  kind: "netlify_ai_free_acceptance",
  observed_at: new Date().toISOString(),
  base_url: baseUrl,
  passed: true,
  no_ai: {
    health_declared_disabled: true,
    hermes_absent: true,
    model_events: 0,
  },
  privacy: {
    suggestions_post_body: true,
    query_string_get_refused: true,
    suggestions_no_store: true,
    case_no_store: true,
    unit_scan_passed: true,
  },
  lived_address: {
    entered: "700 E 9th St",
    first_bin: suggestionPayload.suggestions[0].bin,
    hpd_building_id: result.case.building.buildingid,
    canonical_address: `${result.case.building.housenumber} ${result.case.building.streetname}, ${result.case.building.boro}`,
    complaints_shown: result.case.complaints.length,
    open_violations_shown: result.case.violations.length,
    aep_records: result.case.aep.length,
    route: result.case.next_step.code,
  },
  sources: result.case.sources.map((source) => ({ dataset_id: source.dataset_id, rows: source.row_count })),
  trace_events: result.trace.length,
  elapsed_ms: Math.round((performance.now() - started) * 100) / 100,
  limits: [
    "This is one dated lived-address journey against changing City services.",
    "This is not a concurrent load test or an advocate usability study.",
    "Netlify and City services process standard infrastructure metadata.",
  ],
};

await mkdir(resolve(output, ".."), { recursive: true });
await writeFile(output, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify(report, null, 2));
