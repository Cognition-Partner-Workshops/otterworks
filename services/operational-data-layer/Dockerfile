FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libcrypt1 libxml2 libpam0g libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 odl \
    && useradd --uid 10001 --gid odl --create-home odl

WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY odl_sync ./odl_sync
RUN pip install .

USER 10001:10001
EXPOSE 8098
CMD ["python", "-m", "odl_sync.api"]
