"""Locate the original OpenWorld tree without copying or changing its code."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

REQUIRED_FILES = (
    "pyproject.toml",
    "src/openworld_superkernel/world_fixture.py",
    "src/openworld_superkernel/world_guard.py",
    "src/openworld_superkernel/trust_boundaries.py",
    "src/openworld_superkernel/world_persistence.py",
    "src/openworld_superkernel/hyper_memory_p1e.py",
    "src/openworld_superkernel/memory_contracts.py",
)


def _checked_root(value: str, addon: Path, source: str) -> Path:
    root = Path(value).expanduser()
    if not root.is_absolute():
        root = addon / root
    root = root.resolve()
    missing = [name for name in REQUIRED_FILES if not (root / name).is_file()]
    if missing:
        raise RuntimeError(
            f"{source} tro sai thu muc OpenWorld: {root}. Thieu: "
            + ", ".join(missing)
        )
    return root


def resolve_openworld_root(addon_dir: Path | None = None) -> Path:
    addon = (addon_dir or Path(__file__).resolve().parent.parent).resolve()
    explicit = os.environ.get("OPENWORLD_ROOT", "").strip()
    if explicit:
        return _checked_root(explicit, addon, "OPENWORLD_ROOT")
    config_file = addon / "openworld_config.json"
    if config_file.is_file():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"Khong doc duoc cau hinh {config_file}") from exc
        if (not isinstance(config, dict)
                or set(config) != {"openworld_root"}
                or not isinstance(config["openworld_root"], str)
                or not config["openworld_root"].strip()):
            raise RuntimeError("openworld_config.json can mot truong openworld_root la duong dan")
        return _checked_root(config["openworld_root"], addon, str(config_file))

    # An installed extension belongs to its ancestor project. Prefer that
    # project over unrelated sibling copies, regardless of the shell's cwd.
    for parent in (addon, *addon.parents):
        if all((parent / name).is_file() for name in REQUIRED_FILES):
            return parent
    for parent in addon.parents:
        candidates = [parent / name for name in ("OpenWorld-main", "OpenWorld_Clean")]
        found = [p.resolve() for p in candidates
                 if all((p / name).is_file() for name in REQUIRED_FILES)]
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            raise RuntimeError(
                "Co nhieu ban OpenWorld. Chon mot ban bang openworld_config.json "
                "hoac OPENWORLD_ROOT; khong tu dong ghep cac ban."
            )
    raise RuntimeError(
        "Khong tim thay OpenWorld. Tao openworld_config.json trong gemini_world "
        'voi noi dung {"openworld_root": "../OpenWorld-main"}.'
    )


def activate_openworld(addon_dir: Path | None = None) -> Path:
    root = resolve_openworld_root(addon_dir)
    source = str(root / "src")
    if source not in sys.path:
        sys.path.insert(0, source)
    return root
