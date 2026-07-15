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

`shakti doctor` repeats the executable and feature checks on the current
machine. It also verifies that the trace directory is writable.

The automated suite also runs the complete adapter against a controlled fake
Hermes process and verifies `hermes.inspected`, `hermes.started`, and
`hermes.completed` trace events. This proves the subprocess and trace boundary
without placing the laptop under model load.

The actual modern TUI was also launched in a pseudo-terminal. The governed
wrapper supplied a 32K startup floor and permission for a lower compression
threshold. The TUI reached its ready state with tools, skills, and MCP support
loaded. The captured frame is in the [Day 0 guide](day-0.md).

This proves interface startup. It does not validate a local model response,
32K inference pressure, tool selection, compaction quality, or the quality of a
resident-facing answer. Those require separate traced acceptance runs with
tested memory limits.
