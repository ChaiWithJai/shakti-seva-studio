import { createHash, randomUUID } from "node:crypto";

export const DATASETS = {
  buildings: "kj4p-ruqc",
  complaints: "ygpa-z7cr",
  violations: "wvxf-dwi5",
  aep: "hcir-3275",
};

const DATASET_NAMES = {
  "kj4p-ruqc": "HPD Buildings",
  "ygpa-z7cr": "HPD Complaints and Problems",
  "wvxf-dwi5": "Housing Maintenance Code Violations",
  "hcir-3275": "Alternative Enforcement Program Buildings",
};

const DATASET_URLS = Object.fromEntries(
  Object.keys(DATASET_NAMES).map((id) => [id, `https://data.cityofnewyork.us/d/${id}`]),
);
const SOCRATA_BASE = "https://data.cityofnewyork.us/resource";
const GEOSEARCH_AUTOCOMPLETE = "https://geosearch.planninglabs.nyc/v2/autocomplete";
const GEOSEARCH_SEARCH = "https://geosearch.planninglabs.nyc/v2/search";
const BOROUGHS = new Set(["BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "STATEN ISLAND"]);
const STREET_SUFFIXES = {
  AVE: "AVENUE", BLVD: "BOULEVARD", CT: "COURT", DR: "DRIVE", HWY: "HIGHWAY",
  LN: "LANE", PKWY: "PARKWAY", PL: "PLACE", RD: "ROAD", ST: "STREET", TER: "TERRACE",
};

const BUILDING_FIELDS = ["buildingid", "boro", "housenumber", "streetname", "zip", "bin", "block", "lot"];
const COMPLAINT_FIELDS = [
  "received_date", "complaint_id", "building_id", "major_category", "minor_category",
  "complaint_status", "problem_status", "problem_status_date", "status_description", "unique_key",
];
const VIOLATION_FIELDS = [
  "violationid", "buildingid", "class", "inspectiondate", "novdescription", "currentstatus",
  "currentstatusdate", "violationstatus", "originalcorrectbydate",
];
const AEP_FIELDS = ["building_id", "current_status", "aep_round", "discharge_date"];
const DESCRIPTION_FIELDS = new Set(["novdescription", "status_description"]);

export class CivicDataError extends Error {
  constructor(message, status = 400) {
    super(message);
    this.status = status;
  }
}

function sortValue(value) {
  if (Array.isArray(value)) return value.map(sortValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, sortValue(value[key])]));
  }
  return value;
}

export function canonicalJson(value) {
  return JSON.stringify(sortValue(value));
}

export function sha256Json(value) {
  return createHash("sha256").update(canonicalJson(value)).digest("hex");
}

export class TraceLedger {
  constructor(traceId = randomUUID()) {
    this.traceId = traceId;
    this.events = [];
    this.previousHash = null;
  }

  append(kind, payload = {}) {
    const event = {
      trace_id: this.traceId,
      sequence: this.events.length + 1,
      timestamp: new Date().toISOString(),
      kind,
      payload,
      previous_hash: this.previousHash,
    };
    event.event_hash = sha256Json(event);
    this.previousHash = event.event_hash;
    this.events.push(event);
    return event;
  }
}

export function normalizeText(value, field, maxLength = 80) {
  const normalized = String(value || "").trim().toUpperCase().replace(/\s+/g, " ");
  if (!normalized || normalized.length > maxLength) throw new CivicDataError(`${field} is empty or too long`);
  if (!/^[A-Z0-9 .'-]+$/.test(normalized)) throw new CivicDataError(`${field} contains unsupported characters`);
  return normalized;
}

export function normalizeStreetName(value) {
  const parts = normalizeText(value, "street name").split(" ");
  const suffix = parts.at(-1);
  if (STREET_SUFFIXES[suffix]) parts[parts.length - 1] = STREET_SUFFIXES[suffix];
  return parts.join(" ");
}

export function treatPublicDescription(value) {
  return String(value || "")
    .replace(/[\x00-\x1f\x7f]/g, " ")
    .replace(/\s+LOCATED\s+AT\s+(?:APT|APARTMENT|UNIT)\b.*$/i, " [PRIVATE LOCATION REDACTED]")
    .replace(/\b(?:APT|APARTMENT|UNIT)\s*[#.]?\s*[A-Z0-9-]+\b/gi, "[UNIT REDACTED]")
    .replace(/\s+/g, " ")
    .trim();
}

function keepFields(row, fields) {
  const kept = {};
  for (const field of fields) {
    const value = row?.[field];
    if (value === undefined || value === null || value === "") continue;
    kept[field] = DESCRIPTION_FIELDS.has(field) ? treatPublicDescription(value) : value;
  }
  return kept;
}

function escapeSocrata(value) {
  return String(value).replaceAll("'", "''");
}

async function fetchWithRetry(url, { fetchImpl = fetch, attempts = 3, timeoutMs = 12_000 } = {}) {
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetchImpl(url, {
        headers: { accept: "application/json", "accept-encoding": "identity" },
        signal: AbortSignal.timeout(timeoutMs),
      });
      if (!response.ok) {
        const retryable = response.status === 429 || response.status >= 500;
        if (!retryable) throw new CivicDataError("A City data request was rejected.", 502);
        throw new Error(`temporary City response ${response.status}`);
      }
      const payload = await response.json();
      return payload;
    } catch (error) {
      lastError = error;
      if (error instanceof CivicDataError || attempt === attempts - 1) break;
      await new Promise((resolve) => setTimeout(resolve, 250 * (attempt + 1)));
    }
  }
  if (lastError instanceof CivicDataError) throw lastError;
  throw new CivicDataError("NYC public data is temporarily unavailable. Try again shortly.", 503);
}

async function queryDataset(name, fields, predicate, options, ledger, fetchImpl) {
  const datasetId = DATASETS[name];
  const limit = options?.limit ?? 25;
  if (!datasetId || limit < 1 || limit > 50) throw new CivicDataError("The public data query is outside the allowed boundary.");
  const query = new URLSearchParams({
    "$select": fields.join(","),
    "$where": predicate,
    "$limit": String(limit),
  });
  if (options?.order) query.set("$order", options.order);
  ledger.append("query.started", { dataset_id: datasetId, predicate_hash: sha256Json({ predicate }) });
  const started = performance.now();
  const rows = await fetchWithRetry(`${SOCRATA_BASE}/${datasetId}.json?${query}`, { fetchImpl });
  if (!Array.isArray(rows)) throw new CivicDataError("NYC public data returned an unexpected response.", 502);
  const receipt = {
    dataset_id: datasetId,
    fetched_at: new Date().toISOString(),
    fields,
    predicate_hash: sha256Json({ predicate }),
    row_count: rows.length,
    response_hash: sha256Json(rows),
  };
  ledger.append("query.completed", { ...receipt, duration_ms: Math.round((performance.now() - started) * 100) / 100 });
  return { rows: rows.map((row) => keepFields(row, fields)), receipt };
}

export function deterministicRoute(casePacket) {
  const open = casePacket.violations.filter((item) => String(item.violationstatus || "").toUpperCase() === "OPEN");
  if (open.some((item) => String(item.class || "").toUpperCase() === "C")) {
    return {
      code: "urgent_hpd_follow_up",
      label: "Follow up with HPD about the open Class C violation",
      reason: "The public record shows at least one open immediately hazardous violation.",
    };
  }
  if (open.length) {
    return {
      code: "hpd_follow_up",
      label: "Follow up with HPD about the open violation",
      reason: "The public record shows at least one open housing violation.",
    };
  }
  if (casePacket.complaints.length) {
    return {
      code: "track_complaint",
      label: "Check the complaint status with 311 or HPD",
      reason: "A complaint is present, but this packet does not show an open violation.",
    };
  }
  return {
    code: "start_311",
    label: "Start with an official 311 housing complaint",
    reason: "No matching complaint or violation appears in the selected public records.",
  };
}

async function resolveBuildings(payload, ledger, fetchImpl) {
  if (payload.bin) {
    const bin = normalizeText(payload.bin, "BIN", 12);
    if (!/^\d+$/.test(bin)) throw new CivicDataError("BIN is not recognized");
    return queryDataset("buildings", BUILDING_FIELDS, `bin='${bin}'`, { limit: 10 }, ledger, fetchImpl);
  }
  const borough = String(payload.borough || "").trim() ? normalizeText(payload.borough, "borough") : "";
  if (borough && !BOROUGHS.has(borough)) throw new CivicDataError("borough is not recognized");
  const house = normalizeText(payload.house_number, "house number", 12);
  const street = normalizeStreetName(payload.street_name);
  let predicate = `upper(housenumber)='${escapeSocrata(house)}' AND upper(streetname)='${escapeSocrata(street)}'`;
  if (borough) predicate = `upper(boro)='${escapeSocrata(borough)}' AND ${predicate}`;
  return queryDataset("buildings", BUILDING_FIELDS, predicate, { limit: 10 }, ledger, fetchImpl);
}

async function resolveBuildingId(buildingId, ledger, fetchImpl) {
  const normalized = normalizeText(buildingId, "HPD Building ID", 16);
  if (!/^\d+$/.test(normalized)) throw new CivicDataError("HPD Building ID is not recognized");
  return queryDataset("buildings", BUILDING_FIELDS, `buildingid='${normalized}'`, { limit: 1 }, ledger, fetchImpl);
}

async function buildCase(building, ledger, receipts, fetchImpl) {
  const buildingId = String(building.buildingid || "");
  if (!/^\d+$/.test(buildingId)) throw new CivicDataError("The building record has no valid HPD Building ID.", 502);
  ledger.append("case.started", { building_id: buildingId });
  const complaintsResult = await queryDataset(
    "complaints", COMPLAINT_FIELDS, `building_id=${buildingId}`,
    { order: "received_date DESC", limit: 26 }, ledger, fetchImpl,
  );
  const violationsResult = await queryDataset(
    "violations", VIOLATION_FIELDS, `buildingid=${buildingId} AND violationstatus='Open'`,
    { order: "inspectiondate DESC", limit: 26 }, ledger, fetchImpl,
  );
  const aepResult = await queryDataset(
    "aep", AEP_FIELDS, `building_id=${buildingId}`,
    { order: "aep_round DESC", limit: 10 }, ledger, fetchImpl,
  );
  const allReceipts = [...receipts, complaintsResult.receipt, violationsResult.receipt, aepResult.receipt];
  const casePacket = {
    schema_version: "1.0",
    building: keepFields(building, BUILDING_FIELDS),
    complaints: complaintsResult.rows.slice(0, 25),
    violations: violationsResult.rows.slice(0, 25),
    aep: aepResult.rows,
    record_limits: { complaints: 25, open_violations: 25, aep: 10 },
    truncated: {
      complaints: complaintsResult.rows.length > 25,
      open_violations: violationsResult.rows.length > 25,
    },
    sources: allReceipts.map((receipt) => ({
      name: DATASET_NAMES[receipt.dataset_id],
      url: DATASET_URLS[receipt.dataset_id],
      ...receipt,
    })),
  };
  casePacket.next_step = deterministicRoute(casePacket);
  const packetChars = canonicalJson(casePacket).length;
  if (packetChars > 40_000) throw new CivicDataError("The treated case exceeds the public packet limit.", 502);
  ledger.append("normalization.completed", {
    complaints: casePacket.complaints.length,
    open_violations: casePacket.violations.length,
    aep_records: casePacket.aep.length,
    packet_chars: packetChars,
    truncated: casePacket.truncated,
  });
  ledger.append("routing.completed", casePacket.next_step);
  ledger.append("case.completed", { case_hash: sha256Json(casePacket) });
  casePacket.trace_id = ledger.traceId;
  return casePacket;
}

export async function handleCasePayload(body, fetchImpl = fetch) {
  if (!body || typeof body !== "object") throw new CivicDataError("Send one building search.");
  const ledger = new TraceLedger();
  const type = body.type === "confirm" ? "confirm" : "case";
  ledger.append("case.requested", {
    input_hash: sha256Json(type === "confirm" ? { building_id: body.building_id } : (body.payload || {})),
    fields: type === "confirm" ? ["building_id"] : Object.keys(body.payload || {}).sort(),
    runtime: "netlify-functions",
  });
  const buildingResult = type === "confirm"
    ? await resolveBuildingId(body.building_id, ledger, fetchImpl)
    : await resolveBuildings(body.payload || {}, ledger, fetchImpl);
  if (buildingResult.rows.length !== 1) {
    ledger.append("building.candidates", { count: buildingResult.rows.length });
    return {
      type: "candidates",
      candidates: buildingResult.rows,
      trace_id: ledger.traceId,
      message: "Confirm one building before records are joined.",
      trace: ledger.events,
    };
  }
  const casePacket = await buildCase(buildingResult.rows[0], ledger, [buildingResult.receipt], fetchImpl);
  return { type: "case", case: casePacket, trace: ledger.events };
}

function treatedSuggestions(features, exactHouseNumber = "") {
  const seen = new Set();
  const suggestions = [];
  for (const feature of features || []) {
    const properties = feature?.properties || {};
    const pad = properties?.addendum?.pad || {};
    const house = String(properties.housenumber || "");
    if (exactHouseNumber && house.toUpperCase() !== exactHouseNumber.toUpperCase()) continue;
    if (!house || !properties.street || !properties.borough) continue;
    const label = String(properties.label || "").replace(/, USA$/, "");
    const key = `${pad.bin || ""}|${label}`;
    if (seen.has(key)) continue;
    seen.add(key);
    suggestions.push({
      id: String(properties.gid || properties.id || ""),
      label,
      borough: String(properties.borough || ""),
      house_number: house,
      street_name: String(properties.street || ""),
      zip: String(properties.postalcode || ""),
      bin: String(pad.bin || ""),
      coordinates: (feature?.geometry?.coordinates || []).slice(0, 2),
    });
    if (suggestions.length === 5) break;
  }
  return suggestions;
}

export async function getAddressSuggestions(rawQuery, fetchImpl = fetch) {
  const cleaned = String(rawQuery || "").trim().replace(/\s+/g, " ").slice(0, 100)
    .replace(/(?:,|\s)\s*(?:APT(?:ARTMENT)?|UNIT)\.?\s*#?\s*[A-Z0-9-]+\b/i, "");
  if (cleaned.length < 3) return [];
  const autocompleteUrl = `${GEOSEARCH_AUTOCOMPLETE}?${new URLSearchParams({ text: cleaned, size: "6" })}`;
  const autocomplete = await fetchWithRetry(autocompleteUrl, { fetchImpl, attempts: 2, timeoutMs: 6_000 });
  const suggestions = treatedSuggestions(autocomplete.features);
  if (suggestions.length) return suggestions;
  const house = cleaned.match(/^([0-9]+(?:-[0-9]+)?[A-Z]?)\b/i)?.[1];
  if (!house) return [];
  const searchUrl = `${GEOSEARCH_SEARCH}?${new URLSearchParams({ text: cleaned, size: "6" })}`;
  const search = await fetchWithRetry(searchUrl, { fetchImpl, attempts: 2, timeoutMs: 6_000 });
  return treatedSuggestions(search.features, house);
}

export function jsonResponse(value, status = 200, headers = {}) {
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      ...headers,
    },
  });
}
