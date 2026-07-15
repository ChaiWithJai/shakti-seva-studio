# Security policy

## Prototype boundary

Shaki Seva Studio is a local public-interest technology prototype, not an
official City service. It binds to loopback, requires same-origin WebSocket
handshakes, and keeps live Hermes execution off by default.

Do not enter apartment numbers, resident names, contact information, case
narratives, or other sensitive data. Use only the building-level address fields
shown in the interface.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository. Do not
include resident data, access tokens, or unredacted trace files in a report.

## Operational guidance

- Do not bind the server to a public interface or place it behind a public proxy.
- Review every dataset and field change against `docs/data-treatment.md`.
- Keep `SHAKI_HERMES_ENABLED` unset until the runtime, model, and memory limits
  have passed a traced acceptance run.
- Treat local trace files as potentially sensitive operational records even
  though the application redacts and hashes resident input.
