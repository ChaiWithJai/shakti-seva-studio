# Security policy

## Prototype boundary

Shakti Seva Studio is a public interest technology prototype, not an official
City service. The local edition binds to loopback, requires same origin
WebSocket handshakes, and keeps live Hermes execution off by default. The public
Netlify edition uses same origin HTTPS Functions and contains no AI endpoint.

You may paste a full address that contains an apartment number. The browser
removes the apartment before requesting suggestions from NYC GeoSearch, then
shows the selected building address before querying NYC Open Data. Suggestion
queries are not written to Shakti's trace ledger. In the public edition,
suggestions and cases use POST bodies that are not cached, so the address is not placed
in the request URL. Shakti does not intentionally log or persist those bodies,
but Netlify and City services process normal infrastructure metadata. You can
avoid autocomplete by pasting a complete address and submitting it directly.
Do not enter a resident name, contact information, case narrative, or other
sensitive data.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository. Do not
include resident data, access tokens, or unredacted trace files in a report.

## Operational guidance

- Do not bind the server to a public interface or place it behind a public proxy.
- Keep hosted case and suggestion responses `no-store`. Do not add analytics
  that capture address values or request bodies.
- Do not add a hosted model endpoint without a separate privacy, abuse, cost,
  retention, and threat review.
- Review every dataset and field change against `docs/data-treatment.md`.
- Keep `SHAKTI_HERMES_ENABLED` unset until the runtime, model, and memory limits
  have passed a traced acceptance run.
- Treat local trace files as potentially sensitive operational records even
  though the application redacts and hashes resident input.
