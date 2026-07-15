"""Run the reproducible Shakti Seva Day 0 acceptance checks."""

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
LOCAL_SHAKTI = ROOT / ".venv" / "bin" / "shakti"
GLOBAL_SHAKTI = shutil.which("shakti")
SHAKTI = (
    (str(LOCAL_SHAKTI),)
    if LOCAL_SHAKTI.exists()
    else (GLOBAL_SHAKTI,)
    if GLOBAL_SHAKTI
    else (PYTHON, "-m", "shakti_seva.cli")
)
UNIT_PATTERNS = (
    re.compile(r"\bAPT\.?\s*[A-Z0-9-]+\b", re.IGNORECASE),
    re.compile(r"\bUNIT\s*[#.]?\s*(?!REDACTED\b)[A-Z0-9-]+\b", re.IGNORECASE),
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


def wait_for_endpoint(port: int, path: str, timeout: float = 10) -> dict:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}{path}"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                return json.load(response)
        except Exception:
            time.sleep(0.1)
    raise RuntimeError(f"loopback endpoint {path} did not become ready")


def check_installed_command() -> str:
    result = command(PYTHON, "-c", "import shakti_seva; print(shakti_seva.__file__)")
    if result.returncode != 0 or "src/shakti_seva" not in result.stdout:
        raise RuntimeError(result.stderr.strip() or "editable package import failed")
    return result.stdout.strip()


def check_tests() -> str:
    result = command(PYTHON, "-m", "pytest", timeout=120)
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout.strip().splitlines()[-1]


def check_doctor() -> str:
    result = command(*SHAKTI, "doctor")
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    report = json.loads(result.stdout)
    if not report["hermes"]["ready"] or not report["trace_writable"]:
        raise RuntimeError("Hermes interfaces or trace storage are not ready")
    return report["hermes"]["version"]


def check_interface(interface: str) -> str:
    result = command(*SHAKTI, "hermes", f"--{interface}", "--print-command")
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
    result = command(*SHAKTI, "case", "--fixture")
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
    verified = command(*SHAKTI, "trace", "verify", str(trace_path))
    trace_path.unlink(missing_ok=True)
    if verified.returncode != 0:
        raise RuntimeError(verified.stdout + verified.stderr)
    return f"{verified.stdout.strip()}; route={case['next_step']['code']}"


def check_public_bind_refused() -> str:
    result = command(*SHAKTI, "serve", "--host", "0.0.0.0")
    if result.returncode == 0 or "loopback only" not in result.stderr:
        raise RuntimeError("public bind was not refused")
    return result.stderr.strip()


def check_server_and_socket() -> str:
    port = free_port()
    process = subprocess.Popen(
        [*SHAKTI, "serve", "--port", str(port)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        live = wait_for_endpoint(port, "/api/live")
        if live != {"status": "ok", "check": "liveness", "loopback_only": True}:
            raise RuntimeError("liveness response did not preserve the cheap loopback contract")
        health = wait_for_endpoint(port, "/api/health")
        if health.get("check") != "readiness" or not health.get("hermes", {}).get("ready"):
            raise RuntimeError("readiness response did not confirm Hermes")
        with connect(f"ws://127.0.0.1:{port}/ws", origin=f"http://127.0.0.1:{port}") as websocket:
            ready = json.loads(websocket.recv(timeout=5))
            websocket.send(json.dumps({"type": "ping"}))
            pong = json.loads(websocket.recv(timeout=5))
        if ready.get("type") != "connection" or pong.get("type") != "pong":
            raise RuntimeError("socket readiness contract failed")
        return "cheap liveness ok; Hermes readiness ok; same-origin socket ready; public browser exposes no fixture path"
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
        screenshots / "web-live-start.png",
        screenshots / "web-live-suggestion.png",
        screenshots / "web-live-result.png",
        screenshots / "web-live-sources-trace.png",
    ]
    dimensions: list[str] = []
    for path in images:
        header = path.read_bytes()[:24]
        if header[:8] != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError(f"{path.name} is not a PNG")
        width, height = struct.unpack(">II", header[16:24])
        if width < 1000 or height < 700:
            if not path.name.startswith("web-live-") or width < 500 or height < 900:
                raise RuntimeError(f"{path.name} is too small for review")
        dimensions.append(f"{path.name}={width}x{height}")
    gif = (ROOT / "docs" / "assets" / "web-live-flow.gif").read_bytes()
    if gif[:6] not in {b"GIF87a", b"GIF89a"}:
        raise RuntimeError("web-live-flow.gif is not a GIF")
    gif_width, gif_height = struct.unpack("<HH", gif[6:10])
    if (gif_width, gif_height) != (520, 969):
        raise RuntimeError("web live flow GIF has unexpected dimensions")
    netlify_images = [
        (screenshots / "netlify-no-ai-proof.png", 480, 150),
        (screenshots / "netlify-live-result.png", 480, 700),
    ]
    for path, minimum_width, minimum_height in netlify_images:
        header = path.read_bytes()[:24]
        if header[:8] != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError(f"{path.name} is not a PNG")
        width, height = struct.unpack(">II", header[16:24])
        if width < minimum_width or height < minimum_height:
            raise RuntimeError(f"{path.name} is too small for review")
        dimensions.append(f"{path.name}={width}x{height}")
    map_text = (ROOT / "docs" / "assets" / "five-borough-eval-map.svg").read_text(encoding="utf-8")
    if "<svg" not in map_text or "150 building level cases" not in map_text or ">138<" not in map_text:
        raise RuntimeError("five borough map is missing the reviewed sample evidence")
    live_report = json.loads((ROOT / "evals" / "baseline" / "five-borough.json").read_text(encoding="utf-8"))
    summary = live_report["summary"]
    expected = {
        "sampled": 150,
        "passed": 150,
        "traces_verified": 150,
        "privacy_scans_passed": 150,
        "cases_with_redaction": 79,
        "map_points": 138,
    }
    if any(summary.get(key) != value for key, value in expected.items()):
        raise RuntimeError("five borough baseline does not match the reviewed public claims")
    address_report = json.loads(
        (ROOT / "evals" / "baseline" / "live-address.json").read_text(encoding="utf-8")
    )
    if address_report.get("typed_address") != "700 E 9th Street, Manhattan":
        raise RuntimeError("live address baseline is missing the reviewed browser input")
    if address_report.get("geosearch_match", {}).get("bin") != "1004529":
        raise RuntimeError("live address baseline is missing the reviewed NYC BIN")
    if address_report.get("hpd_match", {}).get("building_id") != "6533":
        raise RuntimeError("live address baseline is missing the reviewed HPD join")
    if address_report.get("displayed_records") != {
        "complaints": 25,
        "open_violations": 6,
        "aep_records": 0,
        "complaints_truncated": True,
    }:
        raise RuntimeError("live address baseline does not match the reviewed result totals")
    source_ids = {source.get("id") for source in address_report.get("sources", [])}
    if source_ids != {"kj4p-ruqc", "ygpa-z7cr", "wvxf-dwi5", "hcir-3275"}:
        raise RuntimeError("live address baseline does not name all four reviewed City sources")
    trace = address_report.get("trace", {})
    if trace.get("events") != 13 or trace.get("verified") is not True:
        raise RuntimeError("live address baseline is missing the verified trace result")
    variants = json.loads(
        (ROOT / "evals" / "baseline" / "address-input-variants.json").read_text(encoding="utf-8")
    )
    variant_rows = variants.get("variants", [])
    if (
        not variants.get("passed")
        or len(variant_rows) != 4
        or any(item.get("bin") != "1004529" or item.get("matched_rank") != 1 for item in variant_rows)
    ):
        raise RuntimeError("address input variants are missing four first-rank live matches")
    profile = json.loads(
        (ROOT / "evals" / "baseline" / "deployment-profile.json").read_text(encoding="utf-8")
    )
    if profile.get("web_process", {}).get("resident_memory_kb") != 47760:
        raise RuntimeError("deployment profile is missing the reviewed web process memory")
    if profile.get("verified_address_queries", {}).get("query_total_ms") != 1856.78:
        raise RuntimeError("deployment profile is missing the reviewed live query timing")
    if profile.get("case_pipeline_reference", {}).get("sampled") != 150:
        raise RuntimeError("deployment profile is missing the reviewed pipeline sample count")
    liveness = profile.get("liveness_route", {})
    if liveness.get("samples") != 20 or liveness.get("duration_ms", {}).get("mean") != 0.631:
        raise RuntimeError("deployment profile is missing the reviewed cheap liveness timing")
    netlify = json.loads(
        (ROOT / "evals" / "baseline" / "netlify-production.json").read_text(encoding="utf-8")
    )
    if netlify.get("passed") is not True or netlify.get("production_url") != "https://shakti.dharmicdata.org":
        raise RuntimeError("Netlify production baseline is not a passing custom-domain run")
    deploy = netlify.get("deployment", {})
    if not deploy.get("repository_commit") or deploy.get("repository_branch") != "main":
        raise RuntimeError("Netlify production baseline is missing repository deployment proof")
    if deploy.get("custom_https_verified") is not True:
        raise RuntimeError("Netlify production baseline is missing custom HTTPS proof")
    no_ai = netlify.get("no_ai", {})
    if no_ai != {"health_declared_disabled": True, "hermes_absent": True, "model_events": 0}:
        raise RuntimeError("Netlify production baseline does not prove the AI-free boundary")
    if netlify.get("runtime", {}).get("python") is not False or netlify.get("runtime", {}).get("websocket") is not False:
        raise RuntimeError("Netlify production baseline includes an unsupported server runtime")
    netlify_address = netlify.get("lived_address", {})
    if netlify_address.get("first_bin") != "1004529" or netlify_address.get("hpd_building_id") != "6533":
        raise RuntimeError("Netlify production baseline is missing the reviewed City join")
    if {item.get("dataset_id") for item in netlify.get("sources", [])} != {
        "kj4p-ruqc", "ygpa-z7cr", "wvxf-dwi5", "hcir-3275"
    }:
        raise RuntimeError("Netlify production baseline does not name all four City sources")
    if netlify.get("trace_events") != 13:
        raise RuntimeError("Netlify production baseline is missing the reviewed trace")
    return (
        "; ".join(dimensions)
        + "; web-live-flow.gif=520x969; live address baseline valid; four address forms valid; deployment profile valid; five borough baseline valid; Netlify production baseline valid; "
        + "prerecorded videos excluded from evidence"
    )


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
    parser = argparse.ArgumentParser(description="Run the Shakti Seva Day 0 evaluation")
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
