# Stand-in for web-02: Python 2.7, the app copied to /opt/branch-locator,
# file logging under /var/log, running as the unprivileged branch-locator
# user like the systemd unit.
FROM docker.io/library/python:2.7.18-slim
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
