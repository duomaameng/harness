FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY harness ./harness
RUN pip install --no-cache-dir .

WORKDIR /workspace

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "harness.api:app", "--host", "0.0.0.0", "--port", "8000"]
