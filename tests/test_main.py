from __future__ import annotations

import unittest
from types import ModuleType
from unittest.mock import patch

import main


class MainRoutingTestCase(unittest.TestCase):
    def test_default_route_runs_the_gui_and_returns_its_exit_code(self) -> None:
        fake_gui = ModuleType("gui")
        run_app = unittest.mock.Mock(return_value=17)
        fake_gui.run_app = run_app  # type: ignore[attr-defined]
        with (
            patch.object(main, "run_blind_watermark_self_test") as run_self_test,
            patch.dict(main.sys.modules, {"gui": fake_gui}),
        ):
            exit_code = main.main([])

        self.assertEqual(exit_code, 17)
        run_app.assert_called_once_with()
        run_self_test.assert_not_called()

    def test_blind_watermark_self_test_flag_bypasses_the_gui(self) -> None:
        fake_gui = ModuleType("gui")
        run_app = unittest.mock.Mock()
        fake_gui.run_app = run_app  # type: ignore[attr-defined]
        with (
            patch.object(
                main,
                "run_blind_watermark_self_test",
                return_value=0,
            ) as run_self_test,
            patch.dict(main.sys.modules, {"gui": fake_gui}),
        ):
            exit_code = main.main(["--self-test-blind-watermark"])

        self.assertEqual(exit_code, 0)
        run_self_test.assert_called_once_with()
        run_app.assert_not_called()

    def test_blind_watermark_self_test_failure_exit_code_is_preserved(self) -> None:
        fake_gui = ModuleType("gui")
        run_app = unittest.mock.Mock()
        fake_gui.run_app = run_app  # type: ignore[attr-defined]
        with (
            patch.object(
                main,
                "run_blind_watermark_self_test",
                return_value=1,
            ) as run_self_test,
            patch.dict(main.sys.modules, {"gui": fake_gui}),
        ):
            exit_code = main.main(["--self-test-blind-watermark"])

        self.assertEqual(exit_code, 1)
        run_self_test.assert_called_once_with()
        run_app.assert_not_called()

    def test_main_uses_process_arguments_when_argv_is_omitted(self) -> None:
        fake_gui = ModuleType("gui")
        run_app = unittest.mock.Mock()
        fake_gui.run_app = run_app  # type: ignore[attr-defined]
        with (
            patch.object(
                main,
                "run_blind_watermark_self_test",
                return_value=0,
            ) as run_self_test,
            patch.dict(main.sys.modules, {"gui": fake_gui}),
            patch.object(
                main.sys,
                "argv",
                ["image-tool.exe", "--self-test-blind-watermark"],
            ),
        ):
            exit_code = main.main()

        self.assertEqual(exit_code, 0)
        run_self_test.assert_called_once_with()
        run_app.assert_not_called()


if __name__ == "__main__":
    unittest.main()
