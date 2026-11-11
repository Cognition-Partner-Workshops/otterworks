FROM python:3.12-slim
RUN pip install --no-cache-dir pyyaml==6.0.2 stomp.py==8.2.0 paramiko==3.5.1 'psycopg[binary]==3.2.9' \
    && useradd --uid 1000 --create-home replay \
    && install -d -o replay -g replay /workspace /state /reports
WORKDIR /workspace
COPY --chown=replay:replay integration /workspace/integration
USER replay
ENTRYPOINT ["python", "-m", "integration.harness"]
