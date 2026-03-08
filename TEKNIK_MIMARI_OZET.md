# Listify — Teknik Mimari Özeti

## 1. Backend (Sunucu Tarafı)

**Framework:** Flask (Python) tabanlı mikro mimari. WSGI uyumlu, modüler route yapısı ile ölçeklenebilir mimari.

**Veritabanı:** SQLAlchemy ORM ile ilişkisel veri yönetimi. İndeksleme (indexing) ile sorgu performansı artırılmış; geliştirme ortamında SQLite, üretim ortamında PostgreSQL desteği.

**Dosya Yönetimi:** Benzersiz UUID kullanımıyla dosya adı çakışmaları önlenir; güvenli ve izlenebilir depolama.

---

## 2. Frontend (Arayüz)

**Teknolojiler:** Bootstrap 5, Modern CSS (Custom Variables) ve Vanilla JavaScript. Jinja2 ile sunucu taraflı dinamik şablon render.

**Görselleştirme:** Chart.js ile dinamik istatistik grafikleri (Doughnut); yatay ve dikey istatistik kartları ile özet veri sunumu.

**Kullanıcı Deneyimi (UX):** Dark/Light Mode desteği, Bootstrap Toast ile canlı bildirimler, PDF önizleme (Modal Preview) özelliği.

---

## 3. Güvenlik ve Doğrulama

**MIME-Type Kontrolü:** python-magic kütüphanesi ile gerçek dosya içerik analizi; uzantı manipülasyonuna karşı koruma. Tehlikeli dosya tipleri engellenir.

**Oturum Yönetimi:** Flask-Login ile kimlik doğrulama ve yetkilendirme; güvenli session yönetimi; `@login_required`, `@teacher_required` decorator'ları ile rol tabanlı erişim kontrolü.

**Süre Yönetimi:** Backend tarafında dinamik süre kontrolü; süresi dolmuş listelerde otomatik erişim kısıtlama.

---

## 4. Fonksiyonel Özellikler

**Öğretmen:** Gelişmiş liste yönetimi, süre ekleme/uzatma, "Hepsini Göster" aksiyonu, istatistik kartları, toplu işlemler.

**Öğrenci:** 6 haneli kodla kayıt sistemi, anlık onay/red takibi, istatistik kartları (kayıtlı listeler, onaylananlar, bekleyenler, başarı oranı).
