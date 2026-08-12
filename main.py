from __future__ import annotations

import sys
from collections.abc import Sequence

from blind_watermark_service import run_blind_watermark_self_test


def run_app() -> int:
    from gui import run_app as launch_gui

    return launch_gui()


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == ["--self-test-blind-watermark"]:
        return run_blind_watermark_self_test()
    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
