# Listify — Profesyonel Öğrenci ve Ödev Yönetim Sistemi

## Teknik Rapor ve Kullanıcı Kılavuzu

**Versiyon:** 1.0  
**Hazırlayan:** Proje Ekibi  
**Son Güncelleme:** Şubat 2025

---

# BÖLÜM I — TEKNİK RAPOR (Jüri Sunumu)

## 1. Projenin Amacı ve Vizyonu

### 1.1 Problem Tanımı
Öğretmenler, derslerinde yüzlerce öğrenciyle çalışırken liste yönetimi, ödev takibi, teslim alma ve değerlendirme süreçlerinde manuel ve kağıt tabanlı işlerle karşı karşıya kalır. Bu durum zaman kaybına, hata riskine ve veri kaybına yol açar.

### 1.2 Çözüm: Listify
**Listify**, öğretmenler için tasarlanmış bir **dijital asistan** niteliğinde web tabanlı bir öğrenci ve ödev yönetim sistemidir. Sistem:

- **Liste oluşturma ve yönetimi**: Benzersiz 6 haneli kodlarla öğrenci listeleri oluşturma
- **Öğrenci kayıt süreci**: Giriş yapmadan veya giriş yaparak listeye katılım
- **Ödev teslim ve takip**: Ödev bazlı teslim alma, revizyon talebi, not verme
- **Onay / red akışı**: Bekleyen, onaylanan ve reddedilen öğrenci durumlarını yönetme
- **Arşiv / çöp kutusu**: Soft delete ile silinen öğelerin geri yüklenebilmesi

**Vizyon:** Eğitimcilerin iş yükünü azaltmak ve veri güvenliği ile kullanılabilirliği bir arada sunan, kurumsal seviyede bir SaaS platformu olmaktır.

---

## 2. Teknik Mimari (Tech Stack)

### 2.1 Kullanılan Teknolojiler

| Katman | Teknoloji | Açıklama |
|--------|-----------|----------|
| Backend | Python 3, Flask | WSGI web framework |
| Veritabanı | SQLite / PostgreSQL | Geliştirme: SQLite, üretim: PostgreSQL |
| ORM | SQLAlchemy, Flask-SQLAlchemy | İlişkisel veri modelleme |
| Kimlik Doğrulama | Flask-Login | Oturum ve rol yönetimi |
| Frontend | HTML5, CSS3, Vanilla JavaScript | SPA değil, sunucu taraflı render |
| Şablon | Jinja2 | Dinamik HTML üretimi |
| UI Framework | Bootstrap 5.3 | Responsive grid, bileşenler |
| İkon | Bootstrap Icons | Arayüz ikonları |
| Raporlama | ReportLab | PDF çıktı üretimi |
| E-posta | SendGrid Web API | Şifre sıfırlama, doğrulama |
| Deployment | Gunicorn, Docker, Railway/Render | WSGI sunucu, container, PaaS |

### 2.2 Veritabanı Yapısı ve İlişkiler

#### Varlık-İlişki Özeti

```
User (Öğretmen / Öğrenci)
  ├── lists (One-to-Many) → ListVera
  └── student_records (One-to-Many) → StudentRecord

ListVera (Liste)
  ├── owner_id → User (Many-to-One)
  ├── students (One-to-Many) → StudentRecord
  └── assignments (One-to-Many) → Assignment

StudentRecord (Öğrenci Kaydı)
  ├── list_id → ListVera (Many-to-One)
  └── user_id → User (Many-to-One, nullable)

Assignment (Ödev)
  ├── list_id → ListVera (Many-to-One)
  └── submissions (One-to-Many) → Submission

Submission (Teslim)
  ├── assignment_id → Assignment (Many-to-One)
  └── user_id → User (Many-to-One)
```

#### One-to-Many İlişkiler

- **User → ListVera**: Bir öğretmen birden fazla liste oluşturabilir (`owner_id` foreign key).
- **ListVera → StudentRecord**: Bir listede birden fazla öğrenci kaydı bulunur.
- **ListVera → Assignment**: Bir listede birden fazla ödev tanımlanabilir.
- **Assignment → Submission**: Bir ödeve birden fazla öğrenci teslim yapabilir.

---

## 3. İleri Seviye Özellikler (Advanced Features)

### 3.1 Güvenlik (Security)

#### 3.1.1 Ownership (Sahiplik) Kontrolü
Tüm liste ve öğrenci işlemlerinde `owner_id == current_user.id` kontrolü yapılır:

- `list_detail`, `approve_student`, `reject_student`, `view_file`, `download_submission`
- `bulk_delete_students`, `restore_student`, `permanent_delete_student`
- `delete_list`, `restore_list`, `purge_list`, `add_assignment`, `delete_assignment`
- Dashboard ve çöp kutusu sorgularında `owner_id=current_user.id` filtresi

Yetkisiz erişimde `403 Forbidden` veya flash mesajıyla yönlendirme yapılır.

#### 3.1.2 MIME-Type Tabanlı Dosya Doğrulaması
Dosya yüklemede hem uzantı hem MIME type kontrolü uygulanır:

```python
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'zip', 'docx'}
ALLOWED_MIMETYPES = {
    'application/pdf', 'image/png', 'image/jpeg', 'image/jpg',
    'application/zip', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
}
BLOCKED_MIMETYPES = {
    'text/html', 'text/javascript', 'application/javascript',
    'image/svg+xml', 'application/x-msdownload', 'application/x-executable',
    'application/x-sh', 'text/x-python', 'application/x-httpd-php'
}
```

`allowed_mimetype(content_type)`:
- Önce `BLOCKED_MIMETYPES` kontrolü; engellenen tipler reddedilir.
- Ardından `ALLOWED_MIMETYPES` kontrolü; yalnızca izin verilen tipler kabul edilir.
- Uzantı tarafında `html`, `htm`, `svg`, `js`, `exe`, `sh`, `py`, `php` engellenir.

#### 3.1.3 Path Traversal ve Dosya Erişimi
`_safe_submission_path(file_path)` ile:

- `..` içeren yollar engellenir.
- Mutlak path (`/`, `\`) engellenir.
- Sonuç path’in `UPLOAD_FOLDER` altında kalması ve gerçek bir dosya olması kontrol edilir.

### 3.2 Veri Yönetimi (Data Management)

#### 3.2.1 Soft Delete (`is_deleted`)
Hem **ListVera** hem **StudentRecord** modellerinde `is_deleted` alanı kullanılır:

| İşlem | Sonuç |
|-------|-------|
| Öğrenci silme (çöpe at) | `StudentRecord.is_deleted = True` |
| Liste silme (çöpe at) | `ListVera.is_deleted = True` |
| Geri yükleme | `is_deleted = False` |
| Kalıcı silme | Kayıt veritabanından `db.session.delete()` ile kaldırılır, dosyalar diskten silinir |

#### 3.2.2 Arşiv / Çöp Kutusu Sistemi
- **Liste çöp kutusu**: `list_trash` rotası, `is_deleted=True` listeleri gösterir. Geri yükleme ve kalıcı silme desteklenir.
- **Öğrenci çöpü**: Liste detay sayfasında “Silinen Öğrenciler” modal’ı ile `is_deleted=True` kayıtlar listelenir; geri yükleme veya kalıcı silme yapılabilir.

#### 3.2.3 Hard Delete (Kalıcı Silme)
- **Öğrenci**: `permanent_delete_student` — kayıt ve ilişkili dosyalar kalıcı silinir.
- **Liste**: `purge_list` — liste ve ilişkili tüm veriler kalıcı silinir.
- **Tüm çöp**: “Tüm Çöpü Boşalt” ile kullanıcının tüm silinmiş listeleri kalıcı silinir.

### 3.3 Performans ve Frontend (Event Delegation, Reactivity)

#### 3.3.1 Event Delegation
Dinamik eklenen DOM öğelerinde (geri yükleme sonrası satırlar vb.) tıklama sorunlarını önlemek için **Event Delegation** kullanılır:

```javascript
document.body.addEventListener('click', function(e) {
    var btn = e.target.closest('.btn-duzenle');
    if (!btn) return;
    e.preventDefault();
    // Modal açma, veri doldurma...
});
```

`.btn-degerlendir`, `.btn-duzenle` gibi butonlar `document.body` üzerindeki tek bir listener ile yakalanır; sayfa yüklendikten sonra eklenen satırlarda da çalışır.

#### 3.3.2 Sayfa Yenilemeden Güncelleme (Reactivity)
- Öğrenci silme / geri yükleme: Fetch API ile JSON endpoint’lere istek atılır; başarıda ilgili satır DOM’dan kaldırılır veya yeniden eklenir.
- Sayaçlar (`statListTotalStudents`, `statListPendingApprovals`): JSON cevabındaki değerlerle güncellenir.
- Toast bildirimleri: `window.showListifyToast()` ile kullanıcıya anlık geri bildirim verilir.

---

## 4. Kullanıcı Deneyimi ve Tasarım (UI/UX)

### 4.1 Modern Dashboard Tasarımı
- **Kart tabanlı görünüm**: Her liste bir kart; başlık, benzersiz kod, durum rozeti, süre bilgisi gösterilir.
- **Esnek grid**: `grid-template-columns: repeat(auto-fit, minmax(300px, 1fr))` ile mobil 1, tablet 2, masaüstü 3–4 sütun düzeni.
- **Gölge ve hover**: `box-shadow`, `transform: scale(1.02)` ile derinlik ve etkileşim hissi.
- **Renk paleti**: Pastel yeşil (#d1fae5) onay, pastel kırmızı (#fee2e2) silme, mavi (#2563eb) ana aksiyon.

### 4.2 Glassmorphism ve Sticky Navbar
- Navbar: `position: sticky; top: 0; z-index: 1000` ile kaydırma sırasında üstte sabit kalır.
- Toplu işlem barı: Masaüstünde `sticky`, mobilde `position: fixed; bottom: 0` ile ekranın altında sabitlenir.
- Arka plan: Hafif kirli beyaz (#f4f7f6) ile göz yormayan bir görünüm sağlanır.

### 4.3 Responsive (Mobil Uyumlu) Yapı
- **Medya sorguları**: `max-width: 767.98px` ve `575.98px` ile mobil/tablet kırılımları.
- **Mobil tablo**: Masaüstünde tablo; mobilde kart görünümü (`#studentsMobileCards`, `d-md-none`).
- **Tablo taşması**: `#studentsTableWrapper` için `overflow-x: auto; -webkit-overflow-scrolling: touch` ile yatay kaydırma.

### 4.4 Dokunmatik Dostu (Touch-Friendly) Tasarım
- Butonlar: `min-height: 44px` (Apple HIG önerisi).
- 3 nokta menüleri: `min-width: 44px`, `min-height: 44px`.
- Form alanları: Mobilde `font-size: 16px` (iOS zoom engellemek için).

### 4.5 İnteraktif Modal Sistemi
- Bootstrap 5 Modal; Değerlendir, Düzenle, Silinen Öğrenciler modalları.
- Değerlendir modalında iframe ile PDF/image önizleme.
- Geri bildirim alanı, not ve revizyon talebi formları.

---

## 5. Güvenlik Duvarı Detayları

### 5.1 Tehlikeli Dosya Engelleme

| Dosya Türü | Neden Engellenir |
|------------|------------------|
| `.html`, `.htm`, `.svg` | XSS ve script çalıştırma riski |
| `.exe`, `.js` | Kötü amaçlı kod çalıştırma |
| `.sh`, `.py`, `.php` | Sunucu tarafı komut/script riski |
| MIME: `text/javascript`, `application/javascript` | Client-side script enjeksiyonu |
| MIME: `image/svg+xml` | SVG içinde script kullanımı |
| MIME: `application/x-msdownload`, `application/x-executable` | Çalıştırılabilir dosya riski |

Yükleme sırasında hem `allowed_file()` (uzantı) hem `allowed_mimetype()` (Content-Type) kontrol edilir.

### 5.2 XSS Koruması
- **Jinja2 varsayılan escape**: `{{ variable }}` ile çıkan tüm değerler otomatik HTML-escape edilir.
- **HTML attribute güvenliği**: `data-*` kullanılan yerlerde `|e` filtresi: `{{ (s.display_name or '—')|e }}`
- **Dinamik içerik**: Modal ve tablolara yazılan kullanıcı verileri `replace(/&lt;/g,'<')` vb. ile decode edilirken DOM API kullanılır; innerHTML’e ham HTML enjekte edilmez.

### 5.3 CSRF ve Oturum
- Flask `SECRET_KEY` ile session imzalama.
- `@login_required`, `@teacher_required` decorator’ları ile yetkisiz erişimin engellenmesi.

---

## 6. Gelecek Vizyonu

### 6.1 Önerilen Özellikler

| Özellik | Açıklama |
|---------|----------|
| **İstatistik grafikleri** | Chart.js / ApexCharts ile teslim oranı, liste bazlı performans, zaman serisi grafikleri |
| **E-posta bildirimleri** | Ödev teslimi, revizyon talebi, liste kapanışı için otomatik mail |
| **PDF raporlama** | Liste raporları, not çizelgeleri; ReportLab altyapısı genişletilebilir |
| **Toplu öğrenci içe aktarma** | CSV/Excel ile toplu kayıt |
| **API (REST)** | Mobil uygulama veya üçüncü parti entegrasyonları için JSON API |
| **Rol tabanlı yetkilendirme** | Yardımcı öğretmen, asistan gibi rollere kısmi erişim |
| **2FA (İki Faktörlü Doğrulama)** | TOTP ile güvenlik artırımı |
| **Audit log** | Kim, ne zaman, hangi işlemi yaptı kaydı |

---

# BÖLÜM II — KULLANICI KILAVUZU

## 1. Sisteme Giriş

### 1.1 Kayıt Olma
- Ana sayfada **“Kayıt Ol”** bağlantısına tıklayın.
- **Öğretmen** veya **Öğrenci** rolünü seçin.
- Kullanıcı adı, şifre ve (öğrenci ise) ad-soyad, öğrenci numarası girin.
- Kayıt sonrası otomatik giriş yapılır.

### 1.2 Giriş Yapma
- Kullanıcı adı ve şifre ile giriş yapın.
- “Beni hatırla” ile oturum süresi uzatılabilir.

### 1.3 Şifremi Unuttum
- Giriş sayfasında **“Şifremi Unuttum”** linkine tıklayın.
- E-posta adresinizi girin; doğrulanmış e-posta varsa sıfırlama linki gönderilir.

---

## 2. Öğretmen Paneli

### 2.1 Yeni Liste Oluşturma
1. **Panelim** sayfasında **“Yeni Liste”** butonuna tıklayın.
2. Liste başlığı ve (isteğe bağlı) açıklama girin.
3. Bitiş tarihi/süresi belirleyin (isteğe bağlı).
4. Kaydedin; sistem 6 haneli benzersiz kod üretir.
5. Bu kodu öğrencilerle paylaşın.

### 2.2 Listeye Ödev Ekleme
1. Liste detay sayfasına girin.
2. **“Ödev Ekle”** butonuna tıklayın.
3. Başlık, açıklama ve son teslim tarihini girin.

### 2.3 Öğrenci Değerlendirme
1. Liste detayında öğrenci satırında **“Değerlendir”** butonuna tıklayın.
2. Teslim edilen dosyayı iframe’de önizleyin.
3. Geri bildirim ve not girin.
4. **“Onayla”** veya **“Reddet”** ile karar verin (reddetmede geri bildirim zorunludur).

### 2.4 Toplu İşlemler
- **Seç** modu: İlgili listede veya Panelim’de **“Seç”** butonu.
- Onaylanacak veya silinecek kayıtları işaretleyin.
- **“Seçilenleri Onayla”** veya **“Çöpe At”** ile toplu işlem yapın.

### 2.5 Silinen Öğrenciler
1. Liste detayında **3 nokta menüsü** → **“Silinen Öğrenciler”**.
2. Geri yükleme veya kalıcı silme yapın.

### 2.6 Çöp Kutusu (Liste Arşivi)
- Navbar veya Panelim’den **“Çöp Kutusu”** ile silinen listelere erişin.
- Listeleri geri yükleyebilir veya kalıcı silebilirsiniz.

---

## 3. Öğrenci Paneli

### 3.1 Listeye Katılma
- **“Liste Koduna Katıl”** ile 6 haneli kodu girin veya öğretmenin verdiği katılım linkini kullanın.
- Giriş yapmadan ad-soyad ve numara ile kayıt mümkün; giriş yaparak da kayıt yapılabilir.

### 3.2 Kayıtlarım
- Tüm kayıtlı olduğunuz listeler ve ödevler burada görünür.
- **Beklemede** / **Onaylandı** / **Reddedildi** durumlarına göre ödev yükleme veya görüntüleme yapılır.

### 3.3 Ödev Teslim Etme
1. İlgili ödevde **“Dosya Yükle”** butonuna tıklayın.
2. Desteklenen formatlar: PDF, PNG, JPG, DOCX, ZIP (maks. 5 MB).
3. HTML ve SVG güvenlik nedeniyle kabul edilmez.
4. Yükleme sonrası “Teslim Edildi” durumu görünür.

### 3.4 Revizyon
- Öğretmen revizyon talep etmişse **“Dosyayı Yeniden Yükle”** ile yeni dosya gönderebilirsiniz.

---

## 4. Sık Kullanılan Özellikler

### 4.1 Arama
- Panelim’de liste adı veya 6 haneli kod ile arama yapılabilir.

### 4.2 Filtre
- **Tamamlanmayan** veya **Tamamlanan** listeler filtrelenebilir.

### 4.3 Tema
- Sağ üstte ay/güneş ikonu ile aydınlık/karanlık tema değiştirilebilir.

### 4.4 PDF İndirme
- Liste detayında **“PDF İndir”** ile öğrenci listesi PDF olarak indirilebilir (ReportLab ile).

---

## 5. Desteklenen Tarayıcılar

- Chrome, Firefox, Safari, Edge (son 2 ana sürüm)
- Mobil tarayıcılar (iOS Safari, Chrome Android)

---

*Bu belge teknik jüri sunumu ve kullanıcı kılavuzu olarak hazırlanmıştır. Güncellemeler proje geliştikçe yapılacaktır.*
