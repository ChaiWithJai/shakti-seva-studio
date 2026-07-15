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
| Fixture and trace | A synthetic case completes and its hash chain verifies |
| Public bind refusal | The web server will not listen on `0.0.0.0` |
| Server and socket | A loopback server handles the same-origin fixture request |
| Published evidence | Screenshots have reviewable dimensions and the demo media has valid file signatures |

Run the suite with:

```bash
.venv/bin/python evals/run.py --output output/evals/day0.json
```

The process exits nonzero if any required check fails. Reports record timings
and sanitized details so that machine-specific home and repository paths are
not committed.

## Captured UI evidence

The web images were captured in a headed Chromium session against the running
loopback server and synthetic fixture. The Case, Evidence, and Trace views were
checked. The browser console had no errors or warnings.

The TUI image came from an actual pseudo-terminal session. A terminal emulator
rendered the captured ready frame into HTML, and Chromium captured that page.
The repository path and Hermes session ID were redacted. This gives a stable,
reviewable artifact without pretending that a model response was tested.

The Liquid narration was rejected after its first long-form take became
unintelligible. The accepted take was generated one paragraph at a time on the
CPU, joined with short pauses, and transcribed locally. The transcript covered
the complete script. The rendered MP4 was checked for its video and audio
streams, duration, dimensions, and representative frames.

## What remains separate

The suite does not score an answer, load a local model, fill a 32K context, or
exercise compaction. A model acceptance run must name the model build, prompt
tokens, generated tokens, memory policy, tool result, trace, and stop condition.
It should run on the synthetic fixture before any live public-record lookup.

Live NYC Open Data validation is also separate because public records can
change. The dated [validation report](validation-report.md) records the latest
bounded live lookup and the treatment issue it exposed.
