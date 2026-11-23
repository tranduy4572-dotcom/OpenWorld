"""One local launcher for the Gemini/OpenWorld lab and its existing tools."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import webbrowser

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


def latest_report(root: Path = ROOT) -> Path | None:
    candidates = [path for path in (root / "runs").glob("*/XEM_DU_LIEU.html")
                  if (path.parent / "trace.jsonl").is_file()]
    return max(candidates, key=lambda path: path.stat().st_mtime_ns, default=None)


def run_tool(choice: str) -> int:
    commands = {
        "1": ["app/agent_lab.py", "--mode", "gemini", "--steps", "6", "--fresh"],
        "2": ["app/agent_lab.py", "--mode", "offline", "--steps", "6", "--auto", "--fresh"],
        "3": ["app/list_models.py"],
        "4": ["app/verify_integration.py"],
        "5": ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
    }
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run([sys.executable, "-B", *commands[choice]], cwd=ROOT,
                          env=environment, check=False).returncode


def main() -> int:
    if sys.version_info < (3, 11):
        print("Can Python 3.11 tro len.")
        return 1
    while True:
        print("\n=== GEMINI + OPENWORLD ===")
        print("1. Chay Gemini that (can key trong .env)")
        print("2. Chay mo phong OFFLINE (khong goi API)")
        print("3. Xem danh sach model Gemini (can key)")
        print("4. Kiem tra ket noi OpenWorld")
        print("5. Chay tests cuc bo (khong goi API that)")
        print("6. Mo bao cao HTML moi nhat")
        print("0. Thoat")
        try:
            choice = input("Chon so, roi nhan Enter: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if choice == "0":
            return 0
        if choice == "6":
            report = latest_report()
            if report is None:
                print("Chua co bao cao. Chay lua chon 2 de tao demo offline.")
            else:
                print("Bao cao:", report)
                if not webbrowser.open(report.resolve().as_uri()):
                    print("Hay mo file HTML tren bang trinh duyet.")
        elif choice in {"1", "2", "3", "4", "5"}:
            try:
                code = run_tool(choice)
                print("\nHoan tat." if code == 0 else f"\nTac vu dung voi ma {code}; xem loi phia tren.")
            except KeyboardInterrupt:
                print("\nDa ngat tac vu; quay lai menu.")
        else:
            print("Lua chon khong hop le. Nhap so 0 den 6.")


if __name__ == "__main__":
    raise SystemExit(main())
