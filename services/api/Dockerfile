FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY worker.py .

ENV PYTHONUNBUFFERED=1

# POSIX shell expands PORT at runtime. Railway injects PORT; local default is 8000.
# exec makes uvicorn PID 1 so it receives container stop signals.
CMD ["sh", "-c", "port=\"${PORT:-8000}\"; case \"$port\" in ''|*[!0-9]*) echo \"PORT must be numeric, got: $port\" >&2; exit 1;; esac; exec uvicorn app.main:app --host 0.0.0.0 --port \"$port\""]
