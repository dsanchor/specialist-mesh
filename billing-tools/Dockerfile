FROM python:3.12-slim

WORKDIR /app

COPY main.py .
COPY openapi.yaml .
COPY openapi.json .

EXPOSE 8091

CMD ["python", "main.py"]
