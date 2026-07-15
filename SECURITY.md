# Security policy

## Prototype boundary

Shakti Seva Studio is a local public-interest technology prototype, not an
official City service. It binds to loopback, requires same-origin WebSocket
handshakes, and keeps live Hermes execution off by default.

You may paste a full address that contains an apartment number. The browser
removes the apartment before requesting suggestions from NYC GeoSearch, then
shows the selected building address before querying NYC Open Data. Suggestion
queries are not written to Shakti's trace ledger. You can avoid autocomplete by
pasting a complete address and submitting it directly.
Do not enter a resident name, contact information, case narrative, or other
sensitive data.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository. Do not
include resident data, access tokens, or unredacted trace files in a report.

## Operational guidance

- Do not bind the server to a public interface or place it behind a public proxy.
- Review every dataset and field change against `docs/data-treatment.md`.
- Keep `SHAKTI_HERMES_ENABLED` unset until the runtime, model, and memory limits
  have passed a traced acceptance run.
- Treat local trace files as potentially sensitive operational records even
  though the application redacts and hashes resident input.
