FROM python:3.12-slim

WORKDIR /app

COPY main.py .
COPY openapi.yaml .

EXPOSE 8091

CMD ["python", "main.py"]
