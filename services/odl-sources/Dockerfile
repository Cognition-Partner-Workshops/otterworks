FROM python:3.12-slim
ARG KUBECTL_VERSION=v1.34.2
RUN pip install --no-cache-dir 'oracledb>=3.4,<5' 'psycopg[binary]>=3.1,<4' psycopg2-binary bcrypt PyYAML \
    && python -c "import urllib.request; urllib.request.urlretrieve('https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl', '/usr/local/bin/kubectl')" \
    && chmod +x /usr/local/bin/kubectl
WORKDIR /app
COPY services/odl-sources /app/services/odl-sources
COPY scripts/seed.py /app/scripts/seed.py
ENV PYTHONPATH=/app/services/odl-sources PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python", "-m", "odl_sources.load", "postgres"]
