from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
VENV_DIR = BACKEND_DIR / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
ENV_FILE = BACKEND_DIR / ".env"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the backend service for the e-commerce art agent demo.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--bind-host", default="127.0.0.1")
    parser.add_argument("--serve-frontend", action="store_true")
    parser.add_argument("--no-reload", action="store_true")
    return parser.parse_args()


def health_ok(port: int) -> bool:
    url = f"http://127.0.0.1:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload.get("status") == "ok"
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=str(cwd), env=env, check=True)


def venv_python_works() -> bool:
    if not VENV_PYTHON.exists():
        return False
    try:
        completed = subprocess.run(
            [str(VENV_PYTHON), "--version"],
            cwd=str(BACKEND_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return completed.returncode == 0


def ensure_venv() -> None:
    if venv_python_works():
        return

    if VENV_DIR.exists():
        shutil.rmtree(VENV_DIR, ignore_errors=True)

    run([sys.executable, "-m", "venv", str(VENV_DIR)], cwd=BACKEND_DIR)

    if not venv_python_works():
        raise RuntimeError("Virtual environment creation failed.")


def install_requirements() -> None:
    run([str(VENV_PYTHON), "-m", "pip", "install", "-r", "requirements.txt"], cwd=BACKEND_DIR)


def build_uvicorn_args(args: argparse.Namespace) -> list[str]:
    command = [
        str(VENV_PYTHON),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        args.bind_host,
        "--port",
        str(args.port),
    ]
    if ENV_FILE.exists():
        command += ["--env-file", ".env"]
    if not args.no_reload:
        command.append("--reload")
    return command


def main() -> int:
    args = parse_args()

    if health_ok(args.port):
        print(f"Backend is already running at http://127.0.0.1:{args.port}/health")
        return 0

    ensure_venv()
    install_requirements()

    env = os.environ.copy()
    if args.serve_frontend:
        env["APP_SERVE_FRONTEND"] = "1"

    run(build_uvicorn_args(args), cwd=BACKEND_DIR, env=env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
