# One image: the built React app is served by the FastAPI backend on port 8000.

# ---- frontend build -----------------------------------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- backend runtime ----------------------------------------------------------------------
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
# yt-dlp needs a JavaScript runtime to resolve YouTube videos.
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/backend/.venv/bin:$PATH" \
    CDJ_DB_PATH=/data/crowdsource_dj.sqlite3 \
    CDJ_FRONTEND_DIST=/app/frontend/dist

# Which proxies may set X-Forwarded-For. Narrow this to your proxy's address when you can:
# rate limits key on the client address, which an untrusted header can fake.
ENV FORWARDED_ALLOW_IPS="*"

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
COPY --from=frontend /app/frontend/dist /app/frontend/dist

RUN useradd --uid 1000 --home /data cdj && mkdir -p /data && chown cdj /data
USER cdj
VOLUME /data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--ws-max-size", "65536"]
