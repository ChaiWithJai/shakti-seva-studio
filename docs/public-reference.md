# Public reference

Shakti Seva Studio is a local civic technology prototype. It helps a person inspect New York City housing repair records while keeping the source, privacy treatment, action, and trace visible.

The [README](../README.md) is the canonical product, design, and engineering
case study. It states what works, the live data path, the dated address proof,
the design decisions, the model boundary, and what has not been proved.

The engineering article [How we built this](how-we-built-this.md) explains the
data sources, record treatment, repository structure, browser and Hermes roles,
measurements, and deployment options. It includes captures from the live app
and the governed Hermes interface.

The public repository is [ChaiWithJai/shakti-seva-studio](https://github.com/ChaiWithJai/shakti-seva-studio). The repository, product, and Python package all use the correct name, Shakti.

## What you can cite

Use the dated [validation report](validation-report.md) for the current test results. Use the [five borough evaluation](five-borough-eval.md) for the live public data method and limits. The sanitized [evaluation baseline](../evals/baseline/five-borough.json) contains the result for each sampled case without an address.

The main live evaluation claim is narrow. On July 15, 2026, the fixed sample included 30 building records in each borough. All 150 case pipelines, privacy scans, and trace chains passed. The run does not represent all New York City buildings and does not prove advocate usability.

## What you can reproduce

Run the local acceptance suite:

```bash
python3 scripts/bootstrap.py
.venv/bin/pytest
.venv/bin/python evals/run.py
```

Run the fixed live public data sample only when you intend to call NYC Open Data:

```bash
PYTHONPATH=src .venv/bin/python evals/five_borough.py --workers 5
```

Raw live traces stay under the ignored `output/` directory. Do not publish them.

## Where to start

Read the [Day 0 guide](day-0.md) for the first local run. Read the [architecture](architecture.md) before changing the model boundary. Read [CONTRIBUTING.md](../CONTRIBUTING.md) before adding a dataset or user task.

The repository includes an Apache 2.0 license, a security policy, a
contribution guide, a citation file, and a read only GitHub Actions workflow.
