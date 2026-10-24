# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS api-build
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY apps/api ./apps/api
COPY apps/demo_agent ./apps/demo_agent
RUN uv sync --locked --no-dev --no-editable --package mutiny-api

FROM node:22-bookworm-slim AS web-build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web ./
# Next.js rewrites are baked into the build. Never pass the API token here.
ARG MUTINY_API_URL=http://api:8000
ENV MUTINY_API_URL=$MUTINY_API_URL
RUN npm run build

FROM node:22-bookworm-slim AS web
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
COPY --from=web-build --chown=node:node /app/.next/standalone ./
COPY --from=web-build --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]

# Keep API last: Railway builds this default target from the repository root.
FROM python:3.12-slim-bookworm AS api
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    MUTINY_DB_PATH=/app/data/mutiny.sqlite
RUN groupadd --gid 10001 mutiny && useradd --uid 10001 --gid mutiny --no-create-home mutiny \
    && mkdir /app/data && chown mutiny:mutiny /app/data
COPY --from=api-build /app/.venv /app/.venv
COPY examples ./examples
COPY config ./config
COPY scripts/ensure_sample_mutiny.py ./scripts/ensure_sample_mutiny.py
# Preserve the Railway sample-ensure behavior, but prepare files during build.
RUN python scripts/ensure_sample_mutiny.py
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "mutiny_api", "--host", "0.0.0.0", "--port", "8000"]
