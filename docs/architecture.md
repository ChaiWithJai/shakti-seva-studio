# Architecture

## Decision

Shakti Seva Studio uses a deterministic data plane and an optional generative
explanation plane. The same case packet feeds the CLI, Hermes TUI workflow, and
local web interface.

## Components

```text
CLI or browser
  -> local FastAPI server
     -> NYC GeoSearch autocomplete (browser flow only)
  -> WebSocket event channel
  -> case service
     -> Socrata client
     -> field allowlist
     -> record normalizer
     -> routing policy
     -> trace ledger
  -> optional Hermes subprocess
```

### Case service

The case service owns address normalization, query construction, identifier
joins, field selection, record limits, and routing. It returns a stable JSON
contract. It does not generate prose.

### Trace ledger

Every event contains the previous event hash. Query values are represented by
hashes in the ledger. Curated public results can appear in the final packet,
but resident free text and apartment-level fields cannot.

### Hermes adapter

The adapter checks the installed Hermes version and required CLI flags. A live
run invokes `hermes chat` with a bounded turn count, a session source tag,
session ID injection, and checkpoints. The adapter passes only the curated
packet. It never passes raw Open Data responses.

### Local web server

FastAPI serves static assets on loopback and exposes `/ws`. The socket carries
typed progress, case, trace, and error messages. It does not expose a public
network listener by default. The server rejects non-loopback bind requests,
and the socket rejects browser handshakes whose `Origin` does not match the
requested local host.

The browser address picker calls the local `/api/address-suggestions` proxy
after three characters. The proxy removes apartment identifiers, requests up to
six NYC GeoSearch candidates, and returns five treated suggestions. Selecting a
suggestion supplies its NYC BIN to the case service, avoiding a second fuzzy
address interpretation. Autocomplete queries are not persisted or traced.

## Context policy

The expected model window is 32K tokens. Shakti targets a much smaller case
packet so the interface remains useful under pressure:

- instructions and tool schemas: up to 4K;
- curated City evidence: up to 8K;
- resident interaction and tool history: up to 8K;
- final explanation and safety reserve: at least 8K; and
- compaction or refusal before the complete conversation reaches 28K.

Raw logs, full building histories, and broad searches are outside the model
context.

## UI patterns

- Dashboard for case state and source freshness.
- Module Tabs for Case, Evidence, and Trace.
- Activity Stream for the chronological repair record.
- Progressive Disclosure for raw identifiers and governance details.
- Forgiving Format for complete pasted addresses.
- Autocomplete and Input Feedback for ranked, canonical NYC addresses.
- Blank Slate behavior for an unresolved live address.
