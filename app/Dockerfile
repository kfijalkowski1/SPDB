FROM python:3.12-slim-bookworm AS base

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.4.9 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY uv.lock pyproject.toml /app/
COPY .streamlit /app/.streamlit

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-install-project --no-dev
COPY code/ /app/code

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-dev


FROM base
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8501
WORKDIR /app

# Run the Streamlit app with auto reload
CMD ["watchmedo", "auto-restart", "--patterns=*.py", "--directory=/app/code", "--recursive", \
  "--", "streamlit", "run", "./code/visualizer.py", "--server.port=8501", "--server.address=0.0.0.0" ]
