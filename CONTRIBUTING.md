# Contributing

Make one small civic technology claim that another person can check. Start with
the synthetic fixture. Do not use a resident address to learn the codebase or
reproduce a bug.

## Choose one user and one task

Write two sentences before you change code:

1. Name the person who will use the result.
2. Name the task they should complete more safely, clearly, or quickly.

For example: "A housing advocate needs to tell a complaint from a violation
before a tenant meeting. The result must preserve the source of each fact."

Do not begin with a model, framework, or dataset. Begin with the person's task.

## Run the known case

```bash
python3 scripts/bootstrap.py
.venv/bin/shakti case --fixture
.venv/bin/python evals/run.py
```

Expect the fixture to name `10 Sample Street, Queens`, choose a next step, and
produce a valid trace. Every Day 0 row must report `PASS`.

## Change one boundary at a time

Code validates the address, selects fields, treats unit locations, limits
records, and chooses the next step. Hermes may explain the resulting packet.
It must not choose the route or receive an unbounded dataset response.

A new NYC Open Data source needs:

1. A public purpose and named user task.
2. The dataset ID and join key.
3. An explicit field list.
4. A record limit and truncation rule.
5. A freshness rule.
6. Treatment for unit locations and free text.
7. Tests for missing, malformed, and oversized responses.

Add a synthetic example that shows the expected result. Keep the model out of
the first acceptance test.

## Check the whole story

Run:

```bash
.venv/bin/pytest
.venv/bin/python evals/run.py
```

For a browser change, start `.venv/bin/shakti serve` and use a reviewed public
building such as the live acceptance address in `docs/validation-report.md`.
Check the address treatment, separate record types, source disclosure, and City
support link. Confirm that the browser console is clean and no request leaves
the documented product boundary. Include a screenshot when the visible result
changes. The screenshot must show its live source receipts and validation date;
do not present a fixture as product proof.

For a Hermes launch change, test `--print-command` first. A model run is a
separate acceptance gate. Record the model, context size, memory limit, prompt,
trace, and stop condition.

## Explain what the change proves

In the pull request, include:

1. The user and task.
2. The smallest visible result.
3. The synthetic input used for automated tests and, for a live data claim, the
   reviewed public building and source receipts used for acceptance.
4. The commands you ran and their results.
5. What remains unknown.

A useful public interest technology portfolio shows judgment as well as code.
Explain why a field enters the case, why an action stays outside the model, and
how another person can reproduce the result.

## Protect people and evidence

Never commit live traces, raw API responses, resident data, model logs, access
tokens, or local paths. A public UI screenshot may use a reviewed building-level
record only when the evidence is already public, unit locations are treated,
and source receipts are visible. Synthetic fixtures belong in automated tests,
not public product proof. Trace events must stay ordered, hash chained, and free
of resident input.

Before you ask for review, confirm:

* The deterministic action boundary is intact.
* The fixture and Day 0 suite pass.
* New fields have privacy treatment tests.
* Visible changes have current evidence.
* The documentation states what was and was not tested.
* No private or machine specific data is present.
