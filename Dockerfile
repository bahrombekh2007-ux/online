FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ma'lumotlar bazasi uchun doimiy joy (Render Disk ulanganda persist bo'ladi)
VOLUME ["/app/data"]
ENV DB_PATH=/app/data/data.db

# Web panel porti (Render PORT o'zgaruvchisini avtomatik beradi)
EXPOSE 8080

CMD ["python", "main.py"]
