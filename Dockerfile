FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 ca-certificates tzdata && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./               # корневой файл с "-r bot/requirements.txt"
COPY bot/requirements.txt bot/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "bot.main"]
