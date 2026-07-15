"""Create a working development environment and verify the installed CLI."""

from __future__ import annotations

import glob
import platform
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "bin" / "python"


def run(*command: str) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    if not PYTHON.exists():
        run("uv", "venv", "--python", "3.13", ".venv")
    run("uv", "pip", "install", "--python", str(PYTHON), "-e", ".[dev]")

    # Python 3.13 skips .pth files with the macOS hidden flag. Some external
    # APFS volumes add that flag to uv's editable-install path file.
    if platform.system() == "Darwin":
        site_packages = ROOT / ".venv" / "lib" / "python3.13" / "site-packages"
        for path in glob.glob(str(site_packages / "*.pth")):
            subprocess.run(["chflags", "nohidden", path], check=False)

    run(str(PYTHON), "-c", "import shaki_seva; print(shaki_seva.__file__)")
    run(str(ROOT / ".venv" / "bin" / "shaki"), "doctor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
