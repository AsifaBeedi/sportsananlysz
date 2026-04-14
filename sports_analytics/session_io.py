from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


class SessionWriter:
    def __init__(self, primary_path: Path, mirror_paths: tuple[Path, ...] = ()) -> None:
        self.primary_path = primary_path
        self.mirror_paths = mirror_paths

    def write(self, payload: dict[str, Any]) -> None:
        serialized = json.dumps(payload, indent=2)
        self._write_atomic(self.primary_path, serialized)

        for path in self.mirror_paths:
            if path != self.primary_path:
                self._write_atomic(path, serialized)

    @staticmethod
    def _write_atomic(path: Path, serialized: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        temp_path.write_text(serialized, encoding="utf-8")

        last_error: PermissionError | None = None
        for _ in range(20):
            try:
                temp_path.replace(path)
                return
            except PermissionError as error:
                last_error = error
                time.sleep(0.1)

        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass

        if last_error is not None:
            raise last_error
