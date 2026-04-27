from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

import sys as _sys

if str(PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in _sys.path:
    _sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sports_analytics.profiles import supported_sports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run lightweight smoke tests for the sports analytics project.")
    parser.add_argument("--sport", choices=supported_sports(), default="tennis", help="Sport to validate.")
    parser.add_argument("--all-sports", action="store_true", help="Run the short analysis validation across all sports.")
    parser.add_argument("--max-frames", type=int, default=1, help="Frame count for short validation runs.")
    parser.add_argument("--dashboard-port", type=int, default=8527, help="Port to use for headless dashboard boot.")
    parser.add_argument("--skip-dashboard", action="store_true", help="Skip the Streamlit startup check.")
    parser.add_argument("--skip-analysis", action="store_true", help="Skip the short analysis run.")
    return parser.parse_args()


def quoted_command(command: list[str]) -> str:
    return " ".join(f'"{part}"' if " " in part else part for part in command)


def run_subprocess(command: list[str], *, timeout: int, expect_timeout_boot: bool = False) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = f"{exc.stdout or ''}\n{exc.stderr or ''}".strip()
        if expect_timeout_boot and "Local URL:" in output:
            return True, output
        return False, output or f"Command timed out: {quoted_command(command)}"

    output = f"{completed.stdout}\n{completed.stderr}".strip()
    if completed.returncode != 0:
        return False, output or f"Command failed with exit code {completed.returncode}: {quoted_command(command)}"
    return True, output


def run_dashboard_boot(port: int) -> bool:
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app/streamlit_app.py",
        "--server.headless",
        "true",
        "--server.port",
        str(port),
    ]
    print(f"[dashboard] {quoted_command(command)}")
    ok, output = run_subprocess(command, timeout=20, expect_timeout_boot=True)
    if ok:
        print("[dashboard] boot check passed")
        return True
    print("[dashboard] boot check failed")
    if output:
        print(output)
    return False


def run_short_analysis(sport: str, max_frames: int) -> bool:
    command = [
        sys.executable,
        "src/main_pipeline.py",
        "--sport",
        sport,
        "--source-type",
        "demo",
        "--no-display",
        "--no-output-video",
        "--writer-codec",
        "mp4v",
        "--max-frames",
        str(max_frames),
    ]
    print(f"[analysis:{sport}] {quoted_command(command)}")
    ok, output = run_subprocess(command, timeout=600)
    if not ok:
        print(f"[analysis:{sport}] failed")
        if output:
            print(output)
        return False

    validate_command = [
        sys.executable,
        "tools/validate_session_payload.py",
        "--latest",
        "--sport",
        sport,
    ]
    for attempt in range(1, 3):
        print(f"[validate:{sport}] {quoted_command(validate_command)} (attempt {attempt}/2)")
        ok, output = run_subprocess(validate_command, timeout=120)
        if ok:
            print(f"[validate:{sport}] passed")
            return True
        if attempt == 1:
            time.sleep(2)

    print(f"[validate:{sport}] failed")
    if output:
        print(output)
    return False


def main() -> int:
    args = parse_args()
    overall_ok = True

    if not args.skip_dashboard:
        overall_ok = run_dashboard_boot(args.dashboard_port) and overall_ok

    if not args.skip_analysis:
        sports = list(supported_sports()) if args.all_sports else [args.sport]
        for sport in sports:
            overall_ok = run_short_analysis(sport, args.max_frames) and overall_ok

    if overall_ok:
        print("Smoke test passed.")
        return 0

    print("Smoke test failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
