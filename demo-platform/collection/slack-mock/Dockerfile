FROM python:3.12.16-slim
RUN useradd --uid 10001 --create-home app && mkdir /data && chown app /data
WORKDIR /app
COPY src/ /app/src/
ENV PYTHONPATH=/app/src PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    COLLECTION_DB_PATH=/data/collection-slack.sqlite3
USER app
EXPOSE 8780
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD python -c "import http.client,sys;c=http.client.HTTPConnection('127.0.0.1',8780,timeout=2);c.request('GET','/healthz');sys.exit(0 if c.getresponse().status==200 else 1)"
CMD ["python", "-m", "collection_slack"]
