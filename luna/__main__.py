"""LUNA Desktop entry point.

Usage:
    python -m luna [--home PATH] [--minimized]
"""

from __future__ import annotations

import argparse
import logging
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="luna", description="LUNA Desktop — local-first AI assistant")
    parser.add_argument("--home", help="Override LUNA_HOME (default: platform app-data dir).")
    parser.add_argument("--minimized", action="store_true", help="Start minimized to the system tray.")
    parser.add_argument("--smoke-test", action="store_true", help="Initialize services and exit (CI smoke test).")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    try:
        from luna.app.application import Application

        app_core = Application(args.home)
    except Exception as exc:  # noqa: BLE001
        logging.error("LUNA failed to initialize: %s", exc)
        return 1

    if args.smoke_test:
        print("LUNA smoke test OK: paths, settings, sqlite, tasks, models, voices initialized.")
        app_core.shutdown()
        return 0

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "PySide6 is required for the LUNA desktop UI.\n"
            "Install with: pip install luna-desktop[ui]",
            file=sys.stderr,
        )
        return 1

    from luna.ui.main_window import MainWindow

    qt_app = QApplication(sys.argv[:1])
    qt_app.setApplicationName("LUNA")
    qt_app.setOrganizationName("LUNA")
    window = MainWindow(app_core, minimized=args.minimized)
    window.show()
    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
