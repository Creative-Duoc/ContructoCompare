from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(
    path: Path,
    payload: Any,
    *,
    ensure_ascii: bool = False,
    indent: int = 2,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_file: Path | None = None
    fd, tmp_name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        tmp_file = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=ensure_ascii, indent=indent)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        tmp_file.replace(path)
    finally:
        if tmp_file and tmp_file.exists():
            try:
                tmp_file.unlink()
            except OSError:
                pass
