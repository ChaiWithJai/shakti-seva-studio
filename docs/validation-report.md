# Validation report

Validated locally on July 14, 2026. This report records what was exercised; it
is not a claim that changing public data or an untested model will behave the
same way later.

## Automated controls

- 11 tests passed for field treatment, address normalization, routing, packet
  limits, trace integrity, CLI behavior, static assets, socket behavior, and the
  Hermes adapter.
- A cross-origin WebSocket handshake was rejected with policy code `1008`.
- A controlled fake Hermes process completed the full adapter boundary and
  produced `hermes.inspected`, `hermes.started`, and `hermes.completed` events.
- `shaki serve --host 0.0.0.0` was refused.

## Installed Hermes interfaces

`shaki doctor` found Hermes Agent `0.18.2` (`2026.7.7.2`) and verified the
required CLI, TUI, checkpoint, source, session ID, bounded-turn, serve, session,
and log interfaces. Both governed launch commands were composed successfully.

No local model was loaded during this validation. Model quality, tool selection,
32K context behavior, compaction, and memory safety remain separate acceptance
gates.

## Live NYC Open Data packet

A building-level lookup using `QUEENS`, `34-15`, and `Parsons Blvd` resolved by
exact normalized address to HPD Building ID `687226`. The resulting packet had:

- 25 displayed complaint records, marked truncated;
- 25 displayed open violations, marked truncated;
- 1 AEP record;
- 28,877 canonical JSON characters;
- the deterministic `urgent_hpd_follow_up` route; and
- a valid 12-event hash chain.

The first live run revealed apartment identifiers embedded inside HPD's public
`novdescription` text. Dropping only the apartment column was insufficient. The
description treatment was added, 22 location-bearing descriptions were treated,
and the repeated scan found no `APT`, `APARTMENT`, or `UNIT` identifier pattern.

## Browser acceptance

A clean headed browser run verified the synthetic fixture, Case, Evidence, and
Trace views, then built the same live public-record timeline over the local
WebSocket. The live browser trace contained 13 events, including the initial
request event. The browser console reported zero errors and zero warnings.
