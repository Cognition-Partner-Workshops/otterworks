FROM python:3.12-slim
WORKDIR /app
COPY loader/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY loader/loader.py ./loader/loader.py
COPY dbt ./dbt
RUN useradd -u 1001 -m app && chown -R app /app
USER 1001
ENV DBT_PROJECT_DIR=/app/dbt PYTHONUNBUFFERED=1
CMD ["python", "loader/loader.py"]
