FROM python:3.10-slim

WORKDIR /app

# Cài đặt thư viện lõi của Linux để chạy MySQL
RUN apt-get update && apt-get install -y gcc default-libmysqlclient-dev pkg-config

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "WMS.wsgi:application"]