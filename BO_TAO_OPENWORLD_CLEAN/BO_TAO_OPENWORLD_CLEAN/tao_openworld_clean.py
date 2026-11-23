#!/usr/bin/env python3
"""Safely create a clean copy of the OpenWorld Python project.

Default: preserve every meaningful part of OpenWorld-main, skip root-level bundles,
Node binaries, caches, generated databases, and local secrets.
Works with an existing local copy, or fetches the OpenWorld-main subtree from
its public GitHub repository if none is found locally.

"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

REPO = "tranduy4572-dotcom/open_world"
BRANCH = "main"
PROJECT_NAME = "OpenWorld-main"
FOLDER_NAME = "OpenWorld_Clean"

# Include the full functional Python project and its quality/evidence materials.
ROOT_FILES = {
    "README.md", "LICENSE", "SECURITY.md", "CONTRIBUTING.md",
    "AGENTS.md", "pyproject.toml", ".gitignore",
}
ROOT_DIRS = {
    "src", "examples", "tests", "benchmarks", "docs", "scripts",
    "research", ".github",
}

# Source files are NOT rewritten. These exclusions target build artifacts,
# local secrets, downloaded binaries, and temporary/runtime data only.
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", ".idea", ".vscode",
    "node_modules", "dist", "build", "htmlcov", ".coverage",
}
EXCLUDED_FILE_NAMES = {".env", ".env.local", "thumbs.db", ".ds_store"}
EXCLUDED_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".exe", ".dll", ".so", ".dylib",
    ".sqlite", ".sqlite3", ".db", ".log", ".tmp", ".bak", ".zip", ".7z",
    ".tar", ".gz", ".whl", ".egg", ".lock",
}
SOURCE_MARKERS = (
    "README.md", "pyproject.toml", "src/openworld_superkernel/world_fixture.py",
    "examples/r0_agent_cycle.py",
)


def is_project(p: Path) -> bool:
    return p.is_dir() and all((p / mark).is_file() for mark in SOURCE_MARKERS)


def candidates(base: Path):
    """Look a couple of levels around the script/working directory."""
    if not base.exists() or not base.is_dir():
        return
    yield base
    yield base / PROJECT_NAME
    yield base / "open_world" / PROJECT_NAME
    for child in sorted(base.iterdir()):
        if child.is_dir() and child.name not in EXCLUDED_DIRS and not child.name.startswith("OpenWorld_Clean"):
            yield child
            yield child / PROJECT_NAME


def locate_local(explicit: str | None):
    if explicit:
        p = Path(explicit.strip().strip('"').strip("'")).expanduser().resolve()
        if is_project(p):
            return p
        if is_project(p / PROJECT_NAME):
            return p / PROJECT_NAME
        raise RuntimeError(f"Không tìm thấy OpenWorld-main hợp lệ tại: {p}")
    here = Path(__file__).resolve().parent
    seen = set()
    for base in (Path.cwd(), here, Path.cwd().parent, here.parent):
        for p in candidates(base):
            k = str(p)
            if k not in seen:
                seen.add(k)
                if is_project(p):
                    return p
    return None


def skip(relative: Path, *, size: int | None = None) -> bool:
    parts = relative.parts
    if not parts:
        return True
    if parts[0] not in ROOT_DIRS and relative.as_posix() not in ROOT_FILES:
        return True
    if any(part.lower() in EXCLUDED_DIRS for part in parts[:-1]):
        return True
    name = parts[-1].lower()
    if name in EXCLUDED_FILE_NAMES or (name.startswith(".env")):
        return True
    if relative.suffix.lower() in EXCLUDED_EXTENSIONS:
        return True
    if name.endswith(("-wal", "-shm", "-journal")):
        return True
    if size is not None and size > 10_000_000:
        return True
    return False


def should_copy(rel: Path, size: int | None = None) -> bool:
    return not skip(rel, size=size)


def request_bytes(url: str, *, accept: str | None = None) -> bytes:
    headers = {"User-Agent": "OpenWorld-Clean-Copy/1.0"}
    if accept:
        headers["Accept"] = accept
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers=headers), timeout=40) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise RuntimeError(f"GitHub HTTP {exc.code}: {url}") from exc
        except (URLError, TimeoutError) as exc:
            if attempt == 3:
                raise RuntimeError(f"Không tải được dữ liệu: {url} ({exc})") from exc
        time.sleep(2 ** attempt)
    raise RuntimeError("Network retries exhausted")


def fetch_tree():
    base = f"https://api.github.com/repos/{REPO}"
    root = json.loads(request_bytes(f"{base}/git/trees/{BRANCH}"))
    node = next((x for x in root.get("tree", []) if x["path"] == PROJECT_NAME and x["type"] == "tree"), None)
    if node is None:
        raise RuntimeError("Không thấy OpenWorld-main trên nhánh main của GitHub")
    tree = json.loads(request_bytes(f"{base}/git/trees/{node['sha']}?recursive=1"))
    if tree.get("truncated"):
        raise RuntimeError("Danh sách file từ GitHub bị cắt ngắn, dừng để tránh tạo bản sao thiếu file")
    return node["sha"], tree.get("tree", [])


def copy_local(source: Path, destination: Path):
    copied = []
    skipped = []
    for root, directories, files in os.walk(source):
        base = Path(root)
        dirs_kept = []
        for directory in sorted(directories):
            rel = (base / directory).relative_to(source)
            if directory.lower() in EXCLUDED_DIRS or rel.parts[0] not in ROOT_DIRS:
                skipped.append(rel.as_posix() + "/")
            else:
                dirs_kept.append(directory)
        directories[:] = dirs_kept
        for name in sorted(files):
            file = base / name
            rel = file.relative_to(source)
            if file.is_symlink():
                skipped.append(rel.as_posix() + " [symlink]")
                continue
            try:
                size = file.stat().st_size
            except OSError:
                skipped.append(rel.as_posix() + " [stat error]")
                continue
            if not should_copy(rel, size=size):
                skipped.append(rel.as_posix())
                continue
            target = destination / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
            copied.append(rel.as_posix())
    return copied, skipped, {"origin": str(source), "method": "local-original-copy"}


def copy_remote(destination: Path):
    sha, tree = fetch_tree()
    copied = []
    skipped = []
    blobs = [entry for entry in tree if entry["type"] == "blob"]
    for i, entry in enumerate(blobs, 1):
        rel = Path(entry["path"])
        if not should_copy(rel, size=entry.get("size")):
            skipped.append(rel.as_posix())
            continue
        remote_path = f"{PROJECT_NAME}/{rel.as_posix()}"
        url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{quote(remote_path, safe='/')}"
        content = request_bytes(url)
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        copied.append(rel.as_posix())
        if len(copied) % 25 == 0:
            print(f"  Đã tải {len(copied)} file...", flush=True)
    return copied, skipped, {"origin": f"https://github.com/{REPO}/tree/{BRANCH}/{PROJECT_NAME}", "method": "github-public-raw", "tree_sha": sha}


def next_destination(parent: Path):
    base = parent / FOLDER_NAME
    if not base.exists():
        return base
    for i in range(2, 1000):
        candidate = parent / f"{FOLDER_NAME}_{i}"
        if not candidate.exists():
            return candidate
    raise RuntimeError("Đã có quá nhiều thư mục đầu ra")


def validate(destination: Path, copied: list[str]):
    missing = [f for f in SOURCE_MARKERS if f not in copied or not (destination / f).is_file()]
    if missing:
        raise RuntimeError("Bản sao thiếu file quan trọng: " + ", ".join(missing))
    modules = list((destination / "src/openworld_superkernel").glob("*.py"))
    if len(modules) < 15:
        raise RuntimeError(f"Dữ liệu mã lõi không đầy đủ ({len(modules)} file Python)")


def write_docs(dest: Path, metadata: dict, copied: list[str], skipped: list[str]):
    manifest = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": metadata,
        "copied_count": len(copied),
        "skipped_inside_project": sorted(skipped),
        "copied_files": sorted(copied),
    }
    (dest / "DANH_SACH_FILE_DUOC_GIU.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    guide = """# OpenWorld_Clean — Bản sao đã dọn gọn

## Đây là gì?

Thư mục này là **bản sao giữ nguyên mã nguồn** từ `OpenWorld-main`.
Công cụ chỉ bỏ các file thừa, cache, dữ liệu phát sinh, file nhị phân,
khóa bí mật, và hoàn toàn không sửa hay xóa dự án gốc.

## Thư mục nên học theo thứ tự

1. `examples/r0_agent_cycle.py` — bắt đầu demo Alice/Bob.
2. `src/openworld_superkernel/r0_cycle.py` — điều phối một lượt Agent.
3. `src/openworld_superkernel/world_fixture.py` — luật World, Agent, tài nguyên, sự kiện.
4. `src/openworld_superkernel/world_guard.py` — kiểm tra quyền.
5. `src/openworld_superkernel/hyper_memory_p1e.py` — bộ nhớ SQLite và dự đoán.
6. `src/openworld_superkernel/math_kernel.py` — các phép toán nghiên cứu.
7. `tests/test_r0_agent_cycle.py` — kiểm tra luồng R0.
8. `docs/vi/README.md` — tổng quan tiếng Việt.

## Cách chạy trong VS Code (Python 3.11+)

Mở chính thư mục OpenWorld_Clean và chạy terminal:

```powershell
python examples/r0_agent_cycle.py
python scripts/check_repository.py
python -m unittest discover -s tests -v
```

Một số bài nghiên cứu dài mặc định SKIPPED; xem README gốc để chạy đủ.

## Vì sao vẫn giữ tests, benchmarks và docs?

- `tests`: tránh sửa mã nguồn rồi làm hỏng các phần khác.
- `benchmarks`: cho phép so sánh thuật toán với baseline, không chỉ nhìn demo.
- `docs`: chứa kiến trúc, giới hạn, và hướng phát triển dự án.
- `.github`: cấu hình kiểm tra CI khi đưa dự án lên GitHub.

## Những phần đã được loại trừ

Bản sao KHÔNG bao gồm các file ở ngoài `OpenWorld-main`, chẳng hạn:
`node.exe`, `npm`, `npx`, `node_modules`, bộ cài `.bat`/`.cmd` ở repo gốc,
nhật ký SQLite mẫu, dữ liệu so sánh, các ghi chú `.txt` hướng dẫn riêng.

Bên trong `OpenWorld-main` chỉ bỏ cache, file build, runtime log,
`.env`, file tạm hoặc file nhị phân phát sinh. Mục tiêu là không xóa các
module nghiên cứu có thể đang được tests hay benchmarks sử dụng.

Xem `DANH_SACH_FILE_DUOC_GIU.json` để biết chính xác file nào đã sao chép.

**Chưa tích hợp Gemini/LLM:** bản này là mã gốc OpenWorld, không phải mini Lab có `brains.py`.
"""
    (dest / "BAT_DAU_TAI_DAY.md").write_text(guide, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Tạo bản sao OpenWorld gọn, KHÔNG xóa mã gốc")
    parser.add_argument("--source", help="Thư mục OpenWorld-main hoặc thư mục cha chứa nó")
    parser.add_argument("--output", help="Thư mục cha nơi tạo OpenWorld_Clean")
    parser.add_argument("--github", action="store_true", help="Bỏ qua bản local, tải bản sạch từ GitHub")
    args = parser.parse_args()

    try:
        source = None if args.github else locate_local(args.source)
        parent = Path(args.output).expanduser().resolve() if args.output else (source.parent if source else Path(__file__).resolve().parent)
        parent.mkdir(parents=True, exist_ok=True)
        destination = next_destination(parent)
        print("\n=== TẠO THƯ MỤC OPENWORLD_CLEAN ===")
        print("Nguồn:", source if source else f"GitHub {REPO} / {PROJECT_NAME}")
        print("Đích:", destination)
        print("Bản gốc sẽ KHÔNG bị thay đổi hoặc xóa.\n")
        with tempfile.TemporaryDirectory(prefix=".openworld_clean_tmp_", dir=str(parent)) as temporary:
            stage = Path(temporary) / "payload"
            stage.mkdir()
            if source is not None:
                copied, skipped, metadata = copy_local(source, stage)
            else:
                print("Không tìm thấy mã local, đang tải bản dự án chính từ GitHub...")
                copied, skipped, metadata = copy_remote(stage)
            validate(stage, copied)
            write_docs(stage, metadata, copied, skipped)
            stage.rename(destination)
        print(f"\nHOÀN THÀNH: {len(copied)} file mã nguồn/tài liệu đã sao chép.")
        print("Bỏ qua", len(skipped), "file/thư mục tạm trong dự án chính.")
        print("Mở thư mục này bằng VS Code:", destination)
        print("Đọc trước file BAT_DAU_TAI_DAY.md")
        return 0
    except Exception as exc:
        print("\nLỖI:", exc, file=sys.stderr)
        print("Không có file gốc nào bị xóa hoặc sửa.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
