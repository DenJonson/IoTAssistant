FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY backend/requirements.ha-worker.txt ./requirements.txt

RUN python -m pip install \
    --no-cache-dir \
    --timeout 120 \
    --retries 10 \
    --index-url https://mirrors.aliyun.com/pypi/simple/ \
    -r requirements.txt

COPY backend/app ./app

CMD ["python", "-m", "app.integrations.home_assistant.worker"]