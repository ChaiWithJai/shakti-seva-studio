# Tracing contract

Each run creates `traces/<trace_id>.jsonl`. Events are append-only and contain:

```json
{
  "trace_id": "uuid",
  "sequence": 1,
  "timestamp": "UTC ISO 8601",
  "kind": "query.completed",
  "payload": {},
  "previous_hash": "sha256 or null",
  "event_hash": "sha256"
}
```

The event hash covers every field except `event_hash`. Changing, removing, or
reordering an event breaks verification.

Required event families are:

- `case.started` and `case.completed`;
- `query.started` and `query.completed`;
- `normalization.completed`;
- `routing.completed`;
- `hermes.inspected`, `hermes.started`, and `hermes.completed`; and
- `case.failed` or `hermes.failed` when applicable.

Trace verification checks sequence numbers, previous hashes, and event hashes.
It does not prove that a source was correct. Source authority and trace
integrity are separate claims.
