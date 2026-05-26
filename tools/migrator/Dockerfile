FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY tools/migrator/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY tools/migrator/migrate.py ./migrate.py
COPY deploy/db/migrations ./migrations

CMD ["python", "migrate.py"]