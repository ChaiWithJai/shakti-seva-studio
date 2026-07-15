# Five borough live data smoke evaluation

On July 15, 2026, Shakti ran a fixed sample of 30 active HPD building records
in each borough. The run used 150 public building records. It did not use
resident input or a model.

![Map of the five borough smoke sample](assets/five-borough-eval-map.svg)

## What ran

The runner selected six active HPD buildings from each of five evenly spaced
Building ID windows in each borough. This produced 30 cases per borough and 150
cases in total. It is a deterministic smoke sample. It is not a random or
representative sample of New York City housing.

For each building, the runner:

1. Fetched the bounded complaint, open violation, and AEP fields.
2. Treated unit location text before it entered the case packet.
3. Checked the 40,000 character packet limit.
4. Selected the next step with code.
5. Verified the complete hash chained trace.
6. Ran a post treatment scan for apartment and unit identifiers.

The runner is in [`evals/five_borough.py`](../evals/five_borough.py). The
sanitized result is in
[`evals/baseline/five-borough.json`](../evals/baseline/five-borough.json). Raw
case traces stay under `output/` and are not committed.

## What the run showed

| Check | Result |
| --- | ---: |
| Case pipelines completed | 150 of 150 |
| Hash chains verified | 150 of 150 |
| Post treatment privacy scans passed | 150 of 150 |
| Cases that required unit location redaction | 79 |
| Cases that hit a complaint or violation record cap | 27 |
| Map points resolved from City data | 138 of 150 |

The code selected these routes:

| Code selected route | Cases |
| --- | ---: |
| Follow up about an open Class C violation | 30 |
| Follow up about another open violation | 36 |
| Track a complaint | 49 |
| Start with an official 311 complaint | 35 |

Case packets ranged from 1,838 to 30,657 canonical JSON characters. The mean
was 7,697 characters. Every packet stayed below the 40,000 character limit.

## What changed because of the loop

The live run did not stay clean on the first attempt.

1. The first privacy assertion treated `[UNIT REDACTED]` as if it were an
   exposed unit. The assertion now distinguishes a treatment marker from an
   untreated identifier. The rerun counted 79 treated cases and passed all 150
   post treatment scans.
2. One Brooklyn request received a temporary HTTP 500 response from NYC Open
   Data. The client now retries temporary 429 and server errors up to three
   times with a short delay. A unit test covers that behavior. The fixed sample
   then completed 150 of 150 cases.
3. Twelve sampled buildings did not resolve to a point in the two City map
   datasets. The map shows 138 resolved points and reports the gap. It does not
   invent coordinates.

```text
fixed public sample
  -> bounded case packets
  -> privacy scan and trace verification
  -> name each failure
  -> change the smallest boundary
  -> add a test
  -> rerun the fixed sample
  -> publish the remaining gaps
```

## What this does not prove

The run proves that the bounded data path completed across a fixed five borough
sample. It does not prove that the sample represents all buildings. It does not
prove that the selected route is right for a person. It does not prove that an
advocate can use the interface during a real conversation.

The next loop is observed use with advocates. Set the task and measures before
the sessions. Watch where people hesitate, where addresses fail, and where the
brief needs a human explanation. Publish those results before making a usability
claim.

## Run it again

This command fetches live public data and writes raw traces under `output/`:

```bash
PYTHONPATH=src .venv/bin/python evals/five_borough.py --workers 5
```

Use `--publish` only when you intend to replace the dated public baseline and
map. Public data can change, so route counts and packet sizes may differ later.
