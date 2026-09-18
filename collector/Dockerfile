FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY config.yaml ./
COPY app ./app

# SQLite lives here; mount a volume so it survives container replacement.
VOLUME ["/app/data"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
