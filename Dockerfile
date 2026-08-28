FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dot/ dot/
COPY config/ config/

CMD ["python", "-m", "dot", "run", "--config", "config/checks.yaml"]
