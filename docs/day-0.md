# Day 0 guide

Day 0 has one goal. Run one complete civic case and see the same evidence as
every other contributor. You do not need resident data or a model call.

At the end, choose one reason to continue. You can help an advocate test the
brief, turn the work into a public interest technology portfolio project, or
adapt the pattern to another civic question.

## 1. Bootstrap

Use Python 3.13 and `uv`:

```bash
python3 scripts/bootstrap.py
```

Expect the final doctor check to report that the local paths and interfaces are
ready. The script creates `.venv`, installs the project in editable mode,
verifies the import, and runs `shakti doctor`. On macOS it also clears hidden
flags that can prevent Python from reading an editable install path file on an
external APFS volume.

## 2. Run the synthetic case

```bash
.venv/bin/shakti case --fixture
```

Expect the command to name the sample building, select a next step, and print a
trace path. The fixture is invented and stable. It exercises field selection,
unit treatment, record limits, deterministic routing, and the hash chained
trace.

## 3. Try the AI-free public web UI

Open [shakti-seva-studio.netlify.app](https://shakti-seva-studio.netlify.app).
The runtime badge and system-boundary card should both state that the public
lookup uses no AI. Type an address, inspect the City match, and open the source
receipts. The hosted edition uses static files and Netlify Functions; it has no
Python, WebSocket, Hermes, or Bonsai runtime.

## 4. Use the local web UI

```bash
.venv/bin/shakti serve
```

Open `http://127.0.0.1:8765`. Type a New York City address and press Enter.
Review the whole flow:

- The address picker returns a canonical NYC address.
- The page explains any difference between the typed address and HPD address.
- The short version shows the code selected action first.
- Complaints and violations remain separate.
- Sources and the processing record remain available in one disclosure.
- The ending links to official NYC Tenant Protection resources.

The server refuses a public bind. Its browser socket accepts the same loopback
origin and rejects a cross-origin handshake.

The browser uses NYC GeoSearch to find the address, then the server queries the
four NYC Open Data sources listed in the README. Public records can change, so
record the address, identifiers, fetch time, row counts, and trace result when
you report a live browser run.

## 5. Use Hermes

```bash
.venv/bin/shakti hermes --print-command --tui
.venv/bin/shakti hermes --tui
```

The wrapper supplies a 32K startup expectation to the evaluated local Hermes
fork. The screenshot proves that the TUI reached its ready state with the
workspace tools loaded. It does not prove model quality, a full 32K prompt, or
memory safety under inference load.

![Hermes TUI ready state](assets/screenshots/hermes-tui.png)

## 6. Run the acceptance suite

```bash
.venv/bin/python evals/run.py
```

Expect every required row to say `PASS`. The JSON report is written under
`output/evals/`. The checked-in [baseline](../evals/baseline/day0.json) records
the public Day 0 result without local paths.

## Choose the next small step

You have enough evidence for a first contribution when the live browser result
has source receipts and every Day 0 row passes. Open the
[contribution guide](../CONTRIBUTING.md). Choose one user visible sentence, one
privacy test, or one synthetic civic case. State what the change helps someone
do and what it does not prove.

Then read the dated [five borough evaluation](five-borough-eval.md). It shows
how the project moved from a safe fixture to a fixed live public data sample,
what the traces found, which failures changed the code, and which map gap
remains open.

## What Day 0 found

The work exposed two integration failures before documentation was written.
Python skipped an editable-install path file marked hidden on the external
volume. Hermes also enforced its upstream 64K startup floor against a 32K local
model. The bootstrap script handles the first issue. The governed wrapper and
the evaluated local fork expose explicit 32K startup controls for the second.

These fixes make startup repeatable. They do not turn a 32K model into a 64K
model or make an unbounded prompt safe.

## Stop conditions

Stop and investigate when the trace fails verification, a response contains a
unit identifier, the server binds beyond loopback, the browser reports a socket
origin error, or Hermes reports less context than the governed target. Do not
work around these failures by increasing model load.
