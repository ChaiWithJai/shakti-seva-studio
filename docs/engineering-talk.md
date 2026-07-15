# Engineering local AI for inspectable civic work

These notes record the architecture, experiments, and failures behind the
project. The earlier prerecorded talk contains fixture based scenes and is not
part of the public demo or evidence contract. The live browser flow and dated
reports are authoritative.

The visual treatment uses three public references. The [Shakti GitHub repository](https://github.com/ChaiWithJai/shakti-seva-studio) is the application artifact. [PrismML Developer](https://yourwildcard.ai/) supplies the measured trace documentation pattern. [Inference the Hard Way](https://chaiwithjai.github.io/inference-the-hard-way/#01-tokenizer) supplies the tokenizer and KV cache whiteboard artifacts.

These notes cover:

* The user task and the evidence standard.
* The FastAPI, WebSocket, case service, and trace application layers.
* The Hermes adapter and the model's limited job.
* The measured Bonsai CPU review runs.
* The data path that runs before the model.
* The privacy and trace boundaries.
* The 32K operating expectation and its limits.
* The fixed 150 case live public data evaluation.
* The failures that changed the code.
* The evidence still needed from observed advocate sessions.

## Application layer

The command line tool, browser, and Hermes terminal interface use one JSON case contract. FastAPI serves the browser on `127.0.0.1`. A same origin WebSocket sends typed progress, case, trace, and error events.

The case service owns the public data policy. It queries four allowed datasets, selects named fields, limits record counts, treats unit locations, joins records by public identifiers, and selects the next action in code. The trace ledger links every event to the previous event hash. Interface code does not own these decisions.

## AI layer

The Hermes adapter inspects the installed command before use. It checks the version and required flags. Model use is off by default.

When enabled, the adapter sends the curated case record and a short explanation instruction. It does not send raw City responses. The command has a four turn limit and a 180 second timeout. The trace stores the case hash, exit code, output size, and output hashes. Code has already selected the next action, so the model cannot change it.

## Local review profile

We used `prism-ml/Bonsai-4B-gguf` through llama.cpp on the CPU to review two versions of the demo script.

| Measurement | First review | Second review |
| --- | ---: | ---: |
| Context | 2,048 tokens | 4,096 tokens |
| Generated output | 240 tokens | 320 tokens |
| Model load | 1.97 seconds | Not recorded |
| Prompt processing | 103.23 tokens per second | 134.3 tokens per second |
| Generation | 22.26 tokens per second | 32.1 tokens per second |

These measurements show that the bounded reviews ran locally. They do not measure Hermes case performance or full 32K inference safety. The [Bonsai review record](bonsai-review.md) lists the findings and the decisions that followed.

The review uses the [Prefill Versus Decode](https://yourwildcard.ai/docs/technical-guides/prefill-vs-decode/) guide to separate the two speed measurements. It uses [Inference the Hard Way Lab 03](https://chaiwithjai.github.io/inference-the-hard-way/#03-kv-cache) to explain why the advertised context window is not a memory safety promise.

## Public data experiment

The five borough run selected 30 fixed HPD building records in each borough. All 150 pipelines, privacy scans, and trace chains passed. The run also exposed a temporary server error, a false privacy failure, and unresolved map points. Those findings led to bounded retry handling, a corrected privacy check, and an explicit map coverage gap.

## Check the claims

Start with these public artifacts:

* [Five borough evaluation](five-borough-eval.md)
* [Sanitized evaluation baseline](../evals/baseline/five-borough.json)
* [Evaluation runner](../evals/five_borough.py)
* [Architecture](architecture.md)
* [Dated validation report](validation-report.md)
* [Contribution guide](../CONTRIBUTING.md)

The prerecorded video sources were removed because their fixture based scenes
were not valid product evidence.

## What this evidence does not claim

The fixed live sample proves data path coverage for the selected records. It does not prove that advocates can use the interface without help. It does not measure time saved, understanding, or outcomes. Observed sessions are the next evaluation.
