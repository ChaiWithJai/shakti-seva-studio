# Evaluation guide

The Day 0 suite is an acceptance test for the product boundary. It combines
unit tests with installed-command and running-server checks.

## Automated checks

| Check | What it proves |
| --- | --- |
| Installed command | The editable package imports through `.venv` |
| Test suite | Field treatment, routing, tracing, CLI, adapter, and socket tests pass |
| Doctor | Required local directories and Hermes interfaces are present |
| Hermes launch contracts | TUI and CLI receive the governed 32K environment |
| CLI fixture and trace | An internal test case completes and its hash chain verifies |
| Public bind refusal | The web server will not listen on `0.0.0.0` |
| Server and socket | Cheap liveness does not inspect Hermes; readiness does; a same-origin socket connects; no browser fixture path exists |
| Published evidence | Screenshots have reviewable dimensions and the demo media has valid file signatures |

Run the suite with:

```bash
.venv/bin/python evals/run.py --output output/evals/day0.json
```

The process exits nonzero if any required check fails. Reports record timings
and sanitized details so that machine-specific home and repository paths are
not committed.

## Captured UI evidence

The public browser evidence comes from a headed run against NYC GeoSearch and
the four NYC Open Data sources. The dated validation report includes the typed
address, selected NYC BIN, HPD Building ID, source row counts, trace result, and
browser console result. Fixture based browser screenshots were removed.

The TUI image came from an actual pseudo-terminal session. A terminal emulator
rendered the captured ready frame into HTML, and Chromium captured that page.
The repository path and Hermes session ID were redacted. This gives a stable,
reviewable artifact without pretending that a model response was tested.

The documentation follows an outcome-first structure and limits claims to
reviewable evidence. Those choices follow the public
[mine-writing-rules](https://github.com/shreyashankar/mine-writing-rules)
collection. The repository publishes no prerecorded demo video as evidence;
the screenshots and GIF above come from the running app and live City sources.

## What remains separate

The suite does not score an answer, load a local model, fill a 32K context, or
exercise compaction. A model acceptance run must name the model build, prompt
tokens, generated tokens, memory policy, tool result, trace, and stop condition.
It should run on the synthetic fixture before any live public-record lookup.

Live NYC Open Data validation is also separate because public records can
change. The dated [validation report](validation-report.md) records the latest
bounded live lookup and the treatment issue it exposed.
