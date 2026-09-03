"""Windows build script: installs runtime deps and packages LUNA.exe.

Usage:
    python scripts/build_windows.py [--skip-install]

Output:
    dist/LUNA/LUNA.exe  (portable one-folder build)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "build" / "luna.spec"

REQUIRED = [
    "PySide6",
    "playwright",
    "onnxruntime",
    "kokoro-onnx",
    "misaki[en]",
    "pyautogui",
    "pyperclip",
    "pillow",
    "httpx",
    "numpy",
    "uiautomation",
    "pywin32",
    "pyinstaller",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-install", action="store_true")
    args = parser.parse_args()

    if not sys.platform.startswith("win"):
        print("NOTE: packaging is Windows-targeted; running on this platform anyway.")

    if not args.skip_install:
        print("Installing build dependencies…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", *REQUIRED])
        print("Installing Chromium for Playwright (headless safe-fallbacks excluded from the build)…")
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])

    print("Building LUNA with PyInstaller…")
    subprocess.check_call([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(SPEC)])

    exe = ROOT / "dist" / "LUNA" / "LUNA.exe"
    if not exe.exists():
        print(f"ERROR: expected executable not found at {exe}", file=sys.stderr)
        return 1
    print(f"OK: {exe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
