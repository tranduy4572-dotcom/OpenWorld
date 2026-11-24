"""Exercise the launcher from a different cwd without calling a live model."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from menu import latest_report


class MenuTests(unittest.TestCase):
    def launch(self, answers):
        with tempfile.TemporaryDirectory() as directory:
            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            return subprocess.run([sys.executable, "-B", str(ROOT / "app/menu.py")],
                                  cwd=directory, env=environment, input=answers,
                                  capture_output=True, text=True, encoding="utf-8", timeout=30)

    def test_menu_can_exit_from_an_unrelated_working_directory(self):
        result = self.launch("0\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("GEMINI + OPENWORLD", result.stdout)

    def test_unknown_option_returns_to_menu(self):
        result = self.launch("not-a-choice\n0\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Lua chon khong hop le", result.stdout)

    def test_connection_option_launches_the_actual_checker(self):
        result = self.launch("4\n0\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Import cac module goc THANH CONG", result.stdout)

    def test_latest_report_requires_trace_and_uses_newest_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "runs/first/XEM_DU_LIEU.html"
            second = root / "runs/second/XEM_DU_LIEU.html"
            unrelated = root / "runs/unrelated/XEM_DU_LIEU.html"
            for report in (first, second, unrelated):
                report.parent.mkdir(parents=True)
                report.write_text("report", encoding="utf-8")
            for report in (first, second):
                (report.parent / "trace.jsonl").write_text("{}\n", encoding="utf-8")
            os.utime(first, ns=(1_000_000, 1_000_000))
            os.utime(second, ns=(2_000_000, 2_000_000))
            os.utime(unrelated, ns=(3_000_000, 3_000_000))
            self.assertEqual(latest_report(root), second)

    def test_no_saved_report_is_handled(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(latest_report(Path(directory)))


if __name__ == "__main__":
    unittest.main()
