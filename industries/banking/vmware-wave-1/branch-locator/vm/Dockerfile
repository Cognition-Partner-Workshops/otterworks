# Stand-in for web-02: Python 2.7, the app copied to /opt/branch-locator,
# file logging under /var/log, running as root like the systemd unit.
FROM docker.io/library/python:2.7.18-slim
COPY requirements.txt /opt/branch-locator/requirements.txt
RUN pip install --no-cache-dir -r /opt/branch-locator/requirements.txt && mkdir -p /var/log/branch-locator
COPY app /opt/branch-locator/app
WORKDIR /opt/branch-locator/app
EXPOSE 5000
CMD ["python", "locator.py"]
