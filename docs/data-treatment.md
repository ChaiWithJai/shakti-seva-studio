# Data treatment

## Purpose

The product helps a resident understand existing public records. It does not
create a risk score, infer fault, or make an enforcement recommendation.

## Source policy

Only official NYC Open Data datasets with stable identifiers are allowed in
version one. Each source receipt records:

- dataset ID;
- retrieval time;
- selected field list;
- hashed query predicate;
- returned row count; and
- canonical response hash.

## Field policy

The normalizer keeps dates, public case identifiers, category labels, status
labels, violation class, public descriptions, and building-level identifiers.

A packet contains at most 25 recent complaints, 25 open violations, and 10 AEP
records. The packet marks when a source result exceeded those display limits.
The complete packet must remain below 40,000 characters or the run stops before
Hermes is called.

It removes apartment numbers, latitude and longitude, resident names, contact
details, anonymous flags, and unbounded free text. Unknown fields are dropped.
Because HPD violation descriptions can embed unit locations inside a public
description, the normalizer also truncates `LOCATED AT APT/UNIT ...` clauses
and redacts standalone apartment or unit identifiers before packet creation.

## Join policy

Records join on published City identifiers. Address text is used only to find
a candidate HPD Building ID. Complaints and violations then join on that ID.
The application does not use fuzzy model matching to merge records.

Common street suffixes are expanded through a small reviewed table before the
exact lookup. For example, `BLVD` becomes `BOULEVARD`. The model does not
normalize or guess addresses.

In the browser, NYC GeoSearch may suggest a canonical address and NYC BIN while
the person types. Apartment identifiers are removed before that request. When a
person chooses a suggestion, the HPD building lookup uses the selected BIN. If
they do not choose one, the bounded deterministic parser and building-candidate
confirmation remain available. The model does not participate in either path.

## Freshness and ambiguity

Every visible source includes a retrieval time. Multiple building candidates
stop the flow for resident confirmation. Missing data is shown as missing and
is not interpreted as proof that a condition does not exist.

## Retention

The default trace records hashes and curated public fields. Raw responses are
not persisted. Local trace files are ignored by Git. No resident data is sent
to Hermes unless live explanations are explicitly enabled.
