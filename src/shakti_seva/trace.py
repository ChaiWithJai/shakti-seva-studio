"""Hash-chained local trace ledger."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


SENSITIVE_KEYS = {
    "apartment",
    "unit",
    "resident_name",
    "email",
    "phone",
    "message",
    "free_text",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[redacted]" if str(key).lower() in SENSITIVE_KEYS else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize(item) for item in value]
    return value


class TraceLedger:
    def __init__(self, directory: Path, trace_id: str | None = None) -> None:
        self.trace_id = trace_id or str(uuid4())
        self.directory = directory
        self.path = directory / f"{self.trace_id}.jsonl"
        self.events: list[dict[str, Any]] = []
        self.previous_hash: str | None = None
        directory.mkdir(parents=True, exist_ok=True)

    def append(self, kind: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {
            "trace_id": self.trace_id,
            "sequence": len(self.events) + 1,
            "timestamp": datetime.now(UTC).isoformat(),
            "kind": kind,
            "payload": sanitize(payload or {}),
            "previous_hash": self.previous_hash,
        }
        event["event_hash"] = sha256_json(event)
        self.previous_hash = event["event_hash"]
        self.events.append(event)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(canonical_json(event) + "\n")
        return event

    @staticmethod
    def verify(path: Path) -> tuple[bool, str]:
        previous_hash: str | None = None
        expected_sequence = 1
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            return False, f"cannot read trace: {exc}"
        if not lines:
            return False, "trace is empty"
        for line_number, line in enumerate(lines, start=1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                return False, f"line {line_number} is not JSON: {exc}"
            if event.get("sequence") != expected_sequence:
                return False, f"line {line_number} has an invalid sequence"
            if event.get("previous_hash") != previous_hash:
                return False, f"line {line_number} breaks the previous hash chain"
            claimed_hash = event.pop("event_hash", None)
            calculated_hash = sha256_json(event)
            if claimed_hash != calculated_hash:
                return False, f"line {line_number} has an invalid event hash"
            previous_hash = claimed_hash
            expected_sequence += 1
        return True, f"verified {len(lines)} events"
