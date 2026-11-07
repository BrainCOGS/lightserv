FROM python:3.14-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends openssh-client graphviz && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev
COPY lightserv /app/lightserv
COPY schemas /app/schemas
COPY lib /opt/libraries
ENV PYTHONPATH=/opt/libraries
COPY run.py celery_worker.py /app/
RUN useradd -r -u 2354 -d /home/lightservuser -m lightservuser && groupadd -g 9038 g_lightsheet_data && usermod -aG g_lightsheet_data lightservuser && mkdir -p /app/logs /home/lightservuser/.ssh && chown -R lightservuser /app /home/lightservuser/.ssh
# Mount SSH credentials at runtime; never bake a private key into an image.
USER lightservuser
EXPOSE 5000
CMD ["gunicorn", "-w", "5", "run:app", "-b", "0.0.0.0:5000"]
