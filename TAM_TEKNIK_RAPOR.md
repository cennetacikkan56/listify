# Listify — Tam Teknik Rapor (Sistem Mimarı Görünüm .

Bu belge, projede yapılan tüm teknik değişikliklerin detaylı dokümantasyonudur.

---

## 1. Dosya Bazlı Değişiklikler

### 1.1 app.py

| Fonksiyon/Öğe | İşlem | Açıklama |
|---------------|-------|----------|
| `_now_istanbul()` | Mevcut | `datetime.now(_TZ_ISTANBUL)` ile Europe/Istanbul (UTC+3) anlık zaman |
| `_compute_due_from_engine(unit, amount)` | Mevcut | Time Engine: dakika/saat/gün/hafta/ay → UTC naive datetime hesaplama |
| `_to_istanbul_iso(dt)` | **Eklenen** | Naive UTC datetime → ISO 8601 string (`+03:00` suffix) dönüşümü |
| `istanbul_iso_filter(dt)` | **Eklenen** | Jinja2 template filter: `{{ dt\|istanbul_iso }}` kullanımı |
| `ListVera.is_accepting_entries()` | **Güncellendi** | `datetime.utcnow()` yerine `_now_istanbul().astimezone(utc)` ile Europe/Istanbul referanslı karşılaştırma |
| `ListVera.check_and_mark_expired()` | **Güncellendi** | Aynı zaman dilimi mantığı ile `is_completed` otomatik güncelleme |
| `Assignment.is_submission_open()` | **Eklenen** | `due_date` kontrolü; Europe/Istanbul referanslı UTC karşılaştırma |
| `approve_student(record_id)` | **Güncellendi** | `grade`, `submission_id` form parametreleri; Submission.grade kaydı |
| `reject_student(record_id)` | Mevcut | Geri bildirim zorunluluğu (server-side validation) |
| `submit_homework()` | **Güncellendi** | Onay kontrolü kaldırıldı (pending de teslim yapabilir); `is_accepting_entries()` ve `is_submission_open()` kontrolleri eklendi |
| `view_file()` | **Güncellendi** | Genişletilmiş `inline_types`: bmp, svg, html, htm, csv |
| `view_my_submission()` | **Güncellendi** | Aynı `inline_types`; `record.status != 'approved'` kontrolü kaldırıldı |
| `my_records()` | **Güncellendi** | Orphan kayıt eşleştirmesi (user_id=None, student_no match); `check_and_mark_expired` çağrısı; DEBUG log |
| `list_detail()` | **Güncellendi** | `list_completed_pct` hesabı: `total_expected = list_total_students * num_assignments` |
| `list_assignments_student()` | **Güncellendi** | `check_and_mark_expired()` çağrısı |

### 1.2 templates/list_detail.html

| Bölüm | İşlem |
|-------|-------|
| Değerlendir modalı | **Yeniden düzenlendi**: Not alanı, iframe ile dosya önizleme, `data-list-id` attribute |
| İncele iframe URL | **Güncellendi**: Sabit path yerine `url_for('view_file', ...)` ile dinamik URL |
| PDF Görüntüle linki | **Güncellendi**: `/download-pdf/...` → `url_for('download_pdf', ...)` |
| Değerlendir JS | Onayla formuna `grade`, `submission_id` hidden alanları eklendi; iframe src dinamik set |

### 1.3 templates/layout.html

| Bölüm | İşlem |
|-------|-------|
| Countdown badge JS | `new Date(exp)` (ISO 8601 parse); `replace(' ', 'T')` kaldırıldı |
| DEBUG_COUNTDOWN | `?debug=countdown` URL param ile konsol log |
| `updateCountdownBadges()` | Her saniye çalışan geri sayım güncelleme |

### 1.4 templates/list_detail.html (countdown-box)

| Bölüm | İşlem |
|-------|-------|
| data-expires | `strftime` → `{{ target_list.expires_at\|istanbul_iso }}` |
| Countdown script | `new Date(expStr)` (replace kaldırıldı) |

### 1.5 templates/dashboard.html, my_records.html, list_detail.html

| Dosya | Değişiklik |
|-------|------------|
| dashboard.html | `data-expires="{{ liste.expires_at\|istanbul_iso }}"` |
| my_records.html | `data-expires="{{ lst.expires_at\|istanbul_iso }}"`; Dosya Yükle modalında desteklenen uzantılar notu; pending/rejected durumunda ödev listesi + Dosya Yükle; DEBUG HTML yorumları |
| student_assignments.html | Desteklenen uzantılar notu; Dosya Yükle linki |
| submit_homework.html | Desteklenen uzantılar notu |

### 1.6 templates/my_records.html (öğrenci paneli mantığı)

| Durum | Görünüm |
|-------|---------|
| `status == 'pending'` | Ödev listesi + Dosya Yükle (onay beklemeden de teslim yapılabilir) |
| `status == 'rejected'` | Ödev listesi + "Onay sonrası açılır" |
| `status == 'approved'` | Ödev listesi + Dosya Yükle / Teslim Edildi / Revizyon Yeniden Yükle |

---

## 2. Veritabanı Şeması (İlgili Sütunlar)

### 2.1 list_vera

| Sütun | Veri Tipi | İşlev |
|-------|-----------|-------|
| `expires_at` | DATETIME (naive UTC) | Listeye kayıt/teslim kapanış zamanı. `_compute_due_from_engine` ile hesaplanır. Karşılaştırma `_now_istanbul()` → UTC dönüşümü ile yapılır. |
| `announcement` | TEXT | Liste duyurusu metni |
| `announcement_updated_at` | DATETIME | Duyuru güncelleme zamanı (yeni duyuru rozeti için) |

### 2.2 student_record

| Sütun | Veri Tipi | İşlev |
|-------|-----------|-------|
| `status` | VARCHAR(20), default='pending' | Onay durumu: `pending`, `approved`, `rejected` |
| `submission_status` | VARCHAR(20), default='pending' | Teslim iş akışı (Beklemede / Teslim edildi / Kontrol edildi) |
| `teacher_feedback` | TEXT | Eğitmenin öğrenciye geri bildirimi |
| `user_id` | INTEGER, nullable | Giriş yapmış öğrenci ile eşleşme; NULL ise `student_no` ile orphan eşleştirmesi yapılır |

### 2.3 assignment

| Sütun | Veri Tipi | İşlev |
|-------|-----------|-------|
| `due_date` | DATETIME (naive UTC) | Ödev teslim son tarihi; `is_submission_open()` ile kontrol |

### 2.4 submission

| Sütun | Veri Tipi | İşlev |
|-------|-----------|-------|
| `grade` | VARCHAR(20) | Öğrenciye verilen not (Onayla sırasında da girilebilir) |
| `revision_requested` | BOOLEAN | Revizyon isteği durumu |
| `file_path` | VARCHAR(500) | Sunucu dosya yolu (relative) |

---

## 3. Zaman Motoru (Time Engine) Mantığı

### 3.1 Birim Dönüşümü

```
units = {
    'ay':    30,           # 1 ay = 30 gün
    'hafta': 7,            # 1 hafta = 7 gün
    'gun':   1,            # 1 gün
    'saat':  1/24,         # 1 saat = 1/24 gün
    'dakika': 1/(24*60)    # 1 dakika = 1/1440 gün
}
days = amount * units[unit]
target = _now_istanbul() + timedelta(days=days)
return target.astimezone(timezone.utc).replace(tzinfo=None)  # Naive UTC
```

**Matematiksel örnek:**
- 2 saat: `days = 2 * (1/24) = 0.0833` → `timedelta(days=0.0833)` ≈ 2 saat
- 30 dakika: `days = 30 * (1/1440)` → yaklaşık 0.5 saat

### 3.2 Europe/Istanbul Zaman Dilimi Senkronizasyonu

**Backend (Python):**
- `_TZ_ISTANBUL = ZoneInfo('Europe/Istanbul')` veya `pytz.timezone('Europe/Istanbul')`
- `_now_istanbul()`: `datetime.now(_TZ_ISTANBUL)` ile awareness-aware anlık zaman
- Karşılaştırmalar için: `now_utc = _now_istanbul().astimezone(timezone.utc).replace(tzinfo=None)` (UTC naive)
- Veritabanına her zaman **naive UTC** yazılır; `_compute_due_from_engine` sonucu `.astimezone(timezone.utc).replace(tzinfo=None)` ile döner
- Frontend’e gönderim: `_to_istanbul_iso(dt)` → `2026-03-17T15:30:00+03:00` (ISO 8601)

**Frontend (JavaScript):**
- `data-expires` attribute’unda ISO 8601 string: `{{ expires_at|istanbul_iso }}`
- Parse: `new Date(exp)` — tarayıcı ISO 8601’i (timezone dahil) doğru yorumlar
- Karşılaştırma: `diff = expDate - new Date()` (milisaniye cinsinden)
- Geri sayım: `Math.floor(diff/1000)` saniye, dakika, saat, gün formatına dönüştürülür

**Neden ISO 8601 + timezone gerekli?**
- Timezone olmadan `2026-03-17T12:00:00` tarayıcıda **yerel saat** olarak yorumlanır
- İstanbul UTC+3 olduğu için UTC ile 3 saat fark oluşur; bu da geri sayımın yanlış hesaplanmasına yol açar

---

## 4. Frontend Koşullu Mantığı

### 4.1 Ödev Ekle / Dosya Yükle Görünürlük Şartları

| Koşul | Sonuç |
|-------|-------|
| `r.status == 'pending'` | Ödev listesi + Dosya Yükle butonu gösterilir |
| `r.status == 'rejected'` | Ödev listesi + "Onay sonrası açılır" (Dosya Yükle yok) |
| `r.status == 'approved'` | Ödev listesi + Dosya Yükle / Teslim Edildi / Revizyon Yeniden Yükle |
| `lst.assignments` boş | "Henüz ödev eklenmedi" mesajı |
| `(lst.id, a.id) in submitted_assignments` | "Teslim Edildi" + Görüntüle / İndir |
| `(lst.id, a.id) in revision_requested_for` | "Dosyayı Yeniden Yükle" butonu |

**Not:** Template’te `is_accepting_entries()` ve `is_submission_open()` ile ilgili görünürlük kısıtları kaldırıldı; backend `submit_homework` bu kontrolleri yapıyor.

### 4.2 Dosya Önizleme (Inline Preview) Mekanizması

**HTTP Response Header’ları:**
- `Content-Type`: Uzantıya göre MIME type (örn. `application/pdf`, `image/jpeg`)
- `Content-Disposition`: **inline** (veya `as_attachment=False` ile gönderim)

**Flask `send_from_directory` parametreleri:**
```python
return send_from_directory(..., mimetype=mimetype, as_attachment=False)
```

**Desteklenen inline türler (mimetype mapping):**
```
pdf  → application/pdf
jpg, jpeg → image/jpeg
png  → image/png
gif  → image/gif
bmp  → image/bmp
svg  → image/svg+xml
txt  → text/plain
html, htm → text/html
csv  → text/csv
```

Bu türlerde `as_attachment=False` ile tarayıcı dosyayı indirmeden görüntüler. Diğer uzantılar (doc, docx, zip vb.) `as_attachment=True` ile indirilir.

**Değerlendir modalındaki iframe:**
- `src` dinamik olarak `view_file` URL’ine ayarlanır
- `url_for('view_file', list_id=0, assignment_id=0, submission_id=0)` ile pattern alınır, JS’te ID’ler replace edilir (subpath/proxy uyumu için)

---

## 5. Güvenlik ve Doğrulama (Validation)

### 5.1 Reddetme İşleminde Geri Bildirim Zorunluluğu

**Sunucu (Python) — `reject_student`:**
```python
feedback_val = request.form.get('teacher_feedback', '').strip()
if not feedback_val or len(feedback_val.strip()) == 0:
    flash("Reddetmek için geri bildirim zorunludur.", "danger")
    return redirect(url_for('list_detail', list_id=record.list_id))
```

**İstemci (JavaScript) — `degerlendirRejectBtn` click handler:**
```javascript
var feedback = (document.getElementById('degerlendirFeedback').value || '').trim();
if (!feedback) {
    if (window.showListifyToast) window.showListifyToast('Reddetmek için geri bildirim zorunludur.', 'danger');
    else alert('Reddetmek için geri bildirim zorunludur.');
    return;
}
// Form submit...
```

### 5.2 Dosya Yükleme Validasyonu

**Backend (`allowed_file`):**
- Uzantı whitelist: `ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'html', 'htm', 'zip', 'rar', '7z', ...}`
- Maksimum boyut: `MAX_CONTENT_LENGTH = 5 * 1024 * 1024` (5 MB)

**Frontend (my_records, submit_homework):**
- `ALLOWED` dizisi ile uzantı kontrolü
- `f.size > MAX_MB * 1024 * 1024` ile boyut kontrolü

### 5.3 Yetkilendirme

- `@teacher_required`: Sadece `role == 'teacher'` olanlar `list_detail`, `approve_student`, `reject_student` vb. rotalara erişebilir
- `submit_homework`: `StudentRecord` ile listeye kayıtlı olma kontrolü
- `view_file`: `target_list.owner_id == current_user.id` (liste sahibi)
- `_safe_submission_path`: Path traversal koruması (`..`, mutlak path engellemesi)

---

## 6. Ek Teknik Notlar

- **SQL Query:** Doğrudan SQL yazılmıyor; SQLAlchemy ORM kullanılıyor
- **Jinja2 Filters:** `istanbul_iso` ile tarih formatlaması
- **Middleware:** Flask-Login `@login_required`, özel `@teacher_required` decorator
- **Debug:** `?debug=countdown` ile countdown log; `DEBUG my_records` ile öğrenci paneli kayıt sayısı log
