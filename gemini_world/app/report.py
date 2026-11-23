"""Write a local, read-only replay of actual executed OpenWorld lab turns."""
from __future__ import annotations

import json
from pathlib import Path


def write_report(dest: Path, records: list[dict]) -> None:
    template = (Path(__file__).parent / "viewer_template.html").read_text(encoding="utf-8")
    # Prevent model-supplied text from closing the JSON script tag.
    safe_json = json.dumps(records, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    dest.write_text(template.replace("__OPENWORLD_TRACE_JSON__", safe_json), encoding="utf-8")
