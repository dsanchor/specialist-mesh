FROM mcr.microsoft.com/devcontainers/python:3.12

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py .
COPY agents/ agents/
COPY .env .

EXPOSE 8088

CMD ["python", "main.py"]
