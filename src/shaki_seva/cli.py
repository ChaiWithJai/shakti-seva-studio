"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import uvicorn

from .data import CaseService, SocrataClient
from .hermes import HermesRuntime
from .server import FIXTURE, ROOT, TRACES
from .trace import TraceLedger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shaki", description="Governed NYC housing repair record assistant")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="Validate Hermes interfaces and trace storage")

    case = subparsers.add_parser("case", help="Build a curated case packet")
    case.add_argument("--fixture", action="store_true", help="Use the synthetic fixture")
    case.add_argument("--borough")
    case.add_argument("--house-number")
    case.add_argument("--street-name")
    case.add_argument("--hermes", action="store_true", help="Ask Hermes to explain the curated packet")

    hermes = subparsers.add_parser("hermes", help="Launch Hermes in the governed workspace")
    interface = hermes.add_mutually_exclusive_group(required=True)
    interface.add_argument("--tui", action="store_true")
    interface.add_argument("--cli", action="store_true")
    hermes.add_argument("--print-command", action="store_true", help="Print rather than execute the command")

    serve = subparsers.add_parser("serve", help="Run the loopback web and WebSocket server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)

    trace = subparsers.add_parser("trace", help="Trace utilities")
    trace_subparsers = trace.add_subparsers(dest="trace_command", required=True)
    verify = trace_subparsers.add_parser("verify")
    verify.add_argument("path", type=Path)
    return parser


def doctor() -> int:
    status = HermesRuntime().inspect()
    TRACES.mkdir(parents=True, exist_ok=True)
    probe = TRACES / ".write-probe"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()
    report = {
        "hermes": status.as_dict(),
        "trace_directory": str(TRACES),
        "trace_writable": True,
        "websocket_endpoint": "ws://127.0.0.1:8765/ws",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if status.ready else 1


def build_case(args: argparse.Namespace) -> int:
    ledger = TraceLedger(TRACES)
    service = CaseService(SocrataClient(), ledger)
    if args.fixture:
        case = service.build_from_fixture(FIXTURE)
    else:
        if not all((args.borough, args.house_number, args.street_name)):
            raise SystemExit("case requires --fixture or borough, house number, and street name")
        buildings = service.resolve_building(args.borough, args.house_number, args.street_name)
        if len(buildings) != 1:
            print(json.dumps({"trace_id": ledger.trace_id, "building_candidates": buildings}, indent=2))
            return 2
        case = service.build_for_building(buildings[0])
    result: dict[str, object] = {"case": case, "trace_path": str(ledger.path)}
    if args.hermes:
        result["hermes_explanation"] = HermesRuntime().run_case(case, ledger, ROOT)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        return doctor()
    if args.command == "case":
        return build_case(args)
    if args.command == "hermes":
        runtime = HermesRuntime()
        command = runtime.interface_command("tui" if args.tui else "cli")
        if args.print_command:
            print(json.dumps(command))
            return 0
        os.chdir(ROOT)
        os.execv(command[0], command)
    if args.command == "serve":
        if args.host not in {"127.0.0.1", "localhost", "::1"}:
            raise SystemExit("Shaki binds to loopback only")
        uvicorn.run("shaki_seva.server:app", host=args.host, port=args.port, reload=False)
        return 0
    if args.command == "trace" and args.trace_command == "verify":
        valid, message = TraceLedger.verify(args.path)
        print(message)
        return 0 if valid else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
