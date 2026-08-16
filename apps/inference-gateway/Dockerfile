FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

EXPOSE 8080
CMD ["uvicorn", "sensemu_gateway.main:app", "--host", "0.0.0.0", "--port", "8080"]

