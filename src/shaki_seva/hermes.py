"""Narrow adapter around the installed Hermes CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .trace import TraceLedger, sha256_json


REQUIRED_HELP_MARKERS = ("--tui", "--cli", "--pass-session-id", "sessions", "serve", "logs")
REQUIRED_CHAT_MARKERS = ("--max-turns", "--checkpoints", "--source")


class HermesError(RuntimeError):
    pass


@dataclass(frozen=True)
class HermesStatus:
    executable: str | None
    version: str | None
    features: dict[str, bool]
    ready: bool
    enabled: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "executable": self.executable,
            "version": self.version,
            "features": self.features,
            "ready": self.ready,
            "enabled": self.enabled,
        }


class HermesRuntime:
    def __init__(self, executable: str = "hermes") -> None:
        self.requested_executable = executable
        self.executable = shutil.which(executable)

    def inspect(self) -> HermesStatus:
        enabled = os.getenv("SHAKI_HERMES_ENABLED") == "1"
        if not self.executable:
            return HermesStatus(None, None, {}, False, enabled)
        try:
            version = subprocess.run(
                [self.executable, "--version"], capture_output=True, text=True, timeout=10, check=False
            )
            help_result = subprocess.run(
                [self.executable, "--help"], capture_output=True, text=True, timeout=10, check=False
            )
            chat_help = subprocess.run(
                [self.executable, "chat", "--help"], capture_output=True, text=True, timeout=10, check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            return HermesStatus(self.executable, None, {}, False, enabled)
        help_text = help_result.stdout + help_result.stderr
        chat_text = chat_help.stdout + chat_help.stderr
        features = {marker: marker in help_text for marker in REQUIRED_HELP_MARKERS}
        features.update({marker: marker in chat_text for marker in REQUIRED_CHAT_MARKERS})
        ready = version.returncode == 0 and help_result.returncode == 0 and chat_help.returncode == 0 and all(features.values())
        first_line = (version.stdout + version.stderr).splitlines()
        return HermesStatus(
            self.executable,
            first_line[0].strip() if first_line else None,
            features,
            ready,
            enabled,
        )

    def interface_command(self, interface: str) -> list[str]:
        if not self.executable:
            raise HermesError("Hermes executable was not found")
        if interface not in {"tui", "cli"}:
            raise HermesError("interface must be tui or cli")
        return [
            self.executable,
            "chat",
            f"--{interface}",
            "--checkpoints",
            "--pass-session-id",
            "--source",
            "shaki-seva",
            "--max-turns",
            "6",
        ]

    def run_case(self, case: dict[str, Any], trace: TraceLedger, cwd: Path) -> str:
        status = self.inspect()
        trace.append("hermes.inspected", status.as_dict())
        if not status.ready:
            raise HermesError("Hermes CLI is not ready")
        if not status.enabled:
            raise HermesError("live Hermes explanations are disabled; set SHAKI_HERMES_ENABLED=1")
        prompt = (
            "Explain this curated public housing repair case packet in plain language. "
            "Use only the packet. Distinguish complaints from verified violations. "
            "Cite dataset IDs and finish with the supplied deterministic next step.\n\n"
            + json.dumps(case, sort_keys=True, ensure_ascii=False)
        )
        command = [
            self.executable or "hermes",
            "chat",
            "-q",
            prompt,
            "--checkpoints",
            "--pass-session-id",
            "--source",
            "shaki-seva",
            "--max-turns",
            "4",
            "--quiet",
        ]
        trace.append(
            "hermes.started",
            {"command": command[:3] + ["[curated prompt]"] + command[4:], "case_hash": sha256_json(case)},
        )
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            trace.append("hermes.failed", {"reason": "timeout", "timeout_seconds": 180})
            raise HermesError("Hermes explanation timed out") from exc
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        trace.append(
            "hermes.completed" if completed.returncode == 0 else "hermes.failed",
            {
                "exit_code": completed.returncode,
                "stdout_hash": sha256_json({"stdout": stdout}),
                "stdout_chars": len(stdout),
                "stderr_hash": sha256_json({"stderr": stderr}),
                "stderr_chars": len(stderr),
            },
        )
        if completed.returncode != 0:
            raise HermesError("Hermes explanation failed; inspect the trace and Hermes logs")
        return stdout
