FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
EXPOSE 8080
CMD ["sh","-c","alembic upgrade head && python -c 'import os,uvicorn; from app.secured import app; from app.rate_limit import install; install(app); uvicorn.run(app, host=\"0.0.0.0\", port=int(os.getenv(\"PORT\",\"8000\")))'"]
