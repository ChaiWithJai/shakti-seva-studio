# Extend Shakti with local AI and traced tool use

The public web edition is complete without AI. Use the local edition when the
research question is about explanation quality, local models, agent tools, or
trace design.

## Start from the deterministic case

Download the repository and build one live case before enabling a model:

```bash
git clone https://github.com/ChaiWithJai/shakti-seva-studio.git
cd shakti-seva-studio
python3 scripts/bootstrap.py
.venv/bin/shakti case \
  --borough MANHATTAN \
  --house-number 140 \
  --street-name "Avenue C" > output/local-case.json
```

Inspect `case`, `sources`, `next_step`, and `trace_path` in the output. The model
must not receive raw City responses or choose a different route.

## Hermes: implemented optional explainer

Hermes is the implemented agent adapter. Model use is off until explicitly
enabled.

```bash
.venv/bin/shakti doctor
export SHAKTI_HERMES_ENABLED=1
.venv/bin/shakti case \
  --borough MANHATTAN \
  --house-number 140 \
  --street-name "Avenue C" \
  --hermes > output/hermes-case.json
```

The Shakti ledger records `hermes.inspected`, `hermes.started`, and either
`hermes.completed` or `hermes.failed`. It hashes output and error streams rather
than copying them into the civic trace.

Hermes has a second, more detailed instrumentation surface for its internal
agent and tool activity:

```bash
hermes logs --component tools --since 30m
hermes sessions list
hermes sessions export --help
.venv/bin/shakti trace verify traces/TRACE_ID.jsonl
```

Use the shared session ID and `--source shakti-seva` tag to relate Hermes logs
to a Shakti run. Shakti does not currently import individual Hermes tool calls
into its hash chain. That is an explicit next engineering task, not a claimed
feature.

## Bonsai: measured bounded reviewer

`prism-ml/Bonsai-4B-gguf` was tested locally with llama.cpp as a small CPU
reviewer for bounded writing artifacts. The dated measurements are in the
[Bonsai review record](bonsai-review.md). Bonsai is not wired into the web UI or
the Hermes adapter.

Today, a contributor can use the treated `case` JSON as a bounded local review
artifact and record the model build, context limit, prompt tokens, generated
tokens, memory policy, output hash, and stop condition. Do not call that an
explanation inside the app until an adapter, trace events, failure behavior, and the
same acceptance gates exist.

## Adapter contract for another local model

A new adapter should accept only the treated case object and return prose plus
operational measurements. It must:

1. verify the model and runtime before loading;
2. enforce a context and output limit appropriate for the machine;
3. record model identity, input hash, output hash, duration, and stop reason;
4. expose every enabled tool and record each tool request and result hash;
5. prevent the model from changing `next_step` or querying broader resident data;
6. fail closed when the packet, tool result, or memory policy exceeds its limit;
7. keep the public hosted edition free of AI.

The first evaluation should compare the explanation to the treated packet and
source receipts. It should not begin with a full 32K prompt. The earlier machine
crash at 42,468 prefill tokens is the reason for that constraint.
