const state = { runtime: "unknown", socket: null, reconnectTimer: null, case: null, trace: [], traceId: null, hermes: null, pendingTraceId: null, selectedAddress: null, searchedAddress: null, suggestions: [], activeSuggestion: -1, suggestionInput: "", suggestionStatus: "idle", suggestionTimer: null, suggestionController: null };
let runtimeReady;
const $ = (selector) => document.querySelector(selector);

function setConnection(status, label) {
  const node = $("#connection");
  node.className = `connection ${status}`;
  $("#connection-label").textContent = label;
}

function connect() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${location.host}/ws`);
  state.socket = socket;
  socket.addEventListener("open", () => setConnection("ready", "Running on this computer"));
  socket.addEventListener("close", () => {
    setConnection("error", "Connection lost");
    clearTimeout(state.reconnectTimer);
    state.reconnectTimer = setTimeout(connect, 1500);
  });
  socket.addEventListener("error", () => setConnection("error", "Connection error"));
  socket.addEventListener("message", (event) => handleMessage(JSON.parse(event.data)));
}

async function loadRuntime() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("runtime check failed");
    const health = await response.json();
    state.runtime = health.transport === "https" ? "serverless" : "local";
    state.hermes = health.hermes || null;
    if (state.runtime === "serverless") {
      setConnection("public", "Live City data · no AI");
    } else {
      connect();
    }
    updateHermesButton();
  } catch {
    state.runtime = "unavailable";
    state.hermes = null;
    setConnection("error", "Data service unavailable");
  }
}

async function sendHttp(message) {
  try {
    const response = await fetch("/api/case", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(message),
    });
    const result = await response.json();
    handleMessage(result);
  } catch {
    hideProgress();
    showError("The public data service could not complete this search. Try again shortly.");
  }
}

function send(message) {
  hideError();
  if (state.runtime === "serverless") {
    void sendHttp(message);
    return true;
  }
  if (!state.socket || state.socket.readyState !== WebSocket.OPEN) {
    showError("The local connection is not ready yet. Please try again.");
    return false;
  }
  state.socket.send(JSON.stringify(message));
  return true;
}

function parseAddress(value) {
  let working = value.trim().replace(/[–—]/g, "-").replace(/\s+/g, " ");
  if (!working) throw new Error("Enter a building address.");

  let unit = null;
  const unitPattern = /(?:,|\s)\s*(?:APT(?:ARTMENT)?|UNIT)\.?\s*#?\s*([A-Z0-9-]+)\b/gi;
  working = working.replace(unitPattern, (_match, identifier) => {
    unit = identifier.toUpperCase();
    return "";
  }).replace(/\s*,\s*,/g, ",").replace(/,?\s*(?:USA|UNITED STATES)\s*$/i, "").trim();

  const parts = working.split(",").map((part) => part.trim()).filter(Boolean);
  let streetAddress = parts[0] || "";
  const locationTail = parts.slice(1).join(", ");
  const boroughMatch = locationTail.match(/\b(BRONX|BROOKLYN|MANHATTAN|QUEENS|STATEN ISLAND)\b/i)
    || (parts.length === 1 ? working.match(/\s+(BRONX|BROOKLYN|MANHATTAN|QUEENS|STATEN ISLAND)(?:\s+(?:NY|NEW YORK))?(?:\s+\d{5}(?:-\d{4})?)?\s*$/i) : null);
  let borough = boroughMatch ? boroughMatch[1].toUpperCase() : "";

  if (parts.length === 1 && boroughMatch) {
    streetAddress = working.slice(0, boroughMatch.index).trim();
  } else if (parts.length === 1) {
    const cityState = working.match(/\s+NEW YORK\s+(?:NY|NEW YORK)(?:\s+\d{5}(?:-\d{4})?)?\s*$/i);
    if (cityState) {
      streetAddress = working.slice(0, cityState.index).trim();
      borough = "MANHATTAN";
    } else {
      streetAddress = working.replace(/\s+\d{5}(?:-\d{4})?\s*$/, "").trim();
    }
  } else if (!borough && /\bNEW YORK\b/i.test(locationTail)) {
    borough = "MANHATTAN";
  }

  const streetMatch = streetAddress.match(/^([0-9]+(?:-[0-9]+)?[A-Z]?)\s+(.+)$/i);
  if (!streetMatch) throw new Error("Start with the building number and street name.");
  const houseNumber = streetMatch[1].toUpperCase();
  const streetName = streetMatch[2].replace(/[\s,]+$/, "").trim();
  if (streetName.length < 2) throw new Error("Add the street name.");

  return {
    payload: { borough, house_number: houseNumber, street_name: streetName },
    unit,
    label: `${houseNumber} ${streetName}${borough ? `, ${titleCase(borough)}` : ""}`,
    scope: borough ? titleCase(borough) : "all five boroughs",
  };
}

function titleCase(value) {
  return String(value).toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function previewAddress() {
  const treatment = $("#address-treatment");
  const error = $("#form-error");
  const value = $("#address").value;
  error.textContent = "";
  $("#address").removeAttribute("aria-invalid");
  if (!value.trim()) {
    treatment.hidden = true;
    treatment.replaceChildren();
    return;
  }
  try {
    const selected = state.selectedAddress?.input === value;
    const parsed = selected ? state.selectedAddress : parseAddress(value);
    treatment.hidden = false;
    treatment.className = selected ? "address-treatment ready" : "address-treatment pending";
    treatment.replaceChildren();
    const search = document.createElement("span");
    if (selected) {
      search.innerHTML = `<strong>NYC address match</strong> ${escapeHtml(parsed.label)}`;
    } else if (state.suggestionStatus === "searching") {
      search.innerHTML = `<strong>Checking NYC addresses…</strong> ${escapeHtml(parsed.label)}`;
    } else if (state.suggestionStatus === "none") {
      search.innerHTML = `<strong>No City suggestion yet</strong> ${escapeHtml(parsed.label)}`;
    } else if (state.suggestionStatus === "unavailable") {
      search.innerHTML = `<strong>City suggestions unavailable</strong> ${escapeHtml(parsed.label)}`;
    } else {
      search.innerHTML = `<strong>Address entered</strong> ${escapeHtml(parsed.label)}`;
    }
    treatment.append(search);
    const scope = document.createElement("span");
    if (selected) {
      scope.innerHTML = `<strong>Confirmed search area</strong> ${escapeHtml(parsed.scope)}`;
    } else if (state.suggestionStatus === "none") {
      scope.innerHTML = `<strong>Try adding a borough or ZIP</strong> Or search this exact address across ${escapeHtml(parsed.scope)}.`;
    } else if (state.suggestionStatus === "unavailable") {
      scope.innerHTML = `<strong>You can still search</strong> We will check this exact address across ${escapeHtml(parsed.scope)}.`;
    } else {
      scope.innerHTML = `<strong>Next</strong> Choose the City suggestion that matches your building.`;
    }
    treatment.append(scope);
    if (parsed.unit) {
      const privacy = document.createElement("span");
      privacy.innerHTML = `<strong>Apartment ${escapeHtml(parsed.unit)} removed</strong> It will not be sent or saved.`;
      treatment.append(privacy);
    }
  } catch (error) {
    treatment.hidden = false;
    treatment.className = "address-treatment pending";
    treatment.replaceChildren();
    const hint = document.createElement("span");
    hint.innerHTML = `<strong>Keep going</strong> ${escapeHtml(error.message)}`;
    treatment.append(hint);
  }
}

function closeSuggestions() {
  const list = $("#address-suggestions");
  list.hidden = true;
  list.replaceChildren();
  state.activeSuggestion = -1;
  $("#address").setAttribute("aria-expanded", "false");
  $("#address").removeAttribute("aria-activedescendant");
}

function setActiveSuggestion(index, focus = false) {
  const options = [...$("#address-suggestions").querySelectorAll("button[role='option']")];
  if (!options.length) return;
  const next = (index + options.length) % options.length;
  state.activeSuggestion = next;
  for (const [optionIndex, option] of options.entries()) {
    const active = optionIndex === next;
    option.setAttribute("aria-selected", String(active));
    option.classList.toggle("active", active);
  }
  $("#address").setAttribute("aria-activedescendant", options[next].id);
  if (focus) options[next].focus();
}

function selectSuggestion(suggestion) {
  const input = $("#address");
  const parsed = {
    input: suggestion.label,
    payload: {
      borough: String(suggestion.borough || "").toUpperCase(),
      house_number: suggestion.house_number,
      street_name: suggestion.street_name,
      bin: suggestion.bin,
    },
    label: suggestion.label,
    scope: titleCase(suggestion.borough),
    unit: null,
  };
  input.value = suggestion.label;
  state.selectedAddress = parsed;
  state.suggestions = [];
  state.suggestionInput = "";
  state.suggestionStatus = "selected";
  closeSuggestions();
  previewAddress();
  input.focus();
}

function renderSuggestions(suggestions, inputValue) {
  const list = $("#address-suggestions");
  list.replaceChildren();
  if (!suggestions.length) {
    closeSuggestions();
    return;
  }
  state.suggestions = suggestions;
  state.suggestionInput = inputValue;
  for (const [index, suggestion] of suggestions.entries()) {
    const button = element("button", "address-suggestion");
    button.type = "button";
    button.id = `address-suggestion-${index}`;
    button.setAttribute("role", "option");
    button.setAttribute("aria-selected", "false");
    button.append(
      element("strong", null, suggestion.label),
      element("span", null, [suggestion.borough, suggestion.zip, suggestion.bin ? `BIN ${suggestion.bin}` : ""].filter(Boolean).join(" · ")),
    );
    button.addEventListener("click", () => selectSuggestion(suggestion));
    button.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        setActiveSuggestion(index + (event.key === "ArrowDown" ? 1 : -1), true);
      }
      if (event.key === "Enter") {
        event.preventDefault();
        selectSuggestion(suggestion);
        $("#case-form").requestSubmit();
      }
      if (event.key === "Escape") {
        event.preventDefault();
        closeSuggestions();
        $("#address").focus();
      }
    });
    list.append(button);
  }
  list.append(element("div", "suggestion-credit", "Official address suggestions from NYC GeoSearch. Choose one to lock the building match."));
  list.hidden = false;
  $("#address").setAttribute("aria-expanded", "true");
  setActiveSuggestion(0);
}

async function requestSuggestions(value) {
  if (state.runtime === "unknown" && runtimeReady) await runtimeReady;
  if (state.runtime === "unavailable") return [];
  state.suggestionController?.abort();
  const query = value.replace(/(?:,|\s)\s*(?:APT(?:ARTMENT)?|UNIT)\.?\s*#?\s*[A-Z0-9-]+\b/gi, "").trim();
  if (query.length < 3) {
    state.suggestionStatus = "idle";
    closeSuggestions();
    previewAddress();
    return [];
  }
  const controller = new AbortController();
  state.suggestionController = controller;
  state.suggestionStatus = "searching";
  previewAddress();
  try {
    const response = state.runtime === "serverless"
      ? await fetch("/api/address-suggestions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ q: query }),
        signal: controller.signal,
      })
      : await fetch(`/api/address-suggestions?q=${encodeURIComponent(query)}`, { signal: controller.signal });
    if (!response.ok) {
      state.suggestionStatus = "unavailable";
      previewAddress();
      return [];
    }
    const result = await response.json();
    const suggestions = result.suggestions || [];
    if ($("#address").value === value) {
      state.suggestionStatus = suggestions.length ? "matches" : "none";
      renderSuggestions(suggestions, value);
      previewAddress();
    }
    return suggestions;
  } catch (error) {
    if (error.name !== "AbortError") {
      state.suggestionStatus = "unavailable";
      closeSuggestions();
      previewAddress();
    }
    return [];
  }
}

function queueSuggestions() {
  const value = $("#address").value;
  state.selectedAddress = null;
  state.suggestions = [];
  state.suggestionInput = "";
  state.suggestionStatus = value.trim() ? "waiting" : "idle";
  clearTimeout(state.suggestionTimer);
  state.suggestionTimer = setTimeout(() => requestSuggestions(value), 220);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
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
    state.pendingTraceId = null;
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
    state.pendingTraceId = message.trace_id;
    renderCandidates(message.candidates || [], message.message);
    return;
  }
  if (message.type === "error") showError(message.message);
}

function showProgress(stage) {
  const labels = {
    resolving: ["Checking the address", "Confirming one City building record before repair records are joined."],
    building: ["Building the timeline", "Gathering the treated complaints and violations for the building you chose."],
    hermes: ["Preparing the explanation", "Hermes is reading the treated public building packet."],
  };
  const [title, detail] = labels[stage] || ["Working", "Processing the request on this computer."];
  $("#progress-title").textContent = title;
  $("#progress-detail").textContent = detail;
  $("#progress").hidden = false;
  $("#candidate-panel").hidden = true;
}

function hideProgress() { $("#progress").hidden = true; }
function showError(message) { const node = $("#workspace-error"); node.textContent = message; node.hidden = false; }
function hideError() { $("#workspace-error").hidden = true; $("#workspace-error").textContent = ""; }

function renderCandidates(candidates, message) {
  const panel = $("#candidate-panel");
  const list = $("#candidate-list");
  list.replaceChildren();
  if (!candidates.length) {
    panel.hidden = true;
    $("#result").hidden = true;
    const error = $("#form-error");
    error.textContent = "We could not match that address to one HPD building. Add the borough or ZIP, then choose a City suggestion.";
    $("#address").setAttribute("aria-invalid", "true");
    $("#address").focus({ preventScroll: true });
    $("#case-form").scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }
  panel.querySelector("p:not(.eyebrow)").textContent = message || "Choose one building before records are joined.";
  for (const candidate of candidates) {
    const button = element("button", "candidate");
    button.type = "button";
    const address = `${candidate.housenumber || ""} ${candidate.streetname || ""}, ${titleCase(candidate.boro || "")}`.trim();
    const meta = `ZIP ${candidate.zip || "not listed"} · HPD Building ${candidate.buildingid || "not listed"}`;
    button.append(element("strong", null, address), element("span", null, meta));
    button.addEventListener("click", () => {
      if (send({ type: "confirm", trace_id: state.pendingTraceId, building_id: candidate.buildingid })) showProgress("building");
    });
    list.append(button);
  }
  panel.hidden = false;
  $("#result").hidden = true;
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderCase() {
  const item = state.case;
  const building = item.building || {};
  const buildingAddress = `${building.housenumber || ""} ${titleCase(building.streetname || "")}, ${titleCase(building.boro || "")}`.trim();
  const searched = state.searchedAddress;
  const addressesDiffer = Boolean(searched?.label && searched.label.toUpperCase() !== buildingAddress.toUpperCase());
  $("#building-address").textContent = addressesDiffer ? searched.label : buildingAddress;
  $("#building-meta").textContent = addressesDiffer
    ? `City records filed under ${buildingAddress} · HPD Building ${building.buildingid || "not available"}`
    : `HPD Building ${building.buildingid || "not available"} · ZIP ${building.zip || "not available"}`;
  const matchNote = $("#address-match-note");
  const primer = $("#address-primer");
  if (addressesDiffer) {
    const bin = building.bin || searched.bin || "not available";
    matchNote.textContent = `Address match: ${searched.label} and ${buildingAddress} share NYC BIN ${bin}.`;
    matchNote.hidden = true;
    $("#primer-searched-address").textContent = searched.label;
    $("#primer-bin").textContent = bin;
    $("#primer-hpd-address").textContent = buildingAddress;
    primer.hidden = false;
  } else {
    matchNote.hidden = true;
    matchNote.textContent = "";
    primer.hidden = true;
  }
  $("#complaint-count").textContent = item.complaints.length;
  $("#open-count").textContent = item.violations.filter((row) => String(row.violationstatus).toUpperCase() === "OPEN").length;
  $("#aep-count").textContent = item.aep.length;
  const limitNote = $("#record-limit-note");
  const limited = [];
  if (item.truncated?.complaints) limited.push("more than 25 complaints matched");
  if (item.truncated?.open_violations) limited.push("more than 25 open violations matched");
  if (limited.length) {
    limitNote.textContent = `Display limit reached: ${limited.join(" and ")}. Shakti shows the 25 most recent records in each limited group. Check the City dataset for the complete history.`;
    limitNote.hidden = false;
  } else {
    limitNote.hidden = true;
    limitNote.textContent = "";
  }
  $("#next-step-label").textContent = item.next_step.label;
  $("#next-step-reason").textContent = item.next_step.reason;
  renderTimeline();
  renderSources();
  renderTrace();
  updateHermesButton();
  $("#candidate-panel").hidden = true;
  $("#result").hidden = false;
  $("#result").scrollIntoView({ behavior: "smooth", block: "start" });
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
    events.push({ date: complaint.received_date, type: "Complaint", title: complaint.major_category || "Housing complaint", detail: `${complaint.complaint_status || "Status not listed"}. ${complaint.status_description || "No public description."}`, id: complaint.complaint_id });
  }
  for (const violation of state.case.violations) {
    events.push({ date: violation.inspectiondate, type: `Class ${violation.class || "not listed"} violation`, title: violation.novdescription || "Housing violation", detail: `${violation.violationstatus || violation.currentstatus || "Status not listed"}. Correction date ${formatDate(violation.originalcorrectbydate)}.`, id: violation.violationid });
  }
  events.sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")));
  const list = $("#timeline");
  list.replaceChildren();
  if (!events.length) { list.append(element("li", "blank-inline", "No complaints or violations appear in this packet.")); return; }
  for (const event of events) {
    const row = element("li");
    row.append(element("time", null, `${event.type} · ${formatDate(event.date)}`), element("strong", null, event.title), element("p", null, event.detail), element("code", null, `Public record ${event.id || "ID not listed"}`));
    list.append(row);
  }
}

function renderSources() {
  const list = $("#source-list");
  list.replaceChildren();
  for (const source of state.case.sources) {
    const card = element("article", "source-card");
    const copy = element("div");
    const detail = source.fetched_at ? `Retrieved ${formatDate(source.fetched_at)} · ${source.row_count ?? "unknown"} rows returned` : "Freshness is in the processing record";
    copy.append(element("strong", null, source.name), element("span", null, detail));
    if (source.url) {
      const link = element("a", null, `Open dataset ${source.dataset_id}`);
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noreferrer";
      card.append(copy, link);
    } else {
      card.append(copy, element("code", null, source.dataset_id));
    }
    list.append(card);
  }
}

function renderTrace() {
  $("#copy-trace").disabled = !state.traceId;
  const list = $("#trace-list");
  list.replaceChildren();
  if (!state.trace.length) { list.append(element("li", "blank-inline", "No processing events yet.")); return; }
  for (const event of state.trace) {
    const row = element("li", "trace-event");
    const summary = element("div");
    summary.append(element("strong", null, event.kind), element("code", null, event.event_hash));
    row.append(element("span", null, event.sequence), summary, element("time", null, new Date(event.timestamp).toLocaleTimeString()));
    list.append(row);
  }
}

function updateHermesButton() {
  const button = $("#hermes-button");
  const link = $("#local-ai-link");
  if (state.runtime === "serverless") {
    button.hidden = true;
    link.hidden = false;
    $("#ai-card-title").textContent = "Bring the treated packet to local AI";
    $("#ai-card-copy").textContent = "Download the repository to run Hermes or Bonsai on your own computer and instrument each tool call. The hosted lookup stays deterministic and AI-free.";
    return;
  }
  button.hidden = false;
  link.hidden = true;
  $("#ai-card-title").textContent = "Read this in plain language";
  $("#ai-card-copy").textContent = "Hermes receives the treated building packet. It cannot change the next step.";
  const enabled = Boolean(state.case && state.hermes?.ready && state.hermes?.enabled);
  button.disabled = !enabled;
  button.textContent = enabled ? "Explain this record" : state.hermes?.ready ? "Hermes is off" : "Hermes unavailable";
}

function resetSearch() {
  $("#result").hidden = true;
  $("#candidate-panel").hidden = true;
  $("#address").focus();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

$("#address").addEventListener("input", () => { previewAddress(); queueSuggestions(); });
$("#address").addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeSuggestions();
  if (event.key === "Enter") {
    event.preventDefault();
    if (!$("#address-suggestions").hidden && state.suggestions[state.activeSuggestion]) {
      selectSuggestion(state.suggestions[state.activeSuggestion]);
    }
    $("#case-form").requestSubmit();
  }
  if (event.key === "ArrowDown" && !$("#address-suggestions").hidden) {
    event.preventDefault();
    setActiveSuggestion(state.activeSuggestion < 0 ? 0 : state.activeSuggestion + 1, true);
  }
});
$("#case-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearTimeout(state.suggestionTimer);
  const button = $("#case-form button[type='submit']");
  try {
    $("#candidate-panel").hidden = true;
    $("#result").hidden = true;
    $("#form-error").textContent = "";
    $("#address").removeAttribute("aria-invalid");
    const value = $("#address").value;
    let parsed = state.selectedAddress?.input === value ? state.selectedAddress : null;
    if (!parsed) {
      button.disabled = true;
      button.textContent = "Matching address…";
      let suggestions = state.suggestionInput === value ? state.suggestions : [];
      if (!suggestions.length) suggestions = await requestSuggestions(value);
      if (suggestions.length) {
        renderSuggestions(suggestions, value);
        const error = $("#form-error");
        error.textContent = "Choose the City address that matches your building. This keeps us from searching the wrong property.";
        setActiveSuggestion(0, true);
        return;
      } else {
        parsed = parseAddress(value);
      }
    }
    previewAddress();
    closeSuggestions();
    state.searchedAddress = { label: parsed.label, bin: parsed.payload.bin || "" };
    if (send({ type: "case", payload: parsed.payload })) showProgress("resolving");
  } catch (error) {
    $("#form-error").textContent = error.message;
    $("#address").setAttribute("aria-invalid", "true");
    $("#address").focus();
  } finally {
    button.disabled = false;
    const label = element("span", null, "Search City records");
    const arrow = element("span", null, "→");
    arrow.setAttribute("aria-hidden", "true");
    button.replaceChildren(label, arrow);
  }
});
$("#edit-address").addEventListener("click", resetSearch);
$("#new-search").addEventListener("click", resetSearch);
$("#hermes-button").addEventListener("click", () => send({ type: "hermes", trace_id: state.traceId }));
$("#copy-trace").addEventListener("click", async () => {
  if (!state.traceId) return;
  await navigator.clipboard.writeText(state.traceId);
  $("#copy-trace").textContent = "Copied";
  setTimeout(() => { $("#copy-trace").textContent = "Copy trace ID"; }, 1200);
});

runtimeReady = loadRuntime();
