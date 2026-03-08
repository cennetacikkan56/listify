# Listify — Hocaya Sunum İçin Teknik Özet

## Proje Analizi ve Teknik Döküman

Bu rapor, **Listify** adlı liste ve ödev yönetim sisteminin teknik altyapısını özetlemektedir. Proje, eğitmenlerin sınıf listeleri oluşturmasına, öğrencilerin kayıt olmasına ve ödev teslim etmesine olanak tanıyan bir web uygulamasıdır.

---

## 1. Teknoloji Yığını (Tech Stack)

### Backend
| Teknoloji | Açıklama |
|-----------|----------|
| **Python 3.10** | Ana programlama dili |
| **Flask** | Hafif, modüler web framework |
| **Flask-SQLAlchemy** | ORM ile veritabanı erişimi |
| **Flask-Login** | Oturum ve kimlik doğrulama |
| **ReportLab** | Sunucu tarafı PDF oluşturma |
| **Werkzeug** | Dosya güvenliği (secure_filename), HTTP hata yönetimi |

### Frontend
| Teknoloji | Açıklama |
|-----------|----------|
| **Bootstrap 5.3** | Responsive UI bileşenleri |
| **Bootstrap Icons** | İkon seti |
| **Custom CSS** | CSS değişkenleri ile tema motoru, tasarım sistemi |
| **Vanilla JavaScript** | Ek framework yok; modal, tema değiştirme, form doğrulama |
| **Jinja2** | Şablon motoru (Flask ile entegre) |
| **Google Fonts (Inter)** | Tipografi |

### Veritabanı
| Ortam | Veritabanı |
|-------|------------|
| **Yerel Geliştirme** | SQLite (`instance/database.db` veya `database.db`) |
| **Docker / Production** | PostgreSQL 15 (docker-compose ile) |

Veritabanı seçimi ortam değişkeniyle yapılır: `DATABASE_URL` varsa PostgreSQL, yoksa SQLite kullanılır.

### Konteyner Yapısı
- **Docker** ile containerization
- **Docker Compose** ile çok konteynerli (web + PostgreSQL) çalıştırma

---

## 2. Mimari: MVC ve Katman Yapısı

Proje **MVC (Model-View-Controller)** benzeri bir yapı kullanır:

| Katman | Karşılık | Açıklama |
|--------|----------|----------|
| **Model** | `app.py` içindeki SQLAlchemy modelleri | `User`, `ListVera`, `StudentRecord`, `Assignment`, `Submission` |
| **View** | `templates/` klasöründeki Jinja2 şablonları | `layout.html` (base), `dashboard.html`, `list_detail.html`, vb. |
| **Controller** | `app.py` içindeki route fonksiyonları | `@app.route` ile tanımlı endpoint’ler |

**Özellikler:**
- Tek ana uygulama dosyası (`app.py`) — modeller, route’lar ve yardımcı fonksiyonlar burada
- Tüm veritabanı erişimi ORM üzerinden; ham SQL sadece migration için kullanılıyor
- `layout.html` ile ortak header, navbar, flash/toast alanı ve tema script’i paylaşılıyor

---

## 3. Öne Çıkan Özellikler

### 3.1 Dinamik Tema Motoru (Karanlık / Aydınlık Mod)
- **CSS değişkenleri** (`:root`, `[data-theme="dark"]`, `[data-theme="light"]`) ile tema yönetimi
- JavaScript ile `document.documentElement.setAttribute('data-theme', theme)` ile tema değiştirme
- Tercih `localStorage` (`listify-theme`) ile saklanıyor
- Geçiş animasyonları: `transition: all 0.2s ease-in-out`
- Aydınlık mod: beyaz arka plan, koyu metin
- Karanlık mod: GitHub benzeri mat füme (#0D1117), açık gri metin (#E6EDF3)

### 3.2 Responsive Tasarım
- **Bootstrap Grid** ile responsive layout
- **Media Queries** ile mobil uyum (örn. `@media (max-width: 767.98px)`)
- Mobilde tablo → kart görünümü, hamburger menü, tam ekran modal
- 44px dokunma hedefleri (erişilebilirlik)

### 3.3 Güvenlik
- **Kimlik doğrulama:** `@login_required`, `@teacher_required` decorator’ları
- **Dosya yükleme:** Sadece `.pdf`, `.doc`, `.docx`; maksimum 5MB
- **İstemci + sunucu** doğrulama (form validation + `allowed_file()`)
- 5MB aşımında `RequestEntityTooLarge` (413) hata yönetimi
- `secure_filename()` ile dosya adı güvenliği
- Rol tabanlı erişim (eğitmen / öğrenci)

### 3.4 PDF Oluşturma Mantığı
- **ReportLab** ile sunucu tarafı PDF üretimi
- **DejaVuSans** fontu ile Türkçe karakter desteği
- A4 sayfa, kenar boşlukları, tablo formatında liste raporu
- `/download-pdf/<list_id>` endpoint’i ile indirme
- Font yoksa Helvetica fallback

### 3.5 Toast Bildirimleri
- Başarılı işlemlerde sağ üstte Bootstrap Toast (3 saniye)
- Hata durumlarında kırmızı toast ile uyarı

---

## 4. Docker Yapısı

### Neden Docker?
1. **Taşınabilirlik:** Farklı ortamlarda aynı Python ve bağımlılıklarla çalışma
2. **Bağımlılık yönetimi:** `requirements.txt` ile tekrarlanabilir kurulum
3. **Geliştirme / üretim uyumu:** Yerel ve sunucuda aynı konfigürasyon

### Dockerfile
- **Base:** `python:3.10-slim`
- **Bağımlılıklar:** `pip install -r requirements.txt`
- **Veri:** `/data` volume (SQLite veya volume mount için)
- **Port:** 5000 expose

### Docker Compose
- **`db` servisi:** PostgreSQL 15, kalıcı volume
- **`web` servisi:** Flask uygulaması, `db`’ye bağımlı
- **Ortam değişkenleri:** `DATABASE_URL`, `FLASK_DEBUG`
- **Port eşlemesi:** 8001:5000 (yerelden 8001’de erişim)
- **Volume:** `./uploads` → ödev dosyaları için

---

## 5. Veritabanı Modelleri (Özet)

| Model | Açıklama |
|-------|----------|
| **User** | Kullanıcı (eğitmen/öğrenci), giriş bilgileri |
| **ListVera** | Eğitmen listesi (başlık, kod, süre, duyuru) |
| **StudentRecord** | Listeye kayıtlı öğrenci |
| **Assignment** | Listeye bağlı ödev |
| **Submission** | Ödev teslimi (dosya yolu, not, geri bildirim) |

---

## 6. Kısa Sunum Özeti (Hocaya Anlatım)

> **Listify**, Python ve Flask tabanlı bir liste ve ödev yönetim sistemidir. Backend’de Flask-SQLAlchemy ile ORM kullanılmakta; veritabanı olarak geliştirmede SQLite, production’da PostgreSQL tercih edilmektedir. Frontend’de Bootstrap 5, custom CSS ve Vanilla JS ile responsive bir arayüz sunulmaktadır. Proje MVC benzeri bir yapıdadır. Öne çıkan teknik özellikler: CSS değişkenleri ile dinamik tema (karanlık/aydınlık mod), media query ile responsive tasarım, dosya tipi ve boyut kontrolü ile güvenli yükleme, ReportLab ile PDF rapor oluşturma ve Bootstrap Toast ile kullanıcı bildirimleri. Docker ve Docker Compose sayesinde uygulama taşınabilir ve farklı ortamlarda tutarlı şekilde çalışacak biçimde paketlenmiştir.

---

*Bu rapor Listify projesinin teknik analizine dayanmaktadır.*
