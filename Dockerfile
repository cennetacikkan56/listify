# Python 3.10 slim base
FROM python:3.10-slim

# PostgreSQL ve derleme için gerekli sistem paketlerini kur

WORKDIR /app

# Bağımlılıkları kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Proje dosyalarını kopyala
COPY . .

# Veritabanı ve klasör yapılandırmaları
RUN mkdir -p /data && chmod 755 /data

# Türkiye saati (UTC+3) - Railway/Render uyumluluğu
ENV TZ=Europe/Istanbul
# VOLUME ["/data"]  # Railway ile uyumluluk için kaldırıldı
ENV DATABASE_PATH=/data

# Railway ve Docker için port ayarı
ENV PORT=5000
EXPOSE 5000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 120 app:app"]