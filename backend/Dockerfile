FROM python:3.11
RUN useradd --create-home appuser
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN pip install --upgrade pip setuptools wheel && \
    pip install --retries 10 -r requirements.txt -r requirements-dev.txt
COPY . .
# Render sets $PORT; default to 8000 for local Docker.
ENV PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:%s/api/v1/health'%os.environ.get('PORT','8000'))" || exit 1
USER appuser
# Shell form so ${PORT} is expanded (Render). Keeps socket_app/workers/timeouts.
CMD gunicorn app.main:socket_app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 120 --graceful-timeout 30 --keep-alive 5
