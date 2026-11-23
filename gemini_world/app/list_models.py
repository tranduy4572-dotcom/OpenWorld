"""List the model names that this Gemini key can discover (never print key)."""
from __future__ import annotations
import json
import os
import sys
sys.dont_write_bytecode = True
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from pathlib import Path
from gemini_api import load_local_env

def main():
    load_local_env(Path(__file__).resolve().parent.parent)
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key or key.startswith("YOUR_") or key.startswith("THAY_") or " " in key:
        print("[LOI] Tao .env va thay GEMINI_API_KEY bang khoa API that.")
        return 1
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000"
        with urlopen(Request(url, headers={"x-goog-api-key": key}), timeout=25) as resp:
            data = json.load(resp)
        usable = [m.get("name", "") for m in data.get("models", [])
                  if "generateContent" in m.get("supportedGenerationMethods", [])]
        print("MODEL CO THE GOI generateContent (chua xac nhan quota):")
        for name in sorted(usable):
            print(" -", name.removeprefix("models/"))
        print("Tong so:", len(usable))
        return 0
    except HTTPError as err:
        content = err.read(500).decode("utf-8", "replace").replace(key, "[REDACTED]")
        print("HTTP", err.code, content)
        return 1
    except (URLError, TimeoutError, ValueError) as err:
        print("Khong ket noi duoc:", type(err).__name__)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
