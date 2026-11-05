FROM docker.io/library/python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS test
WORKDIR /opt/branch-locator
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY tests tests
COPY vm vm
RUN python -m unittest discover -s tests && touch /tests-passed

FROM docker.io/library/python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS runtime
COPY --from=test /tests-passed /tests-passed
COPY requirements.txt /opt/branch-locator/requirements.txt
RUN pip install --no-cache-dir -r /opt/branch-locator/requirements.txt \
 && groupadd --gid 10001 branch-locator \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin branch-locator \
 && mkdir -p /var/log/branch-locator && chown 10001:10001 /var/log/branch-locator
COPY app /opt/branch-locator/app
WORKDIR /opt/branch-locator/app
USER 10001:10001
EXPOSE 5000
CMD ["python", "locator.py"]
