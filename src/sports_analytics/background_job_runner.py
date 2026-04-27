from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an analysis command in the background with log/state updates.")
    parser.add_argument("--state-path", required=True, help="Path to the job-state JSON file.")
    parser.add_argument("--log-path", required=True, help="Path to the log file.")
    return parser.parse_args()


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    state_path = Path(args.state_path).resolve()
    log_path = Path(args.log_path).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    job = load_json(state_path)
    command = list(job.get("command") or [])
    if not command:
        raise SystemExit("No command found in job state for background_job_runner.")
    job["runner_started_at"] = iso_now()
    job["log_path"] = str(log_path)
    save_json(state_path, job)

    with log_path.open("a", encoding="utf-8") as log_handle:
        log_handle.write(f"[{iso_now()}] Starting command: {subprocess.list2cmdline(command)}\n")
        log_handle.flush()

        process = subprocess.Popen(
            command,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=Path.cwd(),
        )
        return_code = process.wait()

        job = load_json(state_path)
        job["completed_at"] = iso_now()
        job["exit_code"] = return_code
        job["status"] = "completed" if return_code == 0 else "failed"
        save_json(state_path, job)

        log_handle.write(f"[{iso_now()}] Command finished with exit code {return_code}\n")
        log_handle.flush()

    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
