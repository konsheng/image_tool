from __future__ import annotations

def run_app() -> int:
    from gui import run_app as launch_gui

    return launch_gui()


def main() -> int:
    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
