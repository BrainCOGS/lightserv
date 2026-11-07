FROM lightserv-port:app
USER root
COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen
COPY tests/container /app/container_tests
USER lightservuser
