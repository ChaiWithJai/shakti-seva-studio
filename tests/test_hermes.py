from pathlib import Path

from shaki_seva.hermes import HermesRuntime
from shaki_seva.trace import TraceLedger


FAKE_HERMES = '''#!/bin/sh
if [ "$1" = "--version" ]; then
  echo "Hermes Agent v0.test"
  exit 0
fi
if [ "$1" = "chat" ] && [ "$2" = "--help" ]; then
  echo "--max-turns --checkpoints --source"
  exit 0
fi
if [ "$1" = "chat" ] && [ "$2" = "-q" ]; then
  echo "This is a bounded explanation from the curated packet."
  exit 0
fi
echo "--tui --cli --pass-session-id sessions serve logs"
'''


def test_hermes_runtime_validates_required_interfaces(tmp_path: Path, monkeypatch) -> None:
    executable = tmp_path / "hermes"
    executable.write_text(FAKE_HERMES)
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}")
    monkeypatch.delenv("SHAKI_HERMES_ENABLED", raising=False)

    runtime = HermesRuntime()
    status = runtime.inspect()
    assert status.ready is True
    assert status.enabled is False
    assert "--tui" in status.features
    assert runtime.interface_command("tui")[-2:] == ["--max-turns", "6"]
    assert runtime.interface_environment() == {
        "HERMES_STARTUP_MINIMUM_CONTEXT_LENGTH": "32000",
        "HERMES_ALLOW_LOW_CONTEXT_COMPRESSION_THRESHOLD": "1",
    }


def test_hermes_adapter_runs_curated_packet_and_traces_it(tmp_path: Path, monkeypatch) -> None:
    executable = tmp_path / "hermes"
    executable.write_text(FAKE_HERMES)
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("SHAKI_HERMES_ENABLED", "1")

    ledger = TraceLedger(tmp_path / "traces")
    answer = HermesRuntime().run_case(
        {"schema_version": "1.0", "sources": [{"dataset_id": "synthetic"}], "next_step": {"code": "test"}},
        ledger,
        tmp_path,
    )

    assert answer.startswith("This is a bounded explanation")
    assert [event["kind"] for event in ledger.events] == [
        "hermes.inspected",
        "hermes.started",
        "hermes.completed",
    ]
    assert "curated prompt" in str(ledger.events[1]["payload"])
