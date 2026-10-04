FROM python:3.14-slim

WORKDIR /app

# git for the nightly GitHub mirror (app/sources/github_mirror.py).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# app/ is copied before the install because pyproject declares it as a package —
# pip install . cannot resolve it otherwise.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

COPY config.yaml ./

# SQLite lives here; mount a volume so it survives container replacement.
VOLUME ["/app/data"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
