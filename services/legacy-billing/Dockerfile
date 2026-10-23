FROM python:3.12-slim

ADD --checksum=sha256:90a6f1a7978a1b1b096dca6c57511ca48d3b8cf052f8e704baf358f34ea2f21b https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem /etc/ssl/certs/rds-global-bundle.pem
RUN chmod 0644 /etc/ssl/certs/rds-global-bundle.pem

WORKDIR /app
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ .
RUN useradd --system --uid 1001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8096
CMD ["gunicorn", "--bind", "0.0.0.0:8096", "app:app"]
