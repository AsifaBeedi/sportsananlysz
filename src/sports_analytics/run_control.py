from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_CONTROL_DIR = PROJECT_ROOT / "data" / "run_control"
JOB_STATE_PATH = RUN_CONTROL_DIR / "analysis_job.json"
JOB_LOG_PATH = RUN_CONTROL_DIR / "analysis_job.log"


def build_analysis_command(
    source_value: str | Path | None,
    sport: str,
    *,
    source_type: str = "file",
    match_id: str | None = None,
    camera_id: str | None = None,
    camera_label: str | None = None,
    camera_role: str | None = None,
    python_executable: str | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    command = [
        python_executable or sys.executable,
        "src/main_pipeline.py",
        "--sport",
        sport,
        "--source-type",
        source_type,
        "--no-display",
    ]
    if source_value is not None:
        command.extend(["--source", str(source_value)])
    if match_id:
        command.extend(["--match-id", str(match_id)])
    if camera_id:
        command.extend(["--camera-id", str(camera_id)])
    if camera_label:
        command.extend(["--camera-label", str(camera_label)])
    if camera_role:
        command.extend(["--camera-role", str(camera_role)])
    if extra_args:
        command.extend(extra_args)
    return command


def launch_analysis_process(
    source_value: str | Path | None,
    sport: str,
    *,
    source_type: str = "file",
    match_id: str | None = None,
    camera_id: str | None = None,
    camera_label: str | None = None,
    camera_role: str | None = None,
    cwd: str | Path | None = None,
    extra_args: list[str] | None = None,
) -> dict[str, Any]:
    command = build_analysis_command(
        source_value,
        sport,
        source_type=source_type,
        match_id=match_id,
        camera_id=camera_id,
        camera_label=camera_label,
        camera_role=camera_role,
        extra_args=extra_args,
    )
    job_log_path = JOB_LOG_PATH
    job_log_path.parent.mkdir(parents=True, exist_ok=True)
    command_text = subprocess.list2cmdline(command)
    job_log_path.write_text(f"[{iso_now()}] Launching command: {command_text}\n", encoding="utf-8")
    popen_kwargs: dict[str, Any] = {
        "cwd": str(cwd or Path.cwd()),
    }
    log_handle = job_log_path.open("a", encoding="utf-8")
    popen_kwargs["stdout"] = log_handle
    popen_kwargs["stderr"] = subprocess.STDOUT

    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        process = subprocess.Popen(command, **popen_kwargs)
    finally:
        log_handle.close()

    job = {
        "pid": process.pid,
        "sport": sport,
        "source_type": source_type,
        "video_path": str(source_value) if source_value is not None else None,
        "match_id": match_id,
        "camera_id": camera_id,
        "camera_label": camera_label,
        "camera_role": camera_role,
        "command": command,
        "command_text": command_text,
        "launched_at": iso_now(),
        "status": "running",
        "log_path": str(job_log_path),
    }
    save_job_state(job)
    return job


def is_process_running(pid: int | None) -> bool:
    if pid in (None, 0):
        return False

    if os.name == "nt":
        return is_process_running_windows(int(pid))

    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError):
        return False
    return True


def stop_process(pid: int | None) -> bool:
    if pid in (None, 0):
        return False

    pid = int(pid)
    if os.name == "nt":
        if terminate_process_windows(pid):
            return True

        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode != 0:
            return False

        for _ in range(10):
            if not is_process_running(pid):
                return True
            time_sleep_short()
        return not is_process_running(pid)

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    return True


def load_job_state(path: Path = JOB_STATE_PATH) -> dict[str, Any] | None:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def save_job_state(job: dict[str, Any], path: Path = JOB_STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(job, indent=2), encoding="utf-8")


def clear_job_state(path: Path = JOB_STATE_PATH) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def refresh_job_state(job: dict[str, Any] | None, path: Path = JOB_STATE_PATH) -> dict[str, Any] | None:
    if job is None:
        return None

    refreshed = dict(job)
    pid = refreshed.get("pid")
    if is_process_running(pid):
        refreshed["status"] = "running"
    elif refreshed.get("status") == "failed":
        refreshed["completed_at"] = refreshed.get("completed_at") or iso_now()
    elif refreshed.get("status") == "stopped":
        refreshed["stopped_at"] = refreshed.get("stopped_at") or iso_now()
    else:
        refreshed["status"] = "completed"
        refreshed["completed_at"] = refreshed.get("completed_at") or iso_now()

    save_job_state(refreshed, path=path)
    return refreshed


def stop_active_job(path: Path = JOB_STATE_PATH) -> dict[str, Any] | None:
    job = load_job_state(path=path)
    if job is None:
        return None

    stopped = stop_process(job.get("pid"))
    refreshed = dict(job)
    refreshed["status"] = "stopped" if stopped else "stop_failed"
    refreshed["stopped_at"] = iso_now()
    save_job_state(refreshed, path=path)
    return refreshed


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def time_sleep_short() -> None:
    import time

    time.sleep(0.1)


def read_job_log_tail(path: str | Path | None, *, max_lines: int = 40) -> str:
    if not path:
        return ""

    log_path = Path(path)
    if not log_path.exists():
        return ""

    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""

    return "\n".join(lines[-max_lines:])


def read_job_log_info(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {"exists": False}

    log_path = Path(path)
    if not log_path.exists():
        return {"exists": False, "path": str(log_path)}

    try:
        stat = log_path.stat()
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {"exists": False, "path": str(log_path)}

    last_updated = datetime.fromtimestamp(stat.st_mtime)
    return {
        "exists": True,
        "path": str(log_path),
        "size_bytes": stat.st_size,
        "line_count": len(lines),
        "last_updated_at": last_updated.isoformat(timespec="seconds"),
        "age_seconds": max(0.0, round((datetime.now() - last_updated).total_seconds(), 2)),
        "last_line": lines[-1] if lines else "",
    }


def terminate_process_windows(pid: int) -> bool:
    try:
        import ctypes
    except ImportError:
        return False

    PROCESS_TERMINATE = 0x0001
    SYNCHRONIZE = 0x00100000
    WAIT_OBJECT_0 = 0x00000000
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE | SYNCHRONIZE, False, pid)
    if not handle:
        return False

    try:
        if not ctypes.windll.kernel32.TerminateProcess(handle, 1):
            return False
        wait_result = ctypes.windll.kernel32.WaitForSingleObject(handle, 1000)
        if wait_result != WAIT_OBJECT_0:
            return not is_process_running(pid)
        return True
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def is_process_running_windows(pid: int) -> bool:
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return False

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False

    try:
        exit_code = wintypes.DWORD()
        if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == STILL_ACTIVE
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)
