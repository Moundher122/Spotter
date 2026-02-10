FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN uv sync --no-install-project --no-cache
COPY . .
RUN chmod +x entry-point.sh
EXPOSE 8000
CMD ["sh", "./entry-point.sh"]
