FROM python:3.12.12-alpine
WORKDIR /app
COPY workload.py .
USER 10001:10001
CMD ["python", "-B", "/app/workload.py"]
