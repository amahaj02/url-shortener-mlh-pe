import os
import sys
from pathlib import Path

from app import create_app

app = create_app()


def _int_env(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _ensure_gunicorn_bind():
    """Let local `.env` PORT/HOST apply when GUNICORN_BIND is not set."""
    if os.getenv("GUNICORN_BIND"):
        return
    host = os.getenv("HOST", "0.0.0.0")
    port = _int_env("PORT", 3000)
    os.environ["GUNICORN_BIND"] = f"{host}:{port}"


def main():
    """Entrypoint for `uv run run.py` — replace this process with Gunicorn (clean Ctrl+C / SIGTERM)."""
    _ensure_gunicorn_bind()
    config = Path(__file__).resolve().parent / "deployment" / "gunicorn.conf.py"
    argv = [sys.executable, "-m", "gunicorn", "-c", str(config), "run:app"]
    os.execvp(sys.executable, argv)


if __name__ == "__main__":
    main()
