FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.api.txt ./requirements.txt

RUN pip install -r requirements.txt

COPY app ./app

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]