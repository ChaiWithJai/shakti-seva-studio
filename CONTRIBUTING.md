# Contributing

Start with the synthetic fixture. Do not use a resident address to learn the
codebase or reproduce a bug.

## Set up the project

```bash
python3 scripts/bootstrap.py
.venv/bin/shaki case --fixture
.venv/bin/python evals/run.py
```

The bootstrap script creates an editable environment, fixes a macOS hidden-file
edge case on external volumes, verifies the import, and runs `shaki doctor`.

## Keep the boundary clear

Code must validate the address, select fields, treat unit locations, limit
records, and choose the next step. Hermes may explain the resulting packet. It
must not choose the route or receive an unbounded dataset response.

A new NYC Open Data source needs all of the following:

- a public purpose;
- the dataset ID and join key;
- an explicit field allowlist;
- a record limit and truncation behavior;
- a freshness rule;
- unit-location and free-text treatment; and
- tests for missing, malformed, and oversized responses.

## Test the whole path

Run the focused tests while you work. Before opening a pull request, run:

```bash
.venv/bin/pytest
.venv/bin/python evals/run.py
```

For a browser change, start `shaki serve`, load the synthetic fixture, and
check the Case, Evidence, and Trace views. Confirm that the browser console is
clean and that no request leaves the loopback origin. Include a screenshot when
the visible result changes.

For a Hermes launch change, test `--print-command` first. A model run is a
separate acceptance gate and needs a stated model, context size, memory limit,
prompt, trace, and stop condition.

## Protect people and evidence

Never commit live traces, raw API responses, resident data, model logs, access
tokens, or local paths. Keep generated screenshots on the synthetic fixture.
Trace events must remain hash chained, ordered, and free of resident input.

## Pull request checklist

- The deterministic routing boundary is intact.
- The fixture and Day 0 suite pass.
- New data fields have treatment tests.
- User-visible changes have current evidence.
- Documentation states what was and was not tested.
- No private or machine-specific data is present.
