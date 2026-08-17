FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
EXPOSE 8080
CMD ["sh","-c","alembic upgrade head && uvicorn app.secured:app --host 0.0.0.0 --port ${PORT:-8000}"]
