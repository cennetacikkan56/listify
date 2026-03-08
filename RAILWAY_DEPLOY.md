# Railway Deployment - SQLite Volume Kurulumu

## Volume Bağlama Adımları

### 1. Projeyi Railway'e Yükle
- [railway.app](https://railway.app) → New Project → Deploy from GitHub
- Repo'yu seç ve deploy et

### 2. Volume Oluştur
- Railway Dashboard → Projeniz → **Volumes** sekmesi
- **+ New Volume** tıkla
- Volume adı ver (örn: `listify-data`)
- **Add Volume** ile onayla

### 3. Volume'u Servise Mount Et
- Oluşturduğun Volume'a tıkla
- **Mount Path** alanına şunu yaz: **`/data`**
- Bu path, uygulamanın SQLite dosyasını yazacağı klasör

### 4. Ortam Değişkenleri
- **Variables** sekmesinde:
  - `SECRET_KEY`: Güçlü bir gizli anahtar (production için zorunlu)
  - `DATABASE_PATH`: Dockerfile'da zaten `/data` olarak ayarlı (değiştirmeyin)
  - `TZ`: `Europe/Istanbul` — Türkiye saati (Dockerfile'da da ayarlı, Railway'de değişken olarak ekleyebilirsiniz)
  - `PORT`: Railway otomatik atar (elle ayarlamayın)

### 5. Deploy
- Değişiklikleri kaydettiğinizde otomatik redeploy olur
- SQLite dosyası `/data/database.sqlite` yolunda kalıcı olarak saklanır

---

**Not:** Volume mount path **mutlaka** `/data` olmalı. Uygulama `DATABASE_PATH=/data` ile bu klasöre yazar.
