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
