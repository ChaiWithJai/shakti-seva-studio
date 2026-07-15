const state = { socket: null, reconnectTimer: null, case: null, trace: [], traceId: null, hermes: null };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function setConnection(status, label) {
  const node = $("#connection");
  node.className = `connection ${status}`;
  $("#connection-label").textContent = label;
  $("#transport-pill").textContent = status === "ready" ? "Socket connected" : label;
  $("#transport-pill").className = `pill ${status === "ready" ? "ready" : "off"}`;
}

function connect() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${location.host}/ws`);
  state.socket = socket;
  socket.addEventListener("open", () => setConnection("ready", "Local socket connected"));
  socket.addEventListener("close", () => {
    setConnection("error", "Socket disconnected");
    clearTimeout(state.reconnectTimer);
    state.reconnectTimer = setTimeout(connect, 1500);
  });
  socket.addEventListener("error", () => setConnection("error", "Socket error"));
  socket.addEventListener("message", (event) => handleMessage(JSON.parse(event.data)));
}

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    const health = await response.json();
    state.hermes = health.hermes;
    const pill = $("#hermes-pill");
    pill.textContent = health.hermes.ready ? (health.hermes.enabled ? "Hermes enabled" : "Hermes verified · off") : "Hermes unavailable";
    pill.className = `pill ${health.hermes.ready ? (health.hermes.enabled ? "ready" : "off") : "off"}`;
    updateHermesButton();
  } catch {
    $("#hermes-pill").textContent = "Hermes check failed";
    $("#hermes-pill").className = "pill off";
  }
}

function send(message) {
  hideError();
  if (!state.socket || state.socket.readyState !== WebSocket.OPEN) {
    showError("The local socket is not connected yet.");
    return;
  }
  state.socket.send(JSON.stringify(message));
}

function handleMessage(message) {
  if (message.type === "connection") return;
  if (message.type === "progress") {
    showProgress(message.stage);
    return;
  }
  hideProgress();
  if (message.type === "case") {
    state.case = message.case;
    state.trace = message.trace || [];
    state.traceId = message.case.trace_id;
    renderCase();
    return;
  }
  if (message.type === "hermes") {
    state.trace = message.trace || state.trace;
    $("#hermes-text").textContent = message.explanation;
    $("#hermes-response").hidden = false;
    renderTrace();
    return;
  }
  if (message.type === "candidates") {
    state.trace = message.trace || [];
    state.traceId = message.trace_id;
    renderTrace();
    showError(`${message.message} Found ${message.candidates.length} candidate(s). The prototype does not merge ambiguous buildings.`);
    switchTab("trace");
    return;
  }
  if (message.type === "error") showError(message.message);
}

function showProgress(stage) {
  const labels = {
    curating: ["Curating the fixture", "Removing disallowed fields and applying the routing policy."],
    resolving: ["Resolving the building", "Confirming one HPD Building ID before joining records."],
    hermes: ["Hermes is reading the packet", "Only curated public fields are in this model turn."],
  };
  const [title, detail] = labels[stage] || ["Working", "The local service is processing the request."];
  $("#progress-title").textContent = title;
  $("#progress-detail").textContent = detail;
  $("#progress").hidden = false;
}
function hideProgress() { $("#progress").hidden = true; }
function showError(message) { const node = $("#workspace-error"); node.textContent = message; node.hidden = false; }
function hideError() { $("#workspace-error").hidden = true; $("#workspace-error").textContent = ""; }

function renderCase() {
  const item = state.case;
  $("#blank-state").hidden = true;
  $("#case-content").hidden = false;
  const building = item.building || {};
  $("#building-address").textContent = `${building.housenumber || ""} ${building.streetname || ""}, ${building.boro || ""}`.trim();
  $("#building-meta").textContent = `HPD Building ID ${building.buildingid || "not available"} · ZIP ${building.zip || "not available"}${item.fixture ? " · synthetic fixture" : ""}`;
  $("#trace-id").textContent = item.trace_id;
  $("#complaint-count").textContent = item.complaints.length;
  $("#violation-count").textContent = item.violations.length;
  $("#open-count").textContent = item.violations.filter((row) => String(row.violationstatus).toUpperCase() === "OPEN").length;
  $("#aep-count").textContent = item.aep.length;
  $("#next-step-label").textContent = item.next_step.label;
  $("#next-step-reason").textContent = item.next_step.reason;
  renderTimeline();
  renderSources();
  renderTrace();
  updateHermesButton();
  switchTab("case");
}

function formatDate(value) {
  if (!value) return "Date not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(date);
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderTimeline() {
  const events = [];
  for (const complaint of state.case.complaints) {
    events.push({ date: complaint.received_date, type: "Complaint record", title: complaint.major_category || "Housing complaint", detail: `${complaint.complaint_status || "Status unavailable"} · ${complaint.status_description || "No public description"}`, id: complaint.complaint_id });
  }
  for (const violation of state.case.violations) {
    events.push({ date: violation.inspectiondate, type: `Class ${violation.class || "?"} violation`, title: violation.novdescription || "Housing violation", detail: `${violation.violationstatus || violation.currentstatus || "Status unavailable"} · correction date ${formatDate(violation.originalcorrectbydate)}`, id: violation.violationid });
  }
  events.sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")));
  const list = $("#timeline");
  list.replaceChildren();
  if (!events.length) { list.append(element("li", "blank-inline", "No complaint or violation records appear in this bounded packet.")); return; }
  for (const event of events) {
    const row = element("li");
    const time = element("time", null, `${event.type} · ${formatDate(event.date)}`);
    const title = element("strong", null, event.title);
    const detail = element("p", null, event.detail);
    const id = element("code", null, `Public record ${event.id || "ID unavailable"}`);
    row.append(time, title, detail, id);
    list.append(row);
  }
}

function renderSources() {
  const list = $("#source-list");
  list.replaceChildren();
  for (const source of state.case.sources) {
    const card = element("article", "source-card");
    const copy = element("div");
    copy.append(element("strong", null, source.name), element("span", null, source.fetched_at ? `Retrieved ${formatDate(source.fetched_at)}` : "Freshness is recorded in query trace events"));
    card.append(copy, element("code", null, source.dataset_id));
    list.append(card);
  }
}

function renderTrace() {
  $("#trace-count").textContent = state.trace.length;
  $("#copy-trace").disabled = !state.traceId;
  const list = $("#trace-list");
  list.replaceChildren();
  if (!state.trace.length) { list.append(element("li", "blank-inline", "No trace events yet.")); return; }
  for (const event of state.trace) {
    const row = element("li", "trace-event");
    const number = element("span", null, event.sequence);
    const summary = element("div");
    summary.append(element("strong", null, event.kind), element("code", null, event.event_hash));
    row.append(number, summary, element("time", null, new Date(event.timestamp).toLocaleTimeString()));
    list.append(row);
  }
}

function updateHermesButton() {
  const button = $("#hermes-button");
  const enabled = Boolean(state.case && state.hermes?.ready && state.hermes?.enabled);
  button.disabled = !enabled;
  button.textContent = enabled ? "Ask Hermes" : state.hermes?.ready ? "Hermes is off" : "Hermes unavailable";
}

function switchTab(name) {
  for (const button of $$("[data-tab]")) button.setAttribute("aria-selected", String(button.dataset.tab === name));
  for (const panel of $$(".tab-panel")) panel.hidden = panel.id !== `panel-${name}`;
}

$("#case-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = Object.fromEntries(form.entries());
  if (!payload.borough || !payload.house_number.trim() || !payload.street_name.trim()) {
    $("#form-error").textContent = "Enter a borough, house number, and street name.";
    return;
  }
  $("#form-error").textContent = "";
  send({ type: "case", payload });
});
function openFixture() { send({ type: "fixture" }); }
$("#fixture-button").addEventListener("click", openFixture);
$$('[data-open-fixture]').forEach((button) => button.addEventListener("click", openFixture));
$("#hermes-button").addEventListener("click", () => send({ type: "hermes", trace_id: state.traceId }));
$("#copy-trace").addEventListener("click", async () => {
  if (!state.traceId) return;
  await navigator.clipboard.writeText(state.traceId);
  $("#copy-trace").textContent = "Copied";
  setTimeout(() => { $("#copy-trace").textContent = "Copy trace ID"; }, 1200);
});
$$('[data-tab]').forEach((button) => button.addEventListener("click", () => switchTab(button.dataset.tab)));

connect();
loadHealth();
