FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    GUNICORN_BIND=0.0.0.0:8000 \
    PATH="/app/.venv/bin:$PATH" \
    UV_PROJECT_ENVIRONMENT="/app/.venv"

WORKDIR /app

RUN python -m pip install --no-cache-dir --upgrade pip uv

RUN groupadd --gid 10001 appuser && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin appuser

COPY pyproject.toml ./
RUN uv sync --no-install-project

COPY . .
RUN uv sync

RUN chown -R 10001:10001 /app

EXPOSE 8000

USER 10001:10001

CMD ["uv", "run", "run.py"]
