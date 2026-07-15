"""Run the reproducible Shaki Seva Day 0 acceptance checks."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.request
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from websockets.sync.client import connect


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PYTHON = ROOT / ".venv" / "bin" / "python"
PYTHON = str(LOCAL_PYTHON if LOCAL_PYTHON.exists() else Path(sys.executable))
LOCAL_SHAKI = ROOT / ".venv" / "bin" / "shaki"
SHAKI = str(LOCAL_SHAKI if LOCAL_SHAKI.exists() else shutil.which("shaki") or "shaki")
UNIT_PATTERNS = (
    re.compile(r"\bAPT\.?\s*[A-Z0-9-]+\b", re.IGNORECASE),
    re.compile(r"\bUNIT\s*[#.]?\s*[A-Z0-9-]+\b", re.IGNORECASE),
    re.compile(r"LOCATED\s+AT\s+(?:APT|APARTMENT|UNIT)\b", re.IGNORECASE),
)


@dataclass
class Check:
    name: str
    status: str
    detail: str
    duration_ms: float


def command(*args: str, timeout: float = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)


def free_port() -> int:
    with closing(socket.socket()) as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


def wait_for_health(port: int, timeout: float = 10) -> dict:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/api/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                return json.load(response)
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("loopback health endpoint did not become ready")


def check_installed_command() -> str:
    result = command(PYTHON, "-c", "import shaki_seva; print(shaki_seva.__file__)")
    if result.returncode != 0 or "src/shaki_seva" not in result.stdout:
        raise RuntimeError(result.stderr.strip() or "editable package import failed")
    return result.stdout.strip()


def check_tests() -> str:
    result = command(PYTHON, "-m", "pytest", timeout=120)
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout.strip().splitlines()[-1]


def check_doctor() -> str:
    result = command(SHAKI, "doctor")
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    report = json.loads(result.stdout)
    if not report["hermes"]["ready"] or not report["trace_writable"]:
        raise RuntimeError("Hermes interfaces or trace storage are not ready")
    return report["hermes"]["version"]


def check_interface(interface: str) -> str:
    result = command(SHAKI, "hermes", f"--{interface}", "--print-command")
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    contract = json.loads(result.stdout)
    if contract["environment"]["HERMES_STARTUP_MINIMUM_CONTEXT_LENGTH"] != "32000":
        raise RuntimeError("the governed 32K startup limit is missing")
    if "HERMES_ALLOW_LOW_CONTEXT_COMPRESSION_THRESHOLD" not in contract["environment"]:
        raise RuntimeError("the low-context compression control is missing")
    if f"--{interface}" not in contract["command"]:
        raise RuntimeError(f"the Hermes {interface} flag is missing")
    return json.dumps(contract, sort_keys=True)


def check_fixture_and_trace() -> str:
    result = command(SHAKI, "case", "--fixture")
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    report = json.loads(result.stdout)
    case = report["case"]
    text = json.dumps(case, sort_keys=True)
    if case["next_step"]["code"] != "urgent_hpd_follow_up":
        raise RuntimeError("fixture did not take the expected deterministic route")
    if any(pattern.search(text) for pattern in UNIT_PATTERNS):
        raise RuntimeError("fixture packet contains a unit identifier")
    trace_path = Path(report["trace_path"])
    verified = command(SHAKI, "trace", "verify", str(trace_path))
    trace_path.unlink(missing_ok=True)
    if verified.returncode != 0:
        raise RuntimeError(verified.stdout + verified.stderr)
    return f"{verified.stdout.strip()}; route={case['next_step']['code']}"


def check_public_bind_refused() -> str:
    result = command(SHAKI, "serve", "--host", "0.0.0.0")
    if result.returncode == 0 or "loopback only" not in result.stderr:
        raise RuntimeError("public bind was not refused")
    return result.stderr.strip()


def check_server_and_socket() -> str:
    port = free_port()
    process = subprocess.Popen(
        [SHAKI, "serve", "--port", str(port)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        health = wait_for_health(port)
        if health.get("status") != "ok" or not health.get("loopback_only"):
            raise RuntimeError("health response did not preserve the loopback contract")
        with connect(f"ws://127.0.0.1:{port}/ws", origin=f"http://127.0.0.1:{port}") as websocket:
            ready = json.loads(websocket.recv(timeout=5))
            websocket.send(json.dumps({"type": "fixture"}))
            progress = json.loads(websocket.recv(timeout=5))
            case = json.loads(websocket.recv(timeout=5))
        if ready.get("type") != "connection" or progress.get("stage") != "curating":
            raise RuntimeError("socket progress contract failed")
        if case.get("type") != "case" or len(case.get("trace", [])) != 4:
            raise RuntimeError("socket fixture or trace contract failed")
        return "health ok; same-origin socket ready; fixture returned 4 trace events"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def check_published_evidence() -> str:
    screenshots = ROOT / "docs" / "assets" / "screenshots"
    images = [
        screenshots / "hermes-tui.png",
        screenshots / "web-case.png",
        screenshots / "web-evidence.png",
        screenshots / "web-trace.png",
        ROOT / "docs" / "assets" / "shaki-seva-day0-poster.png",
    ]
    dimensions: list[str] = []
    for path in images:
        header = path.read_bytes()[:24]
        if header[:8] != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError(f"{path.name} is not a PNG")
        width, height = struct.unpack(">II", header[16:24])
        if width < 1000 or height < 700:
            raise RuntimeError(f"{path.name} is too small for review")
        dimensions.append(f"{path.name}={width}x{height}")
    video = ROOT / "docs" / "assets" / "shaki-seva-day0.mp4"
    if video.stat().st_size < 1_000_000 or video.read_bytes()[:12][4:8] != b"ftyp":
        raise RuntimeError("the published demo is missing or malformed")
    narration = ROOT / "demo" / "public" / "narration.wav"
    if narration.stat().st_size < 1_000_000 or narration.read_bytes()[:4] != b"RIFF":
        raise RuntimeError("the Liquid narration is missing or malformed")
    return "; ".join(dimensions) + "; MP4 and WAV signatures valid"


def run_check(name: str, action: Callable[[], str]) -> Check:
    started = time.monotonic()
    try:
        detail = action()
        status = "pass"
    except Exception as exc:
        detail = str(exc)
        status = "fail"
    detail = detail.replace(str(ROOT), ".").replace(str(Path.home()), "~")
    return Check(name, status, detail, round((time.monotonic() - started) * 1000, 2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Shaki Seva Day 0 evaluation")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "evals" / "day0.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    checks = [
        run_check("installed_command", check_installed_command),
        run_check("tests", check_tests),
        run_check("doctor", check_doctor),
        run_check("hermes_tui_contract", lambda: check_interface("tui")),
        run_check("hermes_cli_contract", lambda: check_interface("cli")),
        run_check("fixture_and_trace", check_fixture_and_trace),
        run_check("public_bind_refused", check_public_bind_refused),
        run_check("server_and_socket", check_server_and_socket),
        run_check("published_evidence", check_published_evidence),
    ]
    report = {
        "schema_version": "1.0",
        "suite": "day0",
        "generated_at": datetime.now(UTC).isoformat(),
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "passed": all(item.status == "pass" for item in checks),
        "checks": [asdict(item) for item in checks],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
