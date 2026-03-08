# Proje ve SQLite Analiz Özeti (AI Asistan Aktarımı İçin)

## 1. Proje yapısı (klasör düzeni)

```
list_proje/
├── app.py                 # Tek ana uygulama dosyası (Flask app, modeller, tüm route'lar)
├── requirements.txt      # flask, flask-sqlalchemy, flask-login, reportlab
├── database.db           # (opsiyonel) Kök dizinde legacy DB
├── instance/             # Varsayılan yerel DB dizini (yoksa oluşturulur)
│   └── database.db       # Yerel SQLite dosyası (instance yoksa kökteki database.db kullanılır)
├── templates/            # Jinja2 HTML şablonları
│   ├── layout.html
│   ├── index.html
│   ├── login.html, register.html
│   ├── dashboard.html, create_list.html, list_detail.html
│   ├── join_form.html
│   ├── add_assignment.html, view_assignment.html
│   ├── student_assignments.html, submit_homework.html
│   └── ...
├── fonts/                # PDF için (reportlab)
├── Dockerfile
├── docker-compose.yml
└── RAILWAY_DEPLOY.md
```

- **Tek Python uygulama dosyası:** `app.py` (modeller, veritabanı bağlantısı ve tüm HTTP route'ları burada).
- **Ham `sqlite3` modülü kullanılmıyor;** tüm veritabanı erişimi **Flask-SQLAlchemy** (ORM) üzerinden.

---

## 2. Web framework

- **Framework:** **Flask**
- **ORM:** **Flask-SQLAlchemy** (SQLAlchemy wrapper)
- **Kimlik doğrulama:** **Flask-Login** (UserMixin, `current_user`, `@login_required`)
- **Veritabanı sürücüsü:** SQLAlchemy’nin varsayılan SQLite sürücüsü (`sqlite:///` URI ile; projede `import sqlite3` yok).

---

## 3. Veritabanı bağlantısı (nerede, nasıl)

**Dosya:** `app.py` (satır ~27–42)

- **URI belirleme:**
  - `DATABASE_PATH` ortam değişkeni varsa: `{DATABASE_PATH}/database.sqlite` kullanılır (ör. Railway volume).
  - Yoksa: `instance/database.db` kullanılır; `instance` yoksa kökteki `database.db` (legacy) kullanılır.
- **Bağlantı ayarları:**
  - `app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path`
  - `app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False`
- **ORM nesnesi:** `db = SQLAlchemy(app)` — tüm modeller ve `db.session` buradan.

**Tabloların oluşturulması:** Uygulama başlarken (`if __name__ == '__main__':`) `with app.app_context(): db.create_all()` ve ardından `_ensure_db_columns()` çağrılır.

---

## 4. Veritabanı modelleri / şema

Tüm modeller `app.py` içinde, `db.Model` alt sınıfı. Tablo isimleri SQLAlchemy’nin varsayılanı (snake_case, çoğul değil): `user`, `list_vera`, `student_record`, `assignment`, `homework_submission`.

| Model | Tablo | Açıklama |
|-------|--------|----------|
| **User** | `user` | `id`, `username` (unique), `password`. Flask-Login için UserMixin. `lists` → ListVera. |
| **ListVera** | `list_vera` | `id`, `title`, `description`, `unique_code` (unique), `owner_id` (FK→user), `is_completed`, `created_at`, `expires_at`. `students` → StudentRecord, `assignments` → Assignment. |
| **StudentRecord** | `student_record` | `id`, `list_id` (FK→list_vera), `name_surname`, `student_no`, `project_title`, `summary`, `submission_status` (pending/submitted/checked). |
| **Assignment** | `assignment` | `id`, `list_id` (FK→list_vera), `title`, `description`, `due_date`, `created_at`. `submissions` → HomeworkSubmission. |
| **HomeworkSubmission** | `homework_submission` | `id`, `assignment_id` (FK→assignment), `student_id` (FK→student_record), `content` (Text), `submitted_at`. Unique: (`assignment_id`, `student_id`). `student` → StudentRecord. |

İlişkiler: User → ListVera (1:N). ListVera → StudentRecord (1:N), ListVera → Assignment (1:N). Assignment → HomeworkSubmission (1:N). StudentRecord → HomeworkSubmission (1:N).

---

## 5. SQLite ile yapılan işlemlerin özeti

- **Doğrudan SQLite API’si yok:** Projede `sqlite3` import edilmez; tüm erişim **Flask-SQLAlchemy** ile:
  - `Model.query.filter_by(...).first()`, `.all()`, `.get_or_404()`
  - `db.session.add(obje)`, `db.session.delete(obje)`, `db.session.commit()`, `db.session.rollback()`
  - Ham SQL sadece migration için: `db.session.execute(text('ALTER TABLE ...'))`

**Özet işlemler:**

- **User:** Kayıt (INSERT), giriş için sorgu (SELECT by username).
- **ListVera:** Oluşturma (INSERT), kullanıcı listeleri (SELECT by owner_id), koda göre liste (SELECT by unique_code), güncelleme (is_completed, expires_at), silme (DELETE).
- **StudentRecord:** Liste bazlı ekleme (INSERT), düzenleme/silme (UPDATE/DELETE), list_id ile listeleme (relationship üzerinden).
- **Assignment:** Listeye ödev ekleme (INSERT), list_id ile listeleme, silme (DELETE); silinince ilgili HomeworkSubmission’lar da siliniyor.
- **HomeworkSubmission:** Ödev teslimi (INSERT veya aynı assignment_id+student_id için UPDATE), assignment’a göre listeleme (relationship).

**Migration:** `_ensure_db_columns()` — `sqlalchemy.inspect` ile mevcut tablo/sütunlar kontrol edilir; eksik sütunlar `ALTER TABLE ... ADD COLUMN` (raw SQL via `text()`) ile eklenir. Sonunda `db.create_all()` ile yeni tablolar oluşturulur.

---

## 6. Kısa tek paragraf özet (kopyala-yapıştır)

Bu proje **Flask** kullanıyor; veritabanı erişimi **Flask-SQLAlchemy** (SQLite) ile yapılıyor, ham **sqlite3** yok. Tüm kod **app.py** içinde: bağlantı `SQLALCHEMY_DATABASE_URI` ile `sqlite:///` + path (ortamda `DATABASE_PATH` varsa orada, yoksa `instance/database.db` veya kökteki `database.db`). Beş model var: **User** (giriş), **ListVera** (listeler), **StudentRecord** (listeye kayıtlı öğrenci), **Assignment** (liste bazlı ödev), **HomeworkSubmission** (ödev teslimi; assignment+student unique). İşlemler tamamen ORM (query, add, commit, delete); ham SQL sadece `_ensure_db_columns()` içinde ALTER TABLE migration için kullanılıyor. Tablolar uygulama başlarken `db.create_all()` ve migration ile güncelleniyor.
