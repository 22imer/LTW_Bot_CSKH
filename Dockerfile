FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home --uid 1000 bot && mkdir -p /app/data && chown bot:bot /app/data
COPY --chown=bot:bot bot.py ./
COPY --chown=bot:bot cskh ./cskh
COPY --chown=bot:bot data/stores.json data/faq.md ./data/

USER bot
CMD ["python", "bot.py"]
