FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY wanguard_exporter.py .

EXPOSE 9100

CMD ["python", "wanguard_exporter.py"]
