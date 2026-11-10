# Imagen para desarrollo local y portable a ECS/EKS si se migra desde Elastic Beanstalk.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv
RUN groupadd --system app && useradd --system --gid app --no-create-home app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY scripts ./scripts

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"

CMD ["gunicorn", "app.main:app", "--workers", "2", "--worker-class", "uvicorn_worker.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "30"]
