"""Gemini API adapter for an extension living inside OpenWorld_Clean/extensions/gemini_world (no SDK dependency).

The model can only PROPOSE a small structured action. All validation and world
mutations belong to OpenWorld's trusted Python process, never to the model.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import time
from urllib import error, request


class GeminiAPIError(RuntimeError):
    pass


def load_local_env(project_root: Path) -> None:
    """Load .env for the demo only; existing OS environment wins."""
    file = project_root / ".env"
    if not file.is_file():
        return
    for raw in file.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in {"GEMINI_API_KEY", "GEMINI_MODEL"}:
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _json_proposal(text: str) -> dict[str, str]:
    """Validate JSON envelope; action allowlists are enforced by world host."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GeminiAPIError("Gemini khong tra ve JSON hop le") from exc
    if not isinstance(data, dict) or type(data.get("action")) is not str:
        raise GeminiAPIError("JSON thieu action chuoi")
    action = data["action"].strip().lower()
    reason = str(data.get("reason", ""))[:200]
    return {"action": action, "reason": reason}


def gemini_proposal(prompt: str) -> dict:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()
    if not key or key.startswith("khóa_") or key.startswith("YOUR_") or key.startswith("THAY_"):
        raise GeminiAPIError("Thieu GEMINI_API_KEY that trong file .env")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,90}", model):
        raise GeminiAPIError("GEMINI_MODEL khong hop le")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json", "temperature": 0.2,
            "maxOutputTokens": 1024,
        },
    }, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=payload, method="POST", headers={
        "Content-Type": "application/json; charset=utf-8", "x-goog-api-key": key,
    })
    for attempt in range(3):
        try:
            with request.urlopen(req, timeout=50) as response:
                body = json.load(response)
            parts = body["candidates"][0]["content"]["parts"]
            raw = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
            proposal = _json_proposal(raw)
            return {"proposal": proposal, "source": "GEMINI_API", "model": model}
        except error.HTTPError as exc:
            snippet = exc.read(700).decode("utf-8", errors="replace").replace(key, "[REDACTED]")
            if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise GeminiAPIError(
                f"Gemini HTTP {exc.code}: {snippet[:400]}. "
                "Kiem tra model, key va han muc. KHONG gui key cho nguoi khac."
            ) from None
        except (error.URLError, TimeoutError) as exc:
            raise GeminiAPIError(f"Khong ket noi duoc Gemini: {type(exc).__name__}") from None
        except (KeyError, IndexError, TypeError) as exc:
            raise GeminiAPIError("Gemini khong co noi dung JSON trong candidates") from exc
    raise GeminiAPIError("Gemini API tam thoi khong phan hoi")


def offline_proposal(actor: str, own_balance: int, bob_balance: int, target: int) -> dict:
    """A clear baseline to verify integration BEFORE supplying an API key."""
    if actor == "bob":
        action = "signal" if bob_balance < target else "hold"
        reason = "Can them tai nguyen" if action == "signal" else "Da du tai nguyen"
    else:
        action = "transfer" if own_balance > 0 and bob_balance < target else "hold"
        reason = "Chuyen 1 tai nguyen" if action == "transfer" else "Khong can chuyen"
    return {"proposal": {"action": action, "reason": reason},
            "source": "OFFLINE_RULES", "model": None}
