"""Capture one real Hermes TUI frame and render it as publishable HTML."""

from __future__ import annotations

import argparse
import fcntl
import html
import os
import pty
import re
import select
import signal
import struct
import subprocess
import termios
import time
from pathlib import Path

import pyte


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PYTHON = ROOT / ".venv" / "bin" / "python"
LOCAL_SHAKTI = ROOT / ".venv" / "bin" / "shakti"
SHAKTI = [str(LOCAL_SHAKTI)] if LOCAL_SHAKTI.exists() else [str(LOCAL_PYTHON), "-m", "shakti_seva.cli"]


def sanitize(text: str) -> str:
    text = text.replace(str(ROOT), "~/shakti-seva-studio")
    text = text.replace(str(ROOT.parent), "~")
    text = re.sub(r"Session:\s*[0-9a-f]{8}", "Session: [redacted]", text, flags=re.IGNORECASE)
    text = text.replace("�", " ")
    return text.rstrip()


def capture(timeout: float = 25) -> str:
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 38, 120, 0, 0))
    process = subprocess.Popen(
        [*SHAKTI, "hermes", "--tui"],
        cwd=ROOT,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        start_new_session=True,
    )
    os.close(slave)
    screen = pyte.Screen(120, 38)
    stream = pyte.Stream(screen)
    deadline = time.monotonic() + timeout
    stable_since: float | None = None
    try:
        while time.monotonic() < deadline:
            readable, _, _ = select.select([master], [], [], 0.25)
            if readable:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    break
                if not data:
                    break
                stream.feed(data.decode("utf-8", errors="replace"))
            current = "\n".join(screen.display)
            if "ready" in current.lower() and "Available Tools" in current:
                stable_since = stable_since or time.monotonic()
                if time.monotonic() - stable_since > 1:
                    return sanitize(current)
        raise RuntimeError("Hermes TUI did not reach its ready state")
    finally:
        try:
            os.killpg(process.pid, signal.SIGINT)
            process.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            process.kill()
        os.close(master)


def render_html(frame: str, destination: Path) -> None:
    rows = html.escape(frame)
    document = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><link rel="icon" href="data:,"><title>Shakti Hermes TUI</title>
<style>
html,body{{margin:0;background:#1d1715;color:#f5e9df;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}
body{{display:grid;place-items:center;min-height:100vh;background:radial-gradient(circle at top,#4b3029,#1d1715 64%)}}
.window{{width:1280px;border:1px solid #815443;border-radius:18px;overflow:hidden;box-shadow:0 32px 90px #0009}}
.bar{{height:48px;background:#2c211e;display:flex;align-items:center;padding:0 18px;gap:9px;color:#cfae9d;font:14px ui-sans-serif,system-ui}}
.dot{{width:12px;height:12px;border-radius:50%}} .r{{background:#ed6a5e}} .y{{background:#f4bf4f}} .g{{background:#61c454}}
.title{{margin-left:12px}} pre{{margin:0;padding:30px 34px 36px;font-size:17px;line-height:1.42;white-space:pre;min-height:700px;background:#171210}}
.note{{position:fixed;right:24px;bottom:18px;color:#b99584;font:13px ui-sans-serif,system-ui}}
</style><body><div class="window"><div class="bar"><i class="dot r"></i><i class="dot y"></i><i class="dot g"></i><span class="title">Shakti Seva Studio · Hermes TUI · governed 32K mode</span></div><pre>{rows}</pre></div><div class="note">Local path and session ID treated for publication.</div></body></html>"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", type=Path, default=ROOT / "output" / "tui" / "hermes-tui.txt")
    parser.add_argument("--html", type=Path, default=ROOT / "output" / "tui" / "hermes-tui.html")
    args = parser.parse_args()
    frame = capture()
    args.text.parent.mkdir(parents=True, exist_ok=True)
    args.text.write_text(frame + "\n", encoding="utf-8")
    render_html(frame, args.html)
    print(args.text)
    print(args.html)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
