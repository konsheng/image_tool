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
        with patch.dict("sys.modules", {"gui": fake_gui}):
            exit_code = main.main()

        self.assertEqual(exit_code, 17)
        run_app.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
