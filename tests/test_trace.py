import json
from pathlib import Path

from shakti_seva.trace import TraceLedger


def test_trace_chain_verifies_and_detects_tampering(tmp_path: Path) -> None:
    ledger = TraceLedger(tmp_path, "test-trace")
    ledger.append("case.started", {"apartment": "4A", "safe": "yes"})
    ledger.append("case.completed", {"count": 1})

    valid, message = TraceLedger.verify(ledger.path)
    assert valid is True
    assert message == "verified 2 events"
    first = json.loads(ledger.path.read_text().splitlines()[0])
    assert first["payload"]["apartment"] == "[redacted]"

    lines = ledger.path.read_text().splitlines()
    changed = json.loads(lines[1])
    changed["payload"]["count"] = 2
    lines[1] = json.dumps(changed)
    ledger.path.write_text("\n".join(lines) + "\n")
    valid, message = TraceLedger.verify(ledger.path)
    assert valid is False
    assert "invalid event hash" in message
