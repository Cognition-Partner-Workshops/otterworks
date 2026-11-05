# branch-locator on the platform: Python 3.12, gunicorn on 8080, uid 10001.
# The VM build (vm/Dockerfile) still uses app/ and requirements.txt; this image uses service/ only.
FROM docker.io/library/python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS test
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY service/ .
RUN python -m unittest discover -v -s tests

FROM docker.io/library/python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=test /srv/locator.py /srv/geo.py /srv/settings.py /srv/gunicorn.conf.py ./
COPY --from=test /srv/templates ./templates
USER 10001:10001
EXPOSE 8080
CMD ["gunicorn", "-c", "gunicorn.conf.py", "locator:app"]
