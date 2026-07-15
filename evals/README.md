# Evaluation suite

The Day 0 suite tests the installed command, the governed data path, the trace
chain, the Hermes launch contract, the loopback server, and the browser socket.
It uses the synthetic fixture by default, so the test does not need resident
data or a model call.

Run it after setup:

```bash
python3 scripts/bootstrap.py
.venv/bin/python evals/run.py
```

The command writes a JSON report under `output/evals/`. Use `--output` to pick a
different path. A run fails when any required check fails.

The suite does not score model answers. Model quality and 32K context pressure
need a separate acceptance run with a chosen model and safe memory limits.

The reviewed [deployment profile](baseline/deployment-profile.json) preserves
the current web process memory, one live query timing, Hermes readiness timing,
cheap liveness timing, and the 150 case timing summary. These values are local
observations. They are not a concurrent load test or a Hermes inference profile.

Recheck the reviewed address in four common forms against live NYC GeoSearch:

```bash
PYTHONPATH=src .venv/bin/python evals/live_address_variants.py
```

The dated [address input baseline](baseline/address-input-variants.json) records
the accepted abbreviation, full city/state/ZIP, punctuation, and City-record
forms. It proves those four forms of one address, not Google Maps parity.

## Five borough live data smoke sample

Run the dated live public data sample with:

```bash
PYTHONPATH=src .venv/bin/python evals/five_borough.py --workers 5
```

The runner selects 30 fixed active HPD building records per borough. It checks
packet limits, unit location treatment, code selected routes, and hash chained
traces. It writes raw evidence under `output/`. It is not a representative
sample or a usability study.

Read the [public five borough report](../docs/five-borough-eval.md) before
rerunning it. Use `--publish` only when replacing the dated public baseline and
map with a reviewed result.
