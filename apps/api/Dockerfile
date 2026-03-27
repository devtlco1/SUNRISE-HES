FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY packages/shared-python /workspace/packages/shared-python
COPY apps/api /workspace/apps/api
COPY pyproject.toml /workspace/pyproject.toml

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e /workspace/packages/shared-python -e /workspace/apps/api[dev]

WORKDIR /workspace/apps/api

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
