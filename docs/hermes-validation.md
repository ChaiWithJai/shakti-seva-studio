# Hermes validation

The local runtime was inspected before integration.

Observed runtime:

- Hermes Agent `0.18.2` (`2026.7.7.2`)
- upstream `6997dc81`, local build `7e84d2b5` with one carried commit
- classic CLI through `hermes --cli`
- modern TUI through `hermes --tui`
- headless backend through `hermes serve`
- local JSON-RPC/WebSocket endpoint at `/api/ws`
- session source tags, session IDs, checkpoints, logs, and bounded turns

`shaki doctor` repeats the executable and feature checks on the current
machine. It also verifies that the trace directory is writable.

The automated suite also runs the complete adapter against a controlled fake
Hermes process and verifies `hermes.inspected`, `hermes.started`, and
`hermes.completed` trace events. This proves the subprocess and trace boundary
without placing the laptop under model load.

It does not validate a local model, 32K inference, tool selection, or the
quality of a resident-facing answer. Those require separate traced acceptance
runs on a runtime with tested memory limits.
