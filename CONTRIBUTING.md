# Contributing

Start with the synthetic fixture. A change is ready for review when it preserves
the deterministic routing boundary, passes the test suite, and produces a valid
hash-chained trace.

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/pytest
.venv/bin/shaki doctor
.venv/bin/shaki case --fixture
```

Never commit live traces, raw API responses, resident data, or model logs. Any
new NYC Open Data source must document its purpose, field allowlist, join key,
record limit, and freshness behavior before code is merged.
