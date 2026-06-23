FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py .
COPY agents/ agents/
COPY .env .

EXPOSE 8088

CMD ["python", "main.py"]
