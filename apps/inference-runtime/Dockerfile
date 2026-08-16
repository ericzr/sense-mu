FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    YOLO_CONFIG_DIR=/tmp/ultralytics

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir '.[runtime]' \
    && useradd --create-home --uid 10001 runtime \
    && mkdir -p /var/cache/sensemu \
    && chown -R runtime:runtime /var/cache/sensemu

USER runtime

CMD ["uvicorn", "sensemu_runtime.main:app", "--host", "0.0.0.0", "--port", "8090"]
