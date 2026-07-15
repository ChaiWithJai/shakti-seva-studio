# Validation report

Validated locally on July 15, 2026. This report records what was exercised; it
is not a claim that changing public data or an untested model will behave the
same way later.

## Automated controls

- 18 tests passed for field treatment, address normalization, routing, packet
  limits, trace integrity, CLI behavior, static assets, socket behavior, and the
  Hermes adapter. The data client test covers bounded retry after a temporary
  server error.
- A cross-origin WebSocket handshake was rejected with policy code `1008`.
- A controlled fake Hermes process completed the full adapter boundary and
  produced `hermes.inspected`, `hermes.started`, and `hermes.completed` events.
- `shakti serve --host 0.0.0.0` was refused.
- The Day 0 acceptance runner passed all nine installed-command, fixture,
  trace, launch-contract, bind, server, and socket checks.

## Installed Hermes interfaces

`shakti doctor` found Hermes Agent `0.18.2` (`2026.7.7.2`) and verified the
required CLI, TUI, checkpoint, source, session ID, bounded-turn, serve, session,
and log interfaces. Both governed launch commands were composed successfully.
The modern TUI then reached its ready state through the Shakti wrapper at the
governed 32K startup target.

No local model was loaded during this validation. Model quality, tool selection,
32K inference pressure, compaction, and memory safety remain separate acceptance
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

## Five borough live data smoke sample

A fixed sample ran 30 active HPD buildings in each borough. All 150 case
pipelines completed. All 150 post treatment privacy scans and hash chains
passed. Seventy nine cases required a unit location redaction marker. Twenty
seven cases reached a complaint or violation record cap while remaining below
the 40,000 character packet limit.

One Brooklyn request received a temporary NYC Open Data HTTP 500 response. The
client gained a bounded retry for temporary 429 and server errors. The same
fixed sample then completed 150 of 150 cases. Two City point datasets resolved
138 map points. Twelve remain unresolved and are reported as a coverage gap.

The sanitized [five borough report](five-borough-eval.md) includes the sampling
method, route counts, map, and limits. Raw traces remain local under `output/`.
This smoke sample proves data path coverage, not representative coverage or
advocate usability.

## Browser acceptance

A clean headed browser run verified the single field address picker. We typed
`700 E 9th Street, Manhattan` and pressed Enter without clicking a suggestion.
NYC GeoSearch returned `700 EAST 9 STREET, New York, NY` and NYC BIN `1004529`.
HPD uses the corner address `140 Avenue C, Manhattan` for the same BIN. The page
showed both addresses, the join identifier, HPD Building `6533`, 25 complaints,
and 6 open violations. A visual primer explained the address-to-BIN-to-HPD
identity chain and linked to the City's BIN definition. Code selected the Class
C follow up route. Source cards
linked to the four NYC Open Data pages and showed the fetch date and returned
row count. The 13 event trace hash chain verified. The final case hash was
`03632f88eb274bc7b59d825dc25b904f0c65434843e2b553e62f4a90de5a492d`.
The browser console reported no errors or warnings.

The non-personal acceptance fields are preserved in the machine-checked
[live address baseline](../evals/baseline/live-address.json). It records the
typed address, City matches, join identifiers, displayed totals, source pages,
route, and trace result without publishing the raw record rows.

The pasted input `900 East 9th Street, New York, NY, Manhattan` was also treated
as `900 East 9th Street, Manhattan` without exposing an internal parser error.
The public web interface contains no synthetic case or fixture control.

The lived address was also sent to live NYC GeoSearch in four common forms:
abbreviated, full city/state/ZIP, punctuated with borough, and uppercase City
record style. Each form returned `700 EAST 9 STREET, New York, NY`, BIN
`1004529`, as the first suggestion. The reviewed
[address input baseline](../evals/baseline/address-input-variants.json) records
the exact results and the narrow scope of this claim.

## Public demo acceptance

The public demo is the live browser flow. It contains no fixture control or
synthetic case. The exact address run, source receipts, alias explanation,
record limit notice, trace verification, and clean browser console are recorded
above.

All prerecorded videos and their production sources were removed because they
contained fixture based scenes. The README, live application, source receipts,
tests, and dated reports are the authoritative public artifacts.
