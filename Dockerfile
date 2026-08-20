# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

FROM base AS prod
# ⚡ OPTIMIZATION: Multiple workers for concurrent request handling
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
