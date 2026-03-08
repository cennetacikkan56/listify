# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, send_from_directory, jsonify, abort
from flask_sqlalchemy import SQLAlchemy  
from sqlalchemy import func
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False
import random
import string
import os
import io
import logging
import secrets
import uuid
import json
from datetime import datetime, timedelta, timezone
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
try:
    from zoneinfo import ZoneInfo
    _TZ_ISTANBUL = ZoneInfo('Europe/Istanbul')
except ImportError:
    import pytz
    _TZ_ISTANBUL = pytz.timezone('Europe/Istanbul')
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from itsdangerous import URLSafeTimedSerializer
try:
    import magic
    HAS_PYTHON_MAGIC = True
except ImportError:
    HAS_PYTHON_MAGIC = False
    magic = None

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'cok-gizli-bir-anahtar-123')
# ESKİ HALİ: app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'gecici-anahtar')
# YENİ HALİ (Bunu yapıştır):
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SESSION_COOKIE_SECURE'] = False  # True + HTTP ile acilinca redirect dongusu olur; gecici False
app.config['JSON_AS_ASCII'] = False  # JSON cevaplarda Turkce karakterlerin dogru gosterilmesi icin

# Veritaban yolu - Railway Volume (/data) veya yerel
basedir = os.path.abspath(os.path.dirname(__file__))
data_dir = os.environ.get('DATABASE_PATH')
if data_dir:
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, 'database.sqlite')
else:
    instance_dir = os.path.join(basedir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    legacy_db = os.path.join(basedir, 'database.db')
    db_path = legacy_db if os.path.isfile(legacy_db) else os.path.join(instance_dir, 'database.db')

# DATABASE_URL varsa (Railway/Heroku PostgreSQL) onu kullan, yoksa SQLite
uri = os.environ.get('DATABASE_URL')
if uri:
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = uri
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# dev dosya ykleme: guvenlik icin sadece belirli uzantilar. HTML/SVG gibi script barindirabilecek dosyalar engellendi.
UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'zip', 'docx'}
ALLOWED_MIMETYPES = {
    'application/pdf',
    'image/png', 'image/jpeg', 'image/jpg',
    'application/zip', 'application/x-zip-compressed',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}
BLOCKED_MIMETYPES = {
    'text/html', 'text/javascript', 'application/javascript',
    'image/svg+xml', 'application/x-msdownload', 'application/x-executable',
    'application/x-sh', 'text/x-python', 'application/x-httpd-php',
}
MAX_UPLOAD_MB = 5
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_MB * 1024 * 1024

# E-posta: SendGrid Web API kullaniliyor. Gonderim icin MAIL_PASSWORD (SendGrid API Key)
# ve MAIL_DEFAULT_SENDER yeterli. MAIL_DEFAULT_SENDER, SendGrid panelinde dogrulanmis
# (verified) gonderici e-posta adresiyle AYNI olmali; aksi halde mail gonderimi reddedilir.
# MAIL_SERVER/MAIL_PORT SMTP icindir (kullanilmiyor).
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', '587'))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('true', '1', 'yes')
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'listify.otomasyon@gmail.com')
# ESKİ HALİ: app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'bcpdedwvoihjspgb')
# YENİ HALİ (Bunu yapıştır):
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'listify.otomasyon@gmail.com')

db = SQLAlchemy(
    app,
    engine_options={
        "pool_pre_ping": True,
        "pool_recycle": 300,
    },
)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Bu sayfaya erimek iin giri yapmalsnz.'

# --- VERTABANI MODELLER ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='student', nullable=False)
    full_name = db.Column(db.String(200), nullable=True)
    student_number = db.Column(db.String(20), unique=True, nullable=True)
    email = db.Column(db.String(254), nullable=True)  # For forgot password
    # is_verified gecici olarak nullable=True yapildi; mevcut kullanicilar icin null olabilir
    is_verified = db.Column(db.Boolean, default=False, nullable=True)
    reset_token = db.Column(db.String(64), nullable=True)
    token_expiry = db.Column(db.DateTime, nullable=True)
    verification_code = db.Column(db.String(6), nullable=True)
    code_expiry = db.Column(db.DateTime, nullable=True)
    lists = db.relationship('ListVera', backref='owner', lazy=True)
    student_records = db.relationship('StudentRecord', backref='user', lazy=True)

class ListVera(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    unique_code = db.Column(db.String(10), unique=True, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)  # Sre dolunca veri eklenemez
    announcement = db.Column(db.Text, nullable=True)  # Liste duyurusu
    students = db.relationship(
        'StudentRecord',
        backref='parent_list',
        lazy=True,
        cascade='all, delete-orphan'
    )
    assignments = db.relationship(
        'Assignment',
        backref='parent_list',
        lazy=True,
        order_by='Assignment.created_at',
        cascade='all, delete-orphan'
    )

    def is_accepting_entries(self):
        """Liste yeni kayt/teslim kabul ediyor mu? Europe/Istanbul referansl (UTC ile karlatrma)."""
        if self.is_completed:
            return False
        now_utc = _now_istanbul().astimezone(timezone.utc).replace(tzinfo=None)
        if self.expires_at and now_utc >= self.expires_at:
            return False
        return True

    def check_and_mark_expired(self):
        """Sre dolduysa listeyi otomatik tamamland iaretle (Europe/Istanbul)."""
        if self.expires_at and not self.is_completed:
            now_utc = _now_istanbul().astimezone(timezone.utc).replace(tzinfo=None)
            if now_utc >= self.expires_at:
                self.is_completed = True
                db.session.commit()

# dev teslim durumu: pending, submitted, checked
SUBMISSION_STATUSES = [
    ('pending', 'Beklemede'),
    ('submitted', 'Teslim edildi'),
    ('checked', 'Kontrol edildi'),
]

# Proje onay durumu (liste kayd)
APPROVAL_STATUSES = [
    ('pending', 'Beklemede'),
    ('approved', 'Onayland'),
    ('rejected', 'Reddedildi'),
]

class StudentRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('list_vera.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name_surname = db.Column(db.String(100))
    student_no = db.Column(db.String(20))
    project_title = db.Column(db.String(200))
    summary = db.Column(db.Text)
    teacher_feedback = db.Column(db.Text, nullable=True)
    submission_status = db.Column(db.String(20), default='pending', nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)  # Onay: pending, approved, rejected
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)

    def status_label(self):
        return dict(SUBMISSION_STATUSES).get(self.submission_status, 'Beklemede')

    def approval_label(self):
        return dict(APPROVAL_STATUSES).get(self.status, 'Beklemede')

    @property
    def display_name(self):
        """user_id varsa User.full_name, yoksa kayttaki name_surname (veri tutarll)."""
        if self.user_id and self.user and self.user.full_name:
            return self.user.full_name
        return self.name_surname or ''

    @property
    def display_student_no(self):
        """user_id varsa User.student_number, yoksa kayttaki student_no."""
        if self.user_id and self.user and self.user.student_number:
            return self.user.student_number
        return self.student_no or ''


class Assignment(db.Model):
    """Listeye eklenen dev (balk, son tarih)."""
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('list_vera.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    submissions = db.relationship('Submission', backref='assignment', lazy=True, cascade='all, delete-orphan')

    def is_submission_open(self):
        """dev teslimi ak m? due_date yoksa veya henz gemediyse True (Europe/Istanbul referansl)."""
        if not self.due_date:
            return True
        now_utc = _now_istanbul().astimezone(timezone.utc).replace(tzinfo=None)
        return now_utc < self.due_date


class Submission(db.Model):
    """dev teslimi: dosya yolu, not ve revizyon durumu."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(255), nullable=True)
    grade = db.Column(db.String(20), nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    revision_requested = db.Column(db.Boolean, default=False, nullable=False)
    user = db.relationship('User', backref=db.backref('submissions', lazy=True))
    __table_args__ = (db.UniqueConstraint('assignment_id', 'user_id', name='uq_assignment_user'),)

@login_manager.user_loader
def load_user(user_id):
    """Flask-Login: session'dan user_id okunurken hata nleme."""
    if user_id is None:
        return None
    try:
        uid = int(user_id)
        return User.query.get(uid)
    except (ValueError, TypeError):
        return None

# --- YARDIMCI FONKSYONLAR ---
def generate_random_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def allowed_file(filename):
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    if not ext.isalnum() or len(ext) > 5:
        return False
    if ext in ('html', 'htm', 'svg', 'svgz', 'js', 'exe', 'sh', 'py', 'php'):
        return False
    return ext in ALLOWED_EXTENSIONS


def allowed_mimetype(content_type):
    """MIME-type dogrulamasi. Tehlikeli tipleri engelle, sadece izin verilenlere izin ver."""
    if not content_type or ';' in content_type:
        ct = (content_type or '').split(';')[0].strip().lower()
    else:
        ct = (content_type or '').strip().lower()
    if ct in BLOCKED_MIMETYPES:
        return False
    if ct in ALLOWED_MIMETYPES:
        return True
    if ct in ('application/octet-stream', ''):
        return None
    return False


def validate_file_content_magic(file_storage):
    """
    python-magic ile dosya iceriginin gercek MIME tipini dogrula.
    Tarayicidan gelen content_type'a guvenme; dosyayi okuyup magic.from_buffer() ile
    gercek turunu kontrol et. Uzantisi .jpg ama icerigi text/html ise reddet.
    Returns: (ok: bool, error_message: str|None)
        (True, None) -> guvenli, devam et
        (False, "Dosya icerigi guvenli degil") -> zararli veya izin verilmeyen tip
        (False, "Dosya kontrolu sirasinda bir hata olustu...") -> kutuphane eksikligi vb.
    """
    if not HAS_PYTHON_MAGIC or magic is None:
        return (False, "Dosya güvenlik kontrolü şu an kullanılamıyor. Lütfen daha sonra tekrar deneyin.")
    try:
        stream = getattr(file_storage, 'stream', file_storage)
        if hasattr(stream, 'seek'):
            stream.seek(0)
        raw = stream.read(8192)
        if hasattr(stream, 'seek'):
            stream.seek(0)
        if not raw:
            return (False, "Dosya içeriği güvenli değil.")
        mime = magic.from_buffer(raw, mime=True)
        if not mime:
            return (False, "Dosya içeriği güvenli değil.")
        mime = (mime or '').strip().lower()
        if mime in BLOCKED_MIMETYPES:
            return (False, "Dosya içeriği güvenli değil.")
        if mime in ALLOWED_MIMETYPES:
            return (True, None)
        return (False, "Dosya içeriği güvenli değil.")
    except Exception as e:
        logger.warning("validate_file_content_magic hata: %s", str(e))
        return (False, "Dosya kontrolü sırasında bir hata oluştu. Lütfen tekrar deneyin.")


def _upload_response(request, ok, message, redirect_url=None):
    """XHR isteklerinde JSON doner (modal hata gosterimi icin), digerinde redirect+flash."""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if ok:
            return jsonify({"ok": True, "message": message, "redirect_url": redirect_url})
        return jsonify({"ok": False, "error": message})
    if ok:
        flash(message, "success")
        return redirect(redirect_url or url_for('my_records'))
    flash(message, "danger")
    return redirect(request.referrer or url_for('my_records'))


def _safe_submission_path(file_path):
    """Validate file_path to prevent directory traversal. Returns path if safe, else None."""
    if not file_path or '..' in file_path or file_path.startswith('/') or file_path.startswith('\\'):
        return None
    base = os.path.abspath(app.config['UPLOAD_FOLDER'])
    full = os.path.normpath(os.path.join(base, file_path))
    if not full.startswith(base) or not os.path.isfile(full):
        return None
    return file_path


def _now_istanbul():
    """Europe/Istanbul (UTC+3) - tm sistem saatleri Trkiye ile senkron."""
    return datetime.now(_TZ_ISTANBUL)


def _compute_due_from_engine(unit: str, amount: int):
    """Time Engine: unit (ay/hafta/gun/saat/dakika) + amount -> UTC naive datetime (Europe/Istanbul referansl)."""
    if not amount or amount <= 0:
        return None
    now = _now_istanbul()
    units = {'ay': 30, 'hafta': 7, 'gun': 1, 'saat': 1/24, 'dakika': 1/(24*60)}
    days = 0
    if unit == 'ay':
        days = amount * 30
    elif unit == 'hafta':
        days = amount * 7
    elif unit == 'gun':
        days = amount
    elif unit == 'saat':
        days = amount / 24
    elif unit == 'dakika':
        days = amount / (24 * 60)
    else:
        return None
    target = now + timedelta(days=days)
    return target.astimezone(timezone.utc).replace(tzinfo=None)


def _to_istanbul_iso(dt):
    """Naive UTC datetime -> ISO 8601 string with +03:00 (Europe/Istanbul). Frontend iin."""
    if dt is None:
        return ''
    utc_dt = dt.replace(tzinfo=timezone.utc)
    ist = utc_dt.astimezone(_TZ_ISTANBUL)
    return ist.strftime('%Y-%m-%dT%H:%M:%S') + '+03:00'


def _ensure_upload_dirs():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def teacher_required(f):
    """Sadece role='teacher' olan kullanclar eriebilir."""
    from functools import wraps
    @wraps(f)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if getattr(current_user, 'role', None) != 'teacher':
            flash('Bu sayfaya eriim yetkiniz yok. Sadece eitmenler listeleri ynetebilir.', 'warning')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_view


@app.template_filter('istanbul_iso')
def istanbul_iso_filter(dt):
    """Jinja filter: Naive UTC datetime -> ISO 8601 +03:00 (Europe/Istanbul)."""
    return _to_istanbul_iso(dt)


# --- KISITLAMASIZ ERISIM: before_request icinde HICBIR yonlendirme yok ---
# Kullanici dogrulama yapmadan tum sayfalari (Profil, Kayitlarim vb.) gezebilir.
_db_startup_done = False

@app.before_request
def _run_db_startup_once():
    global _db_startup_done
    if _db_startup_done:
        return
    try:
        _ensure_db_columns()
        convert_all_passwords()
        _test_mail_send()
        _db_startup_done = True
    except Exception:
        pass


@app.context_processor
def inject_is_verified():
    """Tum sablonlarda is_verified guvenli kullanilsin: current_user.is_verified yoksa False."""
    if current_user.is_authenticated:
        return {'is_verified': getattr(current_user, 'is_verified', False)}
    return {'is_verified': False}


# --- ROTALAR (ROUTES) ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_name = (request.form.get('username') or '').strip()
        pass_word = request.form.get('password') or ''
        pass_confirm = request.form.get('password_confirm') or ''
        email_val = (request.form.get('email') or '').strip().lower() or None
        role = (request.form.get('role') or 'student').strip().lower()
        if role not in ('teacher', 'student'):
            role = 'student'
        full_name = request.form.get('full_name', '').strip() or None
        student_number = request.form.get('student_number', '').strip() or None
        if not user_name:
            flash("Kullanici adi gerekli.", "warning")
            return redirect(url_for('register'))
        if not pass_word:
            flash("Sifre gerekli.", "warning")
            return redirect(url_for('register'))
        if pass_word != pass_confirm:
            flash("Sifreler eslesmiyor.", "warning")
            return redirect(url_for('register'))
        if role == 'student':
            if not full_name:
                flash("Ogrenci kaydi icin Ad-Soyad gereklidir.", "warning")
                return redirect(url_for('register'))
            if not student_number:
                flash("Ogrenci kaydi icin Ogrenci Numarasi gereklidir.", "warning")
                return redirect(url_for('register'))
        elif role == 'teacher':
            student_number = None
        # E-posta zaten kayitliysa engelle (buyuk/kucuk harf duyarsiz)
        if email_val:
            existing_email = User.query.filter(db.func.lower(User.email) == email_val).first()
            if existing_email:
                flash("Bu e-posta adresi zaten kayitli. Lutfen baska bir tane deneyin.", "danger")
                return redirect(url_for('register'))
        user_exists = User.query.filter_by(username=user_name).first()
        if user_exists:
            flash("Bu kullanici adi zaten alinmis!", "danger")
            return redirect(url_for('register'))
        if role == 'student' and student_number:
            existing_num = User.query.filter_by(student_number=student_number).first()
            if existing_num:
                flash("Bu ogrenci numarasi ile zaten bir kayit mevcut.", "warning")
                return redirect(url_for('register'))
        try:
            new_user = User(
                username=user_name, password=generate_password_hash(pass_word, method='pbkdf2:sha256'), role=role,
                full_name=full_name, student_number=student_number,
                email=email_val
            )
            new_user.is_verified = False
            db.session.add(new_user)
            db.session.commit()
            if email_val:
                ok, err = send_verification_email(new_user)
                if ok:
                    flash("Dogrulama e-postasi gonderildi. Lutfen e-postanizi kontrol edin.", "success")
                else:
                    flash(f"Dogrulama e-postasi gonderilemedi: {err}", "warning")
            return redirect(url_for('login'))
        except IntegrityError:
            db.session.rollback()
            flash("Kayit sirasinda bir hata olustu. Kullanici adi, e-posta veya ogrenci numarasi zaten kullaniliyor olabilir.", "danger")
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if 'show_security_note' not in session:
        session['show_security_note'] = True
    if request.method == 'POST':
        user_name = (request.form.get('username') or '').strip()
        pass_word = request.form.get('password') or ''
        if not user_name or not pass_word:
            flash("Kullanici adi ve sifre gerekli.", "warning")
            return redirect(url_for('login'))
        user = User.query.filter_by(username=user_name).first()
        if user:
            try:
                password_ok = check_password_hash(user.password, pass_word)
            except Exception:
                password_ok = False
            if not password_ok and user.password == pass_word:
                # Yumusak gecis: eski duz metin sifre dogruysa hemen hash'le ve kalici kaydet
                user.password = generate_password_hash(pass_word, method='pbkdf2:sha256')
                try:
                    db.session.commit()
                    print("DEBUG: Sifre hashlenerek guncellendi!")
                except Exception:
                    db.session.rollback()
                password_ok = True
            if password_ok:
                login_user(user)
                session.pop('show_security_note', None)
                if getattr(user, 'role', None) == 'teacher':
                    return redirect(url_for('dashboard'))
                return redirect(url_for('my_records'))
        flash("Hatali kullanici adi veya sifre!", "danger")
    show_note = session.get('show_security_note', False)
    session['show_security_note'] = False
    return render_template('login.html', show_security_note=show_note)


SENDGRID_URL = 'https://api.sendgrid.com/v3/mail/send'


def _test_mail_send():
    """Mail gonderimini test et; MAIL_ ayarlarini ve sonucu loglara yaz. (Bir kerelik cagrilir.)"""
    api_key = os.environ.get('MAIL_PASSWORD')
    sender = os.environ.get('MAIL_DEFAULT_SENDER') or app.config.get('MAIL_DEFAULT_SENDER') or 'listify.otomasyon@gmail.com'
    sender = (sender or '').strip() if isinstance(sender, str) else 'listify.otomasyon@gmail.com'
    logger.info("Mail ayarlari: MAIL_PASSWORD=%s, MAIL_DEFAULT_SENDER=%s", "tanimli" if (api_key and str(api_key).strip()) else "eksik", sender or "eksik")
    if not api_key or not str(api_key).strip():
        logger.warning("Mail test: MAIL_PASSWORD eksik, gonderim atlandi.")
        return
    to = sender or 'listify.otomasyon@gmail.com'
    ok, err = _send_sendgrid_email(
        to,
        "Listify Mail Test",
        "<p>Bu bir test postasidir. Mail altyapisi calisiyor.</p>",
        "Listify mail test - altyapi calisiyor.",
    )
    if ok:
        logger.info("Mail test: gonderim basarili.")
    else:
        logger.warning("Mail test: gonderim basarisiz - %s", err or "bilinmeyen hata")


def _send_sendgrid_email(to_email, subject, html_body, plain_text=None):
    """Send an email using SendGrid Web API (HTTP).

    Env:
      - MAIL_PASSWORD: SendGrid API Key
      - MAIL_DEFAULT_SENDER: verified sender address
    """
    try:
        api_key = os.environ.get('MAIL_PASSWORD')
        if not api_key or not str(api_key).strip():
            msg = "E-posta ayarları eksik: MAIL_PASSWORD (SendGrid API Key)"
            logger.warning(msg)
            return False, msg
        default_sender = os.environ.get('MAIL_DEFAULT_SENDER') or 'listify.otomasyon@gmail.com'
        default_sender = str(default_sender).strip() if default_sender else 'listify.otomasyon@gmail.com'
        if not plain_text:
            plain_text = "Bu e-postayı düz metin olarak görüntülemek için HTML destekli bir e-posta istemcisi kullanın."

        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": default_sender, "name": "Listify"},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": plain_text},
                {"type": "text/html", "value": html_body},
            ],
            "tracking_settings": {
                "click_tracking": {"enable": False},
                "open_tracking": {"enable": False},
            },
        }
        # ensure_ascii=False: Turkish characters stay intact
        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json; charset=utf-8",
        }
        if HAS_REQUESTS:
            r = requests.post(SENDGRID_URL, data=body_bytes, headers=headers, timeout=30)
            if r.status_code >= 400:
                err_msg = f"SendGrid HTTP {r.status_code}: {(r.text or '')[:300]}"
                logger.warning("SendGrid API error: %s", err_msg)
                return False, err_msg
            return True, None
        req = Request(SENDGRID_URL, data=body_bytes, headers=headers, method="POST")
        with urlopen(req, timeout=30) as resp:
            code = resp.getcode()
            if code >= 400:
                err_msg = f"SendGrid HTTP {code}"
                return False, err_msg
            return True, None
    except HTTPError as e:
        err_msg = f"SendGrid HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:300] if e.fp else ''}"
        logger.exception("SendGrid email failed: %s", err_msg)
        return False, err_msg
    except URLError as e:
        err_msg = str(e.reason) if getattr(e, "reason", None) else str(e)
        logger.exception("SendGrid email failed: %s", err_msg)
        return False, err_msg
    except Exception as e:
        err_msg = str(e)
        logger.exception("SendGrid email failed: %s", err_msg)
        return False, err_msg


def _send_password_reset_email(to_email, reset_url):
    plain_text = (
        "Şifrenizi sıfırlamak için aşağıdaki bağlantıyı tıklayın (24 saat geçerlidir):\n\n"
        f"{reset_url}\n\n"
        "Bu talebi siz yapmadıysanız bu e-postayı dikkate almayın."
    )
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><style>
    body {{ font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; color: #1a1a1a; margin: 0; padding: 24px; background: #f5f5f5; }}
    .container {{ max-width: 480px; margin: 0 auto; background: #fff; border-radius: 12px; padding: 32px; box-shadow: 0 4px 6px rgba(0,0,0,0.08); }}
    h2 {{ margin: 0 0 16px; font-size: 1.25rem; color: #111; }}
    p {{ margin: 0 0 24px; font-size: 0.9375rem; }}
    .btn {{ display: inline-block; background: #007bff; color: #fff !important; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: 600; font-size: 0.9375rem; }}
    .btn:hover {{ background: #0056b3; }}
    .muted {{ color: #6b7280; font-size: 0.8125rem; margin-top: 24px; }}
    </style></head>
    <body>
    <div class="container">
    <h2>Listify — Şifre Sıfırlama</h2>
    <p>Şifrenizi sıfırlamak için aşağıdaki düğmeye tıklayın. Bağlantı 24 saat içinde geçerlidir.</p>
    <p><a href="{reset_url}" class="btn">Şifreyi Sıfırla</a></p>
    <p class="muted">Bu talebi siz yapmadıysanız bu e-postayı dikkate almayın.</p>
    </div>
    </body>
    </html>
    """
    return _send_sendgrid_email(to_email, "Listify - Şifre Sıfırlama", html_body, plain_text)


def send_verification_email(user):
    """6 haneli OTP uretir, veritabanina yazar ve e-posta ile gonderir (SendGrid)."""
    if not user or not getattr(user, "email", None):
        return False, "E-posta adresi tanimli degil."
    code = str(random.randint(100000, 999999))
    user.verification_code = code
    user.code_expiry = datetime.utcnow() + timedelta(minutes=10)
    logger.info("Dogrulama kodu gonderiliyor: email=%s, kod=%s", user.email, code)
    print(">>> TEST KODU: %s <<<" % code)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return False, "Kod kaydedilemedi."
    plain_text = "Merhaba, Listify doğrulama kodunuz: %s. Bu kod 10 dakika geçerlidir." % code
    subject = "Onay Kodunuz: %s" % code
    return _send_sendgrid_email(user.email, subject, plain_text, plain_text)


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        if not email:
            flash("E-posta adresi girin.", "warning")
            return redirect(url_for('forgot_password'))
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if not user or not user.email:
            flash("Bu e-posta adresiyle kayitli bir hesap bulunamadi.", "danger")
            return redirect(url_for('forgot_password'))
        serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        token = serializer.dumps({'user_id': user.id}, salt='password-reset')
        user.reset_token = token
        user.token_expiry = datetime.utcnow() + timedelta(hours=24)
        try:
            db.session.commit()
            print("[Reset] token_created user_id=%s email=%s secret_key_used=True token_prefix=%s" % (user.id, user.email, token[:12] + "..."))
            reset_url = url_for('reset_password', token=token, _external=True)
            ok, err = _send_password_reset_email(user.email, reset_url)
            if ok:
                flash("Sifre sifirlama baglantisi e-posta adresinize gonderildi.", "success")
            else:
                flash(f"E-posta gonderilemedi: {err}", "danger")
        except Exception:
            db.session.rollback()
            flash("Bir hata olustu. Lutfen tekrar deneyin.", "danger")
            return redirect(url_for('forgot_password'))
        return redirect(url_for('login'))
    return render_template('forgot_password.html')


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    print('KONTROL: KOD GUNCEL - 24 SAAT KURALI AKTIF')
    token = request.args.get('token') or request.form.get('token') or ''
    token = (token or '').strip()
    if token and request.args.get('token'):
        token = token.replace(' ', '+')
    if not token:
        flash("Gecersiz veya eksik sifre sifirlama baglantisi.", "danger")
        return redirect(url_for('login'))
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    user = None
    try:
        data = serializer.loads(token, max_age=7200, salt='password-reset')
        user_id = data.get('user_id')
        if user_id is not None:
            user = User.query.get(user_id)
            if user and user.reset_token != token:
                user = None
    except Exception as e:
        print("[Reset] token_load failed: %s" % str(e))
    now_utc = datetime.utcnow()
    expiry_naive = None
    if user and user.token_expiry:
        et = user.token_expiry
        if getattr(et, 'tzinfo', None) is not None:
            expiry_naive = et.astimezone(timezone.utc).replace(tzinfo=None)
        else:
            expiry_naive = et.replace(tzinfo=None) if hasattr(et, 'replace') else et
    expired = expiry_naive is not None and now_utc > expiry_naive
    print("[Reset] token_load secret_key_used=True token_prefix=%s user_found=%s user_id=%s email=%s expired=%s" % (
        token[:12] + "..." if len(token) > 12 else token,
        user is not None,
        user.id if user else None,
        user.email if user else None,
        expired,
    ))
    if not user:
        flash("Gecersiz veya suresi dolmus sifre sifirlama baglantisi.", "danger")
        return redirect(url_for('login'))
    try:
        exp = user.token_expiry
        if exp is None:
            is_expired = False
        elif getattr(exp, 'tzinfo', None) is not None:
            is_expired = now_utc > exp.astimezone(timezone.utc).replace(tzinfo=None)
        else:
            is_expired = now_utc > (exp.replace(tzinfo=None) if hasattr(exp, 'replace') else exp)
    except (TypeError, ValueError):
        is_expired = False
    if is_expired:
        user.reset_token = None
        user.token_expiry = None
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        flash("Sifirlama baglantisinin suresi dolmus. Lutfen tekrar deneyin.", "danger")
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        new_pass = request.form.get('new_password') or ''
        confirm = request.form.get('confirm_password') or ''
        if not new_pass or len(new_pass) < 4:
            flash("Sifre en az 4 karakter olmalidir.", "warning")
            return redirect(url_for('reset_password', token=token))
        if new_pass != confirm:
            flash("Sifreler eslesmiyor.", "warning")
            return redirect(url_for('reset_password', token=token))
        # Sifremi Unuttum akisi: yeni sifre pbkdf2:sha256 ile hashlenip kaydediliyor
        user.password = generate_password_hash(new_pass, method='pbkdf2:sha256')
        user.reset_token = None
        user.token_expiry = None
        user.is_verified = True  # E-posta linkine erisim kanitlandi, ek OTP gerekmez
        try:
            db.session.commit()
            flash("Sifreniz basariyla guncellendi. Giris yapabilirsiniz.", "success")
            return redirect(url_for('login'))
        except Exception:
            db.session.rollback()
            flash("Bir hata olustu. Lutfen tekrar deneyin.", "danger")
            return redirect(url_for('reset_password', token=token))
    try:
        return render_template('reset_password.html', token=token)
    except Exception as e:
        logger.exception("reset_password template error: %s", str(e))
        flash("Sayfa yuklenirken hata olustu. Lutfen tekrar deneyin.", "danger")
        return redirect(url_for('login'))


@app.route('/resend-verification', methods=['POST'])
@login_required
def resend_verification():
    """Mevcut kullanici icin e-posta dogrulama mailini tekrar gonder."""
    try:
        # Zaten doğrulanmışsa tekrar göndermeye gerek yok
        if getattr(current_user, 'is_verified', False):
            flash("E-posta adresiniz zaten dogrulanmis.", "info")
            return redirect(url_for('index'))
        # E-posta tanımlı değilse önce profil sayfasına yönlendir
        if not getattr(current_user, 'email', None):
            flash("Hesabiniz icin tanimli bir e-posta adresi bulunmuyor. Lutfen profil sayfasindan ekleyin.", "warning")
            return redirect(url_for('profile'))
        ok, err = send_verification_email(current_user)
        if ok:
            flash("Dogrulama kodu e-postaniza gonderildi. 10 dakika gecerli.", "success")
            return redirect(url_for('verify_code', sent=1))
        else:
            flash(f"Dogrulama kodu gonderilemedi: {err}", "danger")
    except Exception as e:
        logger.exception("resend_verification failed: %s", str(e))
        flash("Dogrulama kodu gonderilirken beklenmeyen bir hata olustu.", "danger")
    return redirect(request.referrer or url_for('verify_code'))


@app.route('/profile/add-email-send-verification', methods=['POST'])
@login_required
def add_email_send_verification():
    """E-posta ekleyip dogrulama maili gonderir (Profil/Dashboard uyari bandindan)."""
    email_val = (request.form.get('email') or '').strip().lower()
    if not email_val:
        flash("E-posta adresi girin.", "warning")
        return redirect(request.referrer or url_for('profile'))
    current_user.email = email_val
    current_user.is_verified = False
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("E-posta kaydedilirken hata olustu.", "danger")
        return redirect(request.referrer or url_for('profile'))
    ok, err = send_verification_email(current_user)
    if ok:
        flash("Dogrulama maili adresinize gonderildi!", "success")
    else:
        flash("Dogrulama maili gonderilemedi: %s" % (err or "bilinmeyen hata"), "danger")
    return redirect(request.referrer or url_for('profile'))


@app.route('/verify-code', methods=['GET', 'POST'])
@login_required
def verify_code():
    """6 haneli OTP ile e-posta dogrulama."""
    if getattr(current_user, 'is_verified', False):
        flash("Hesabiniz zaten dogrulanmis.", "info")
        return redirect(url_for('dashboard') if getattr(current_user, 'role', None) == 'teacher' else url_for('my_records'))
    if request.method == 'POST':
        code_raw = (request.form.get('code') or '').strip().replace(' ', '')
        if not code_raw or len(code_raw) != 6 or not code_raw.isdigit():
            flash("Gecerli 6 haneli kodu girin.", "warning")
            return redirect(url_for('verify_code'))
        stored = getattr(current_user, 'verification_code', None) or ''
        expiry = getattr(current_user, 'code_expiry', None)
        now = datetime.utcnow()
        if expiry and getattr(expiry, 'tzinfo', None):
            expiry = expiry.replace(tzinfo=None) if expiry.tzinfo else expiry
        expired = expiry is not None and now > expiry
        if stored != code_raw or expired:
            flash("Kod gecersiz veya suresi dolmus. Yeni kod icin maili tekrar gonderin.", "danger")
            return redirect(url_for('verify_code'))
        current_user.is_verified = True
        current_user.verification_code = None
        current_user.code_expiry = None
        try:
            db.session.commit()
            logger.info("E-posta dogrulandi (OTP): user_id=%s", current_user.id)
            flash("Dogrulanmis Hesap! Hesabiniz basariyla dogrulandi.", "success")
        except Exception:
            db.session.rollback()
            flash("Kayit sirasinda hata olustu.", "danger")
            return redirect(url_for('verify_code'))
        return redirect(url_for('dashboard') if getattr(current_user, 'role', None) == 'teacher' else url_for('my_records'))
    code_sent = request.args.get('sent') == '1'
    return render_template('verify_code.html', code_sent=code_sent)


@app.route('/verify-email/<token>')
def verify_email(token):
    """Eski link dogrulama; yonlendir (artik OTP kullaniliyor)."""
    flash("Link ile dogrulama kapatildi. E-posta ile gelen 6 haneli kodu girin.", "info")
    if current_user.is_authenticated:
        return redirect(url_for('verify_code'))
    return redirect(url_for('login', next=url_for('verify_code')))


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(error):
    msg = "Dosya boyutu çok büyük. Maksimum %d MB yükleyebilirsiniz. Daha küçük bir dosya yükleyin." % MAX_UPLOAD_MB
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"ok": False, "error": msg}), 413
    flash(msg, "danger")
    referrer = request.referrer
    if referrer and ('list-join' in referrer or 'assignment' in referrer or 'my-records' in referrer):
        return redirect(url_for('my_records'))
    return redirect(referrer or url_for('index'))


@app.errorhandler(413)
def handle_413(_error):
    return handle_file_too_large(None)


@app.errorhandler(IntegrityError)
def handle_integrity_error(error):
    """Veritabanı kısıt ihlali (unique, foreign key vb.)"""
    db.session.rollback()
    flash("İşlem veritabanı kısıtı nedeniyle başarısız oldu. Lütfen verileri kontrol edin.", "danger")
    return redirect(request.referrer or url_for('index'))


@app.errorhandler(500)
def handle_500(error):
    """Genel sunucu hatası - uygulama çökmesini önler."""
    db.session.rollback()
    logger.exception("500 Internal Server Error")
    flash("Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.", "danger")
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
@teacher_required
def dashboard():
    user_lists = ListVera.query.filter_by(owner_id=current_user.id, is_deleted=False).all()
    for lst in user_lists:
        lst.check_and_mark_expired()
        active = [s for s in lst.students if not getattr(s, 'is_deleted', False)]
        lst._has_pending = any(s.status != 'approved' for s in active)
        lst._student_count = len(active)
    stat_total_lists = len(user_lists)
    stat_total_students = sum(len([s for s in lst.students if not getattr(s, 'is_deleted', False)]) for lst in user_lists)
    stat_total_submissions = 0
    stat_approved = 0
    for lst in user_lists:
        active = [s for s in lst.students if not getattr(s, 'is_deleted', False)]
        stat_approved += sum(1 for s in active if s.status == 'approved')
        stat_total_submissions += sum(1 for a in lst.assignments for sub in a.submissions if sub.file_path)
    stat_approval_rate = round((stat_approved / stat_total_students * 100) if stat_total_students else 0)
    is_verified = getattr(current_user, 'is_verified', False)
    return render_template(
        'dashboard.html',
        listeler=user_lists,
        is_verified=is_verified,
        stat_total_lists=stat_total_lists,
        stat_total_students=stat_total_students,
        stat_total_submissions=stat_total_submissions,
        stat_approval_rate=stat_approval_rate,
    )

@app.route('/create-list', methods=['GET', 'POST'])
@login_required
@teacher_required
def create_list():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip() or None
        if not title:
            flash("Liste bal gerekli.", "warning")
            return redirect(url_for('create_list'))
        code = generate_random_code().strip().upper()
        expires_at = None
        exp_unit = request.form.get('expires_unit', '').strip()
        exp_amount = request.form.get('expires_amount', '').strip()
        if exp_unit and exp_amount and exp_amount.isdigit():
            expires_at = _compute_due_from_engine(exp_unit, int(exp_amount))
        try:
            new_list = ListVera(
                title=title, description=description, unique_code=code,
                owner_id=current_user.id, expires_at=expires_at
            )
            db.session.add(new_list)
            db.session.commit()
            return redirect(url_for('dashboard'))
        except IntegrityError:
            db.session.rollback()
            flash("Liste oluturulurken hata olutu. Ltfen tekrar deneyin.", "danger")
            return redirect(url_for('create_list'))
    return render_template('create_list.html')

@app.route('/join', methods=['POST'])
def join_list():
    code = (request.form.get('list_code') or '').strip().upper()
    go_to_assignments = request.form.get('action') == 'assignments'
    logger.info("join_list: Searching for list with normalized code=%r (len=%d)", code, len(code))
    target_list = ListVera.query.filter(
        func.upper(func.trim(ListVera.unique_code)) == code,
        ListVera.is_deleted == False
    ).first()
    if target_list:
        logger.info("join_list: Found list id=%s title=%r", target_list.id, target_list.title)
        if go_to_assignments:
            return redirect(url_for('list_assignments_student', list_id=target_list.id))
        return redirect(url_for('show_join_form', list_id=target_list.id))
    try:
        all_codes = [r[0] for r in ListVera.query.filter_by(is_deleted=False).with_entities(ListVera.unique_code).limit(20).all()]
    except Exception as e:
        all_codes = []
        logger.exception("join_list: Could not fetch sample codes: %s", e)
    logger.warning("join_list: List not found for code=%r. Sample codes in DB: %s", code, all_codes)
    flash('Hatal kod! Byle bir liste bulunamad. Ltfen kodu kontrol edin.', 'danger')
    dest = url_for('my_records') if current_user.is_authenticated and getattr(current_user, 'role', None) == 'student' else url_for('index')
    return redirect(dest)



def _join_form_prefill():
    """Giri yapm rencinin full_name ve student_number ile form n doldurma verisi."""
    if not current_user.is_authenticated:
        return None
    full = getattr(current_user, 'full_name', None) or ''
    num = getattr(current_user, 'student_number', None) or ''
    if not full.strip() or not num.strip():
        return None
    parts = full.strip().split(None, 1)
    ad = parts[0] if parts else ''
    soyad = parts[1] if len(parts) > 1 else ''
    return {'ad': ad, 'soyad': soyad, 'student_no': num, 'readonly': True}


@app.route('/list-join/<int:list_id>', methods=['GET'])
def show_join_form(list_id):
    logger.info("show_join_form: list_id=%s", list_id)
    target_list = ListVera.query.get_or_404(list_id)
    target_list.check_and_mark_expired()
    if not target_list.is_accepting_entries():
        if target_list.is_completed:
            flash('Bu liste tamamland olarak iaretlendi. Yeni kayt eklenemez.', 'warning')
        else:
            flash('Bu listenin kayt sresi doldu. Yeni kayt eklenemez.', 'warning')
        return redirect(url_for('index'))
    form_data = session.pop('join_form_data', None)
    join_prefill = _join_form_prefill() if not form_data else None
    return render_template('join_form.html', list_info=target_list, form_data=form_data, join_prefill=join_prefill)

def _validate_student_no(value):
    """renci numaras: sadece rakam, negatif deil."""
    if not value or not value.strip():
        return False, "renci numaras gerekli."
    val = value.strip()
    if not val.isdigit():
        return False, "renci numaras sadece rakamlardan olumaldr."
    if int(val) <= 0:
        return False, "renci numaras negatif veya sfr olamaz."
    return True, val


@app.route('/save-student/<int:list_id>', methods=['POST'])
def save_student(list_id):
    target_list = ListVera.query.get_or_404(list_id)
    target_list.check_and_mark_expired()
    if not target_list.is_accepting_entries():
        flash('Bu listeye artk kayt eklenemez (liste tamamland veya sre doldu).', 'danger')
        return redirect(url_for('index'))
    ad = request.form.get('ad', '').strip()
    soyad = request.form.get('soyad', '').strip()
    name_from_single = request.form.get('name', '').strip()
    if ad or soyad:
        name_surname = f"{ad} {soyad}".strip()
    else:
        name_surname = name_from_single
    if not name_surname:
        session['join_form_data'] = {
            'ad': ad, 'soyad': soyad, 'name': name_from_single,
            'student_no': request.form.get('student_no', ''),
            'project_title': request.form.get('project_title', ''),
            'summary': request.form.get('summary', '')
        }
        flash('Ad ve soyad gerekli.', 'warning')
        return redirect(url_for('show_join_form', list_id=list_id))

    student_no_raw = request.form.get('student_no', '').strip()
    ok, result = _validate_student_no(student_no_raw)
    if not ok:
        session['join_form_data'] = {
            'ad': ad, 'soyad': soyad, 'name': name_from_single,
            'student_no': request.form.get('student_no', ''),
            'project_title': request.form.get('project_title', ''),
            'summary': request.form.get('summary', '')
        }
        flash(result, 'danger')
        return redirect(url_for('show_join_form', list_id=list_id))
    student_no = result

    # Mkerrer renci numaras kontrol (ayn liste iinde)
    existing = StudentRecord.query.filter_by(list_id=list_id, student_no=student_no).first()
    if existing:
        session['join_form_data'] = {
            'ad': ad, 'soyad': soyad, 'name': name_from_single,
            'student_no': request.form.get('student_no', ''),
            'project_title': request.form.get('project_title', ''),
            'summary': request.form.get('summary', '')
        }
        if getattr(existing, 'is_deleted', False):
            flash('Bu öğrenci silinenler listesinde mevcut, lütfen oradan geri yükleyin.', 'danger')
        else:
            flash('Bu öğrenci numarası zaten kayıtlı. Lütfen farklı bir numara girin.', 'danger')
        return redirect(url_for('show_join_form', list_id=list_id))

    user_id = current_user.id if current_user.is_authenticated else None
    try:
        new_student = StudentRecord(
            list_id=list_id,
            user_id=user_id,
            name_surname=name_surname,
            student_no=student_no,
            project_title=request.form.get('project_title'),
            summary=request.form.get('summary')
        )
        db.session.add(new_student)
        db.session.commit()
        flash('Kaydnz baaryla tamamland!', 'success')
        if current_user.is_authenticated:
            return redirect(url_for('my_records'))
        return redirect(url_for('index'))
    except IntegrityError:
        db.session.rollback()
        session['join_form_data'] = {
            'ad': ad, 'soyad': soyad, 'name': name_from_single,
            'student_no': request.form.get('student_no', ''),
            'project_title': request.form.get('project_title', ''),
            'summary': request.form.get('summary', '')
        }
        flash('Kayt srasnda hata olutu. renci numaras zaten kullanlyor olabilir.', 'danger')
        return redirect(url_for('show_join_form', list_id=list_id))

@app.route('/list-detail/<int:list_id>')
@login_required
@teacher_required
def list_detail(list_id):
    logger.info("list_detail: Accessing details for list_id=%s", list_id)
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        flash("Bu listeye erişim yetkiniz yok.", "danger")
        return redirect(url_for('dashboard'))
    if getattr(target_list, 'is_deleted', False):
        abort(404)
    target_list.check_and_mark_expired()
    active_students = [s for s in target_list.students if not getattr(s, 'is_deleted', False)]
    deleted_students = [s for s in target_list.students if getattr(s, 'is_deleted', False)]
    students_submitted = set()
    for a in target_list.assignments:
        for sub in a.submissions:
            if sub.user_id and sub.file_path:
                students_submitted.add(sub.user_id)
    submitted_count = sum(1 for s in active_students if s.user_id and s.user_id in students_submitted)
    list_total_students = len(active_students)
    list_submissions = sum(1 for a in target_list.assignments for sub in a.submissions if sub.file_path)
    list_pending_approvals = sum(1 for s in active_students if s.status == 'pending')
    list_status_approved = sum(1 for s in active_students if s.status == 'approved')
    list_status_pending = sum(1 for s in active_students if s.status == 'pending')
    list_status_rejected = sum(1 for s in active_students if s.status == 'rejected')
    list_status_not_submitted = 0
    for s in active_students:
        has_sub = False
        for a in target_list.assignments:
            for sub in a.submissions:
                if sub.user_id == s.user_id and sub.file_path:
                    has_sub = True
                    break
            if has_sub:
                break
        if not has_sub:
            list_status_not_submitted += 1
    filter_pending = request.args.get('filter') == 'pending'
    students_display = [s for s in active_students if s.status == 'pending'] if filter_pending else list(active_students)
    return render_template(
        'list_detail.html',
        target_list=target_list,
        students_display=students_display,
        deleted_students=deleted_students,
        filter_pending=filter_pending,
        statuses=SUBMISSION_STATUSES,
        approval_statuses=APPROVAL_STATUSES,
        submitted_count=submitted_count,
        list_total_students=list_total_students,
        list_completed_submissions=list_submissions,
        list_pending_approvals=list_pending_approvals,
        list_status_approved=list_status_approved,
        list_status_pending=list_status_pending,
        list_status_rejected=list_status_rejected,
        list_status_not_submitted=list_status_not_submitted,
    )


@app.route('/list-detail/<int:list_id>/assignment/add', methods=['GET', 'POST'])
@login_required
@teacher_required
def add_assignment(list_id):
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        flash("Bu listeye erişim yetkiniz yok.", "danger")
        return redirect(url_for('dashboard'))
    # Tekil dev kstlamas: Listede zaten dev varsa eklemeye izin verme
    if target_list.assignments and len(target_list.assignments) >= 1:
        flash("Listede zaten bir dev tanml. Yeni dev ekleyemezsiniz; mevcut devi dzenleyebilir veya silebilirsiniz.", "warning")
        return redirect(url_for('list_detail', list_id=list_id))
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash("dev bal gerekli.", "warning")
            return redirect(url_for('list_detail', list_id=list_id))
        description = request.form.get('description', '').strip() or None
        due_date = None
        due_unit = request.form.get('due_unit', '').strip()
        due_amount = request.form.get('due_amount', '').strip()
        if due_unit and due_amount and due_amount.isdigit():
            due_date = _compute_due_from_engine(due_unit, int(due_amount))
        try:
            a = Assignment(list_id=list_id, title=title, description=description, due_date=due_date)
            db.session.add(a)
            db.session.commit()
            flash("dev eklendi.", "success")
        except IntegrityError:
            db.session.rollback()
            flash("dev eklenirken veritaban hatas olutu.", "danger")
        return redirect(url_for('list_detail', list_id=list_id))
    return render_template('add_assignment.html', target_list=target_list)


@app.route('/list-detail/<int:list_id>/assignment/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
@teacher_required
def view_assignment(list_id, assignment_id):
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        flash("Bu listeye erişim yetkiniz yok.", "danger")
        return redirect(url_for('dashboard'))
    assignment = Assignment.query.filter_by(id=assignment_id, list_id=list_id).first_or_404()
    if request.method == 'POST':
        sub_id_raw = request.form.get('submission_id')
        sub_id = None
        if sub_id_raw is not None:
            try:
                sub_id = int(sub_id_raw) if sub_id_raw else None
            except (ValueError, TypeError):
                pass
        grade = request.form.get('grade', '').strip() or None
        if sub_id:
            sub = Submission.query.filter_by(id=sub_id, assignment_id=assignment_id).first()
            if sub:
                try:
                    sub.grade = grade
                    db.session.commit()
                    flash("Not gncellendi.", "success")
                except IntegrityError:
                    db.session.rollback()
                    flash("Not kaydedilirken hata olutu.", "danger")
        return redirect(url_for('view_assignment', list_id=list_id, assignment_id=assignment_id))
    return render_template('view_assignment.html', target_list=target_list, assignment=assignment)


@app.route('/list-detail/<int:list_id>/save-grade', methods=['POST'])
@login_required
@teacher_required
def save_submission_grade(list_id):
    """Liste detay modalndan not kaydet; list_detail'e geri dn."""
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        return "Yetkisiz.", 403
    sub_id_raw = request.form.get('submission_id')
    sub_id = None
    if sub_id_raw is not None:
        try:
            sub_id = int(sub_id_raw) if sub_id_raw else None
        except (ValueError, TypeError):
            pass
    grade_raw = request.form.get('grade')
    grade = (grade_raw.strip() if grade_raw is not None and isinstance(grade_raw, str) else '') or None
    if sub_id:
        sub = Submission.query.filter_by(id=sub_id).first()
        if sub and sub.assignment and sub.assignment.list_id == list_id:
            try:
                sub.grade = grade
                db.session.add(sub)
                db.session.commit()
                db.session.refresh(sub)
                flash("Not gncellendi.", "success")
            except Exception as e:
                db.session.rollback()
                logger.exception("save_submission_grade hatas: sub_id=%s: %s", sub_id, str(e))
                flash("Not kaydedilirken hata olutu.", "danger")
    return redirect(url_for('list_detail', list_id=list_id))


@app.route('/withdraw-submission/<int:list_id>/<int:assignment_id>', methods=['POST'])
@login_required
def withdraw_submission(list_id, assignment_id):
    """renci: Not verilmemise devi geri ek (sil)."""
    target_list = ListVera.query.get_or_404(list_id)
    assignment = Assignment.query.filter_by(id=assignment_id, list_id=list_id).first_or_404()
    record = StudentRecord.query.filter_by(list_id=list_id, user_id=current_user.id).first()
    if not record or record.status != 'approved':
        flash("Yetkisiz.", "danger")
        return redirect(url_for('my_records'))
    sub = Submission.query.filter_by(assignment_id=assignment_id, user_id=current_user.id).first()
    if not sub or not sub.file_path:
        flash("Gerekletirilecek teslim bulunamad.", "warning")
        return redirect(url_for('my_records'))
    if sub.grade:
        flash("Not verildii iin dev geri ekilemez.", "warning")
        return redirect(url_for('my_records'))
    full_path = os.path.join(app.config['UPLOAD_FOLDER'], sub.file_path)
    if os.path.isfile(full_path):
        try:
            os.remove(full_path)
        except OSError:
            pass
    try:
        db.session.delete(sub)
        db.session.commit()
        flash("deviniz geri ekildi. Yeniden ykleyebilirsiniz.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Geri ekme srasnda hata olutu.", "danger")
    return redirect(url_for('my_records'))


@app.route('/request-revision/<int:list_id>/<int:assignment_id>/<int:submission_id>', methods=['POST'])
@login_required
@teacher_required
def request_revision(list_id, assignment_id, submission_id):
    """Hoca: Geri bildirim gnder, not verme; renci revizyonda."""
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        return "Yetkisiz.", 403
    sub = Submission.query.filter_by(id=submission_id, assignment_id=assignment_id).first_or_404()
    feedback_val = request.form.get('teacher_feedback')
    feedback_val = (feedback_val.strip() if feedback_val and isinstance(feedback_val, str) else '') or None
    record = StudentRecord.query.filter_by(list_id=list_id, user_id=sub.user_id).first()
    try:
        sub.revision_requested = True
        if record:
            record.teacher_feedback = feedback_val
        db.session.commit()
        flash("Revizyon talebi gnderildi. renci dosyay yeniden ykleyebilir.", "success")
    except Exception as e:
        db.session.rollback()
        logger.exception("request_revision hatas: %s", str(e))
        flash("Revizyon talebi kaydedilirken hata olutu.", "danger")
    return redirect(url_for('list_detail', list_id=list_id))


@app.route('/list-detail/<int:list_id>/assignment/<int:assignment_id>/download/<int:submission_id>')
@login_required
@teacher_required
def download_submission(list_id, assignment_id, submission_id):
    """retmen: dosya indirme (as_attachment=True)."""
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        return "Yetkisiz!", 403
    sub = Submission.query.filter_by(id=submission_id, assignment_id=assignment_id).first_or_404()
    safe_path = _safe_submission_path(sub.file_path)
    if not safe_path:
        flash("Dosya bulunamad.", "danger")
        return redirect(url_for('view_assignment', list_id=list_id, assignment_id=assignment_id))
    name = sub.user.full_name or f"user_{sub.user_id}" if sub.user else f"user_{sub.user_id}"
    orig = getattr(sub, 'original_filename', None) or os.path.basename(sub.file_path)
    safe_name = secure_filename(name)[:50] + "_" + secure_filename(orig)[:100]
    return send_from_directory(app.config['UPLOAD_FOLDER'], safe_path, as_attachment=True, download_name=safe_name)


@app.route('/list-detail/<int:list_id>/assignment/<int:assignment_id>/view/<int:submission_id>')
@login_required
@teacher_required
def view_file(list_id, assignment_id, submission_id):
    """retmen: dosyay taraycda a (as_attachment=False). PDF/resim/html/txt taraycda nizlenir."""
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        return "Yetkisiz.", 403
    sub = Submission.query.filter_by(id=submission_id, assignment_id=assignment_id).first_or_404()
    safe_path = _safe_submission_path(sub.file_path)
    if not safe_path:
        flash("Dosya bulunamad.", "danger")
        return redirect(url_for('list_detail', list_id=list_id))
    ext = (sub.file_path or '').lower().split('.')[-1] if '.' in (sub.file_path or '') else ''
    inline_types = {'pdf': 'application/pdf', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'bmp': 'image/bmp', 'svg': 'image/svg+xml', 'txt': 'text/plain', 'html': 'text/html', 'htm': 'text/html', 'csv': 'text/csv'}
    mimetype = inline_types.get(ext)
    if mimetype:
        return send_from_directory(app.config['UPLOAD_FOLDER'], safe_path, mimetype=mimetype, as_attachment=False)
    return send_from_directory(app.config['UPLOAD_FOLDER'], safe_path, as_attachment=True)


@app.route('/list-detail/<int:list_id>/assignment/<int:assignment_id>/preview/<int:submission_id>')
@login_required
@teacher_required
def preview_submission(list_id, assignment_id, submission_id):
    """Hoca: PDF nizleme (view_file ile ayn, geriye uyumluluk iin)."""
    return view_file(list_id, assignment_id, submission_id)


@app.route('/list-join/<int:list_id>/assignment/<int:assignment_id>/view')
@login_required
def view_my_submission(list_id, assignment_id):
    """renci: kendi dosyasn taraycda a."""
    target_list = ListVera.query.get_or_404(list_id)
    assignment = Assignment.query.filter_by(id=assignment_id, list_id=list_id).first_or_404()
    record = StudentRecord.query.filter_by(list_id=list_id, user_id=current_user.id).first()
    if not record:
        flash("Bu dosyaya eriim yetkiniz yok.", "danger")
        return redirect(url_for('my_records'))
    sub = Submission.query.filter_by(assignment_id=assignment_id, user_id=current_user.id).first_or_404()
    safe_path = _safe_submission_path(sub.file_path)
    if not safe_path:
        flash("Dosya bulunamad.", "danger")
        return redirect(url_for('my_records'))
    ext = (sub.file_path or '').lower().split('.')[-1] if '.' in (sub.file_path or '') else ''
    inline_types = {'pdf': 'application/pdf', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'bmp': 'image/bmp', 'svg': 'image/svg+xml', 'txt': 'text/plain', 'html': 'text/html', 'htm': 'text/html', 'csv': 'text/csv'}
    mimetype = inline_types.get(ext)
    if mimetype:
        return send_from_directory(app.config['UPLOAD_FOLDER'], safe_path, mimetype=mimetype, as_attachment=False)
    return send_from_directory(app.config['UPLOAD_FOLDER'], safe_path, as_attachment=True)


@app.route('/list-join/<int:list_id>/assignment/<int:assignment_id>/download')
@login_required
def download_my_submission(list_id, assignment_id):
    """renci: kendi dosyasn indir."""
    target_list = ListVera.query.get_or_404(list_id)
    assignment = Assignment.query.filter_by(id=assignment_id, list_id=list_id).first_or_404()
    record = StudentRecord.query.filter_by(list_id=list_id, user_id=current_user.id).first()
    if not record or record.status != 'approved':
        flash("Bu dosyaya eriim yetkiniz yok.", "danger")
        return redirect(url_for('my_records'))
    sub = Submission.query.filter_by(assignment_id=assignment_id, user_id=current_user.id).first_or_404()
    safe_path = _safe_submission_path(sub.file_path)
    if not safe_path:
        flash("Dosya bulunamad.", "danger")
        return redirect(url_for('my_records'))
    orig = getattr(sub, 'original_filename', None) or os.path.basename(sub.file_path)
    safe_name = secure_filename(current_user.full_name or f"user_{current_user.id}")[:50] + "_" + secure_filename(orig)[:100]
    return send_from_directory(app.config['UPLOAD_FOLDER'], safe_path, as_attachment=True, download_name=safe_name)


@app.route('/list-detail/<int:list_id>/assignment/<int:assignment_id>/delete', methods=['POST'])
@login_required
@teacher_required
def delete_assignment(list_id, assignment_id):
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        return "Yetkisiz!", 403
    assignment = Assignment.query.filter_by(id=assignment_id, list_id=list_id).first_or_404()
    for sub in assignment.submissions:
        if sub.file_path:
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], sub.file_path)
            if os.path.isfile(full_path):
                try:
                    os.remove(full_path)
                except OSError:
                    pass
    try:
        Submission.query.filter_by(assignment_id=assignment_id).delete()
        db.session.delete(assignment)
        db.session.commit()
        flash("dev silindi.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("dev silinirken hata olutu.", "danger")
    return redirect(url_for('list_detail', list_id=list_id))


@app.route('/list-join/<int:list_id>/assignments')
@login_required
def list_assignments_student(list_id):
    """renci: liste kodu ile girince devleri grr."""
    logger.info("list_assignments_student: list_id=%s", list_id)
    target_list = ListVera.query.get_or_404(list_id)
    target_list.check_and_mark_expired()
    return render_template('student_assignments.html', list_info=target_list)


@app.route('/list-join/<int:list_id>/assignment/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def submit_homework(list_id, assignment_id):
    """renci: dev dosyas ykleme (sadece bu listeye kaytl ve giri yapm renci)."""
    logger.info("submit_homework: list_id=%s assignment_id=%s", list_id, assignment_id)
    target_list = ListVera.query.get_or_404(list_id)
    target_list.check_and_mark_expired()
    if not target_list.is_accepting_entries():
        flash("Bu listenin teslim sresi doldu veya liste tamamland. Teslim yaplamaz.", "warning")
        return redirect(url_for('my_records'))
    assignment = Assignment.query.filter_by(id=assignment_id, list_id=list_id).first_or_404()
    if not assignment.is_submission_open():
        flash("Bu devin teslim sresi doldu.", "warning")
        return redirect(url_for('my_records'))
    record = StudentRecord.query.filter_by(list_id=list_id, user_id=current_user.id).first()
    if not record:
        return _upload_response(request, False, "Bu listeye kayıtlı değilsiniz. Önce listeye kayıt olun.")
    if record.status != 'approved':
        return _upload_response(request, False, "Dosya yükleyebilmek için projenizin onaylanmış olması gerekir. Liste detayında onay bekleyen öğrenciler yükleme yapamaz.")
    xhr = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if request.method == 'POST':
        if 'file' not in request.files:
            return _upload_response(request, False, "Dosya seçin.")
        file = request.files['file']
        if not file or file.filename == '':
            return _upload_response(request, False, "Dosya seçin.")
        if not allowed_file(file.filename):
            return _upload_response(request, False, "Geçersiz dosya. Sadece PDF, PNG, JPG, DOCX, ZIP kabul edilir.")
        mt = allowed_mimetype(file.content_type)
        if mt is not True:
            return _upload_response(request, False, "Dosya tipi güvenlik nedeniyle kabul edilmiyor.")
        magic_ok, magic_err = validate_file_content_magic(file)
        if not magic_ok:
            return _upload_response(request, False, magic_err or "Dosya içeriği güvenli değil.")
        _ensure_upload_dirs()
        assign_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"assignment_{assignment_id}")
        os.makedirs(assign_dir, exist_ok=True)
        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'bin'
        original_name = (file.filename or 'upload')[:200]
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        rel_path = os.path.join(f"assignment_{assignment_id}", unique_name)
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], rel_path)
        try:
            file.save(full_path)
        except (IOError, OSError) as e:
            logger.warning("submit_homework: dosya kaydetme hatasi: %s", str(e))
            return _upload_response(request, False, "Dosya kaydedilemedi. Lütfen tekrar deneyin.")
        existing = Submission.query.filter_by(assignment_id=assignment_id, user_id=current_user.id).first()
        try:
            if existing:
                if existing.file_path:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], existing.file_path)
                    if os.path.isfile(old_path):
                        try:
                            os.remove(old_path)
                        except OSError:
                            pass
                existing.file_path = rel_path
                existing.original_filename = original_name
                existing.submitted_at = datetime.utcnow()
                was_revision = getattr(existing, 'revision_requested', False)
                existing.revision_requested = False
                db.session.commit()
                msg = "Dosyanız yeniden yüklendi. İnceleme bekliyor." if was_revision else "Ödeviniz güncellendi."
            else:
                sub = Submission(assignment_id=assignment_id, user_id=current_user.id, file_path=rel_path, original_filename=original_name)
                db.session.add(sub)
                db.session.commit()
                msg = "Ödeviniz teslim edildi."
            return _upload_response(request, True, msg, redirect_url=url_for('my_records'))
        except Exception as e:
            db.session.rollback()
            logger.exception("submit_homework: veritabanı hatası: %s", str(e))
            try:
                if os.path.isfile(full_path):
                    os.remove(full_path)
            except OSError:
                pass
            return _upload_response(request, False, "Kayıt sırasında hata oluştu. Lütfen tekrar deneyin.")
    my_sub = Submission.query.filter_by(assignment_id=assignment_id, user_id=current_user.id).first()
    return render_template('submit_homework.html', list_info=target_list, assignment=assignment, my_submission=my_sub)


@app.route('/delete-student/<int:student_id>')
@login_required
@teacher_required
def delete_student(student_id):
    student = StudentRecord.query.get_or_404(student_id)
    list_id = student.list_id
    if student.parent_list.owner_id != current_user.id:
        flash("Bu ilemi yapma yetkiniz yok!", "danger")
        return redirect(url_for('dashboard'))
    try:
        db.session.delete(student)
        db.session.commit()
        flash("renci kayd silindi.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("renci silinirken hata olutu.", "danger")
    return redirect(url_for('list_detail', list_id=list_id))


@app.route('/approve-student/<int:record_id>', methods=['POST'])
@login_required
@teacher_required
def approve_student(record_id):
    record = StudentRecord.query.get_or_404(record_id)
    if record.parent_list.owner_id != current_user.id:
        flash("Yetkisiz.", "danger")
        return redirect(url_for('dashboard'))
    feedback_val = request.form.get('teacher_feedback')
    feedback_val = (feedback_val.strip() if feedback_val and isinstance(feedback_val, str) else '') or None
    grade_val = request.form.get('grade')
    grade_val = (grade_val.strip() if grade_val and isinstance(grade_val, str) else '') or None
    sub_id_raw = request.form.get('submission_id')
    sub_id = int(sub_id_raw) if sub_id_raw and str(sub_id_raw).isdigit() else None
    old_status = record.status
    record.status = 'approved'
    if feedback_val is not None:
        record.teacher_feedback = feedback_val
    if sub_id and grade_val is not None:
        sub = Submission.query.filter_by(id=sub_id).first()
        if sub and sub.assignment and sub.assignment.list_id == record.list_id and sub.user_id == record.user_id:
            sub.grade = grade_val
    try:
        db.session.commit()
        logger.info("approve_student: record_id=%s, old_status=%s, new_status=approved", record_id, old_status)
        flash("Proje onayland." + (" Not kaydedildi." if grade_val else ""), "success")
    except IntegrityError:
        db.session.rollback()
        flash("Onay kaydedilirken hata olutu.", "danger")
    return redirect(url_for('list_detail', list_id=record.list_id))


@app.route('/reject-student/<int:record_id>', methods=['POST'])
@login_required
@teacher_required
def reject_student(record_id):
    record = StudentRecord.query.get_or_404(record_id)
    if record.parent_list.owner_id != current_user.id:
        flash("Yetkisiz.", "danger")
        return redirect(url_for('dashboard'))
    feedback_val = request.form.get('teacher_feedback')
    feedback_val = (feedback_val.strip() if feedback_val and isinstance(feedback_val, str) else '') or None
    if not feedback_val or len(feedback_val.strip()) == 0:
        flash("Reddetmek iin geri bildirim zorunludur.", "danger")
        return redirect(url_for('list_detail', list_id=record.list_id))
    old_status = record.status
    record.status = 'rejected'
    record.teacher_feedback = feedback_val
    try:
        db.session.commit()
        logger.info("reject_student: record_id=%s, old_status=%s, new_status=rejected", record_id, old_status)
        flash("Proje reddedildi. renci gncelleyip tekrar onaya sunabilir.", "info")
    except IntegrityError:
        db.session.rollback()
        flash("Red kaydedilirken hata olutu.", "danger")
    return redirect(url_for('list_detail', list_id=record.list_id))


@app.route('/dashboard/approve-all-pending', methods=['POST'])
@login_required
@teacher_required
def approve_all_pending_all_lists():
    """Tum listelerdeki tum bekleyen ogrencileri tek tikla onayla."""
    user_lists = ListVera.query.filter_by(owner_id=current_user.id, is_deleted=False).all()
    total_approved = 0
    for lst in user_lists:
        for s in lst.students:
            if getattr(s, 'is_deleted', False):
                continue
            if s.status == 'pending':
                s.status = 'approved'
                total_approved += 1
    try:
        db.session.commit()
        flash("%d öğrenci tüm listelerde onaylandı." % total_approved, "success")
    except IntegrityError:
        db.session.rollback()
        flash("Toplu onay kaydedilirken hata oluştu.", "danger")
    return redirect(url_for('dashboard'))


@app.route('/bulk-approve-submissions/<int:list_id>', methods=['POST'])
@login_required
@teacher_required
def bulk_approve_submissions(list_id):
    """Approve all pending student records (Beklemede) for this list in one go."""
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        flash("Yetkisiz.", "danger")
        return redirect(url_for('dashboard'))
    records = StudentRecord.query.filter_by(list_id=list_id, status='pending', is_deleted=False).all()
    for r in records:
        r.status = 'approved'
    try:
        db.session.commit()
        flash("Tm devler baaryla onayland.", "success")
        logger.info("bulk_approve_submissions: list_id=%s, count=%s", list_id, len(records))
    except IntegrityError:
        db.session.rollback()
        flash("Toplu onay kaydedilirken hata olutu.", "danger")
    return redirect(url_for('list_detail', list_id=list_id))


@app.route('/list-detail/<int:list_id>/bulk-delete', methods=['POST'])
@login_required
@teacher_required
def bulk_delete_students(list_id):
    """Secilen ogrenci kayitlarini siler. JSON doner (istatistik guncellemesi icin)."""
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        return {"ok": False, "error": "Yetkisiz"}, 403
    ids_raw = request.form.getlist('record_ids[]') or request.get_json(silent=True) or {}
    if isinstance(ids_raw, dict):
        ids_raw = ids_raw.get('record_ids', [])
    ids = []
    for x in ids_raw:
        try:
            ids.append(int(x))
        except (ValueError, TypeError):
            pass
    if not ids:
        return jsonify({"ok": False, "error": "İşlem sırasında bir hata oluştu, lütfen internetinizi kontrol edin."})
    records = StudentRecord.query.filter(
        StudentRecord.id.in_(ids),
        StudentRecord.list_id == list_id,
    ).all()
    deleted = 0
    for rec in records:
        rec.is_deleted = True
        deleted += 1
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"ok": False, "error": "İşlem sırasında bir hata oluştu, lütfen internetinizi kontrol edin."})
    students_remaining = StudentRecord.query.filter_by(list_id=list_id, is_deleted=False).all()
    list_total_students = len(students_remaining)
    list_pending_approvals = sum(1 for s in students_remaining if s.status == 'pending')
    return jsonify({"ok": True, "deleted": deleted, "list_total_students": list_total_students, "list_pending_approvals": list_pending_approvals})


@app.route('/list-detail/<int:list_id>/restore-student/<int:record_id>', methods=['POST'])
@login_required
@teacher_required
def restore_student(list_id, record_id):
    """Silinen ogrenciyi geri yukle (is_deleted=False)."""
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        return jsonify({"ok": False, "error": "Bu listeye erişim yetkiniz yok."}), 403
    record = StudentRecord.query.filter_by(id=record_id, list_id=list_id).first_or_404()
    if not getattr(record, 'is_deleted', False):
        return jsonify({"ok": False, "error": "Kayıt zaten aktif"})
    record.is_deleted = False
    try:
        db.session.commit()
        return jsonify({
            "ok": True,
            "record": {
                "id": record.id,
                "display_name": record.display_name or "",
                "display_student_no": record.display_student_no or "",
                "status": record.status or "pending",
                "project_title": record.project_title or ""
            }
        })
    except IntegrityError:
        db.session.rollback()
        return jsonify({"ok": False, "error": "Geri yükleme hatası"})


@app.route('/list-detail/<int:list_id>/permanent-delete-student/<int:record_id>', methods=['POST'])
@login_required
@teacher_required
def permanent_delete_student(list_id, record_id):
    """Silinen ogrenciyi veritabanindan kalici olarak sil (hard delete)."""
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        return jsonify({"ok": False, "error": "Bu listeye erişim yetkiniz yok."}), 403
    record = StudentRecord.query.filter_by(id=record_id, list_id=list_id).first_or_404()
    if not getattr(record, 'is_deleted', False):
        return jsonify({"ok": False, "error": "Kayıt aktif, önce çöpe taşıyın"})
    try:
        db.session.delete(record)
        db.session.commit()
        return jsonify({"ok": True})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"ok": False, "error": "Silme hatası"})


@app.route('/list-detail/<int:list_id>/bulk-approve-selected', methods=['POST'])
@login_required
@teacher_required
def bulk_approve_selected(list_id):
    """Secilen ogrencilerden sadece durumu 'Beklemede' olanlari onaylar. JSON doner."""
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        return jsonify({"ok": False, "error": "Bu listeye erişim yetkiniz yok."}), 403
    ids_raw = request.form.getlist('record_ids[]') or (request.get_json(silent=True) or {}).get('record_ids', [])
    ids = []
    for x in ids_raw:
        try:
            ids.append(int(x))
        except (ValueError, TypeError):
            pass
    if not ids:
        return jsonify({"ok": False, "error": "İşlem sırasında bir hata oluştu, lütfen internetinizi kontrol edin."})
    records = StudentRecord.query.filter(
        StudentRecord.id.in_(ids),
        StudentRecord.list_id == list_id,
        StudentRecord.status == 'pending',
    ).all()
    approved = 0
    for r in records:
        r.status = 'approved'
        approved += 1
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"ok": False, "error": "İşlem sırasında bir hata oluştu, lütfen internetinizi kontrol edin."})
    students = StudentRecord.query.filter_by(list_id=list_id, is_deleted=False).all()
    list_total_students = len(students)
    list_pending_approvals = sum(1 for s in students if s.status == 'pending')
    return jsonify({"ok": True, "approved": approved, "list_total_students": list_total_students, "list_pending_approvals": list_pending_approvals})


@app.route('/save-announcement/<int:list_id>', methods=['POST'])
@login_required
@teacher_required
def save_announcement(list_id):
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        return "Yetkisiz.", 403
    target_list.announcement = request.form.get('announcement', '').strip() or None
    target_list.announcement_updated_at = datetime.utcnow() if target_list.announcement else None
    try:
        db.session.commit()
        flash("Duyuru kaydedildi.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Duyuru kaydedilirken hata olutu.", "danger")
    return redirect(url_for('list_detail', list_id=list_id))


@app.route('/save-evaluation/<int:list_id>', methods=['POST'])
@login_required
@teacher_required
def save_evaluation(list_id):
    """Tek ilemde not + geri bildirim kaydet."""
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        return "Yetkisiz.", 403
    record_id = request.form.get('record_id', type=int)
    sub_id_raw = request.form.get('submission_id')
    sub_id = int(sub_id_raw) if sub_id_raw and str(sub_id_raw).isdigit() else None
    grade_raw = request.form.get('grade')
    grade = (grade_raw.strip() if grade_raw and isinstance(grade_raw, str) else '') or None
    feedback_val = request.form.get('teacher_feedback')
    feedback_val = (feedback_val.strip() if feedback_val and isinstance(feedback_val, str) else '') or None
    record = StudentRecord.query.filter_by(id=record_id, list_id=list_id).first_or_404()
    try:
        record.teacher_feedback = feedback_val
        if sub_id:
            sub = Submission.query.filter_by(id=sub_id).first()
            if sub and sub.assignment and sub.assignment.list_id == list_id and sub.user_id == record.user_id:
                sub.grade = grade
        db.session.commit()
        flash("Deerlendirme kaydedildi.", "success")
    except Exception as e:
        db.session.rollback()
        logger.exception("save_evaluation hatas: %s", str(e))
        flash("Deerlendirme kaydedilirken hata olutu.", "danger")
    return redirect(url_for('list_detail', list_id=list_id))


@app.route('/save-feedback/<int:record_id>', methods=['POST'])
@login_required
@teacher_required
def save_student_feedback(record_id):
    record = StudentRecord.query.get_or_404(record_id)
    if record.parent_list.owner_id != current_user.id:
        return "Yetkisiz.", 403
    feedback_val = request.form.get('teacher_feedback')
    feedback_val = (feedback_val.strip() if feedback_val is not None and isinstance(feedback_val, str) else '') or None
    record.teacher_feedback = feedback_val
    list_id = record.list_id
    try:
        db.session.add(record)
        db.session.commit()
        db.session.refresh(record)
        flash("Geri bildirim kaydedildi.", "success")
    except Exception as e:
        db.session.rollback()
        logger.exception("save_student_feedback hatas: record_id=%s: %s", record_id, str(e))
        flash("Geri bildirim kaydedilirken hata olutu.", "danger")
    return redirect(url_for('list_detail', list_id=list_id))


@app.route('/edit-student/<int:student_id>', methods=['POST'])
@login_required
@teacher_required
def edit_student(student_id):
    student = StudentRecord.query.get_or_404(student_id)
    if student.parent_list.owner_id != current_user.id:
        return "Yetkisiz ilem!", 403
    student.project_title = request.form.get('project_title')
    student.summary = request.form.get('summary')
    student.teacher_feedback = request.form.get('teacher_feedback', '').strip() or None
    if not student.user_id:
        new_student_no_raw = request.form.get('student_no', '').strip()
        ok, result = _validate_student_no(new_student_no_raw)
        if not ok:
            flash(result, 'danger')
            return redirect(url_for('list_detail', list_id=student.list_id))
        new_student_no = result
        duplicate = StudentRecord.query.filter(
            StudentRecord.list_id == student.list_id,
            StudentRecord.student_no == new_student_no,
            StudentRecord.id != student_id
        ).first()
        if duplicate:
            flash("Bu renci numaras zaten listede kaytl.", "danger")
            return redirect(url_for('list_detail', list_id=student.list_id))
        student.name_surname = request.form.get('name')
        student.student_no = new_student_no
    try:
        db.session.commit()
        flash("Kayt gncellendi.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Kayt gncellenirken hata olutu.", "danger")
    return redirect(url_for('list_detail', list_id=student.list_id))


@app.route('/student-status/<int:student_id>', methods=['POST'])
@login_required
@teacher_required
def student_status(student_id):
    """dev teslim durumunu hzl gncelle."""
    student = StudentRecord.query.get_or_404(student_id)
    if student.parent_list.owner_id != current_user.id:
        flash("Bu ilemi yapma yetkiniz yok!", "danger")
        return redirect(url_for('dashboard'))
    status = request.form.get('status', 'pending')
    if status in ('pending', 'submitted', 'checked'):
        student.submission_status = status
        try:
            db.session.commit()
            flash("Teslim durumu gncellendi.", "success")
        except IntegrityError:
            db.session.rollback()
            flash("Teslim durumu gncellenirken hata olutu.", "danger")
    return redirect(url_for('list_detail', list_id=student.list_id))

@app.route('/complete-list/<int:list_id>', methods=['POST'])
@login_required
@teacher_required
def complete_list(list_id):
    target_list = ListVera.query.get_or_404(list_id)
    if getattr(target_list, 'is_deleted', False):
        abort(404)
    if target_list.owner_id != current_user.id:
        flash("Bu ilemi yapma yetkiniz yok!", "danger")
        return redirect(url_for('dashboard'))
    target_list.is_completed = True
    try:
        db.session.commit()
        flash("Liste tamamland olarak iaretlendi. Artk yeni kayt eklenemez.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Liste gncellenirken hata olutu.", "danger")
    return redirect(request.referrer or url_for('list_detail', list_id=list_id))


@app.route('/extend-list/<int:list_id>', methods=['POST'])
@login_required
@teacher_required
def extend_list(list_id):
    target_list = ListVera.query.get_or_404(list_id)
    if getattr(target_list, 'is_deleted', False):
        abort(404)
    if target_list.owner_id != current_user.id:
        flash("Bu ilemi yapma yetkiniz yok!", "danger")
        return redirect(url_for('dashboard'))
    duration_str = request.form.get('duration_value', '').strip()
    duration_unit = request.form.get('duration_unit', 'saat').strip()
    if not duration_str or not duration_str.isdigit():
        flash("Geerli bir sre girin (rn: 15 dakika veya 1 saat).", "warning")
        return redirect(request.referrer or url_for('list_detail', list_id=list_id))
    val = int(duration_str)
    if val <= 0:
        flash("Sre 0'dan byk olmaldr.", "warning")
        return redirect(request.referrer or url_for('list_detail', list_id=list_id))
    unit = duration_unit if duration_unit in ('dakika', 'saat', 'gun', 'hafta', 'ay') else 'saat'
    target_list.expires_at = _compute_due_from_engine(unit, val)
    target_list.is_completed = False
    try:
        db.session.commit()
        flash("Sre uzatld. Liste yeniden kayt kabul ediyor.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Sre uzatlrken hata olutu.", "danger")
    return redirect(url_for('list_detail', list_id=list_id))


@app.route('/uncomplete-list/<int:list_id>', methods=['POST'])
@login_required
@teacher_required
def uncomplete_list(list_id):
    target_list = ListVera.query.get_or_404(list_id)
    if getattr(target_list, 'is_deleted', False):
        abort(404)
    if target_list.owner_id != current_user.id:
        flash("Bu ilemi yapma yetkiniz yok!", "danger")
        return redirect(url_for('dashboard'))
    target_list.is_completed = False
    try:
        db.session.commit()
        flash("Tamamland iareti kaldrld. Liste yeniden kayt kabul ediyor.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Liste gncellenirken hata olutu.", "danger")
    return redirect(request.referrer or url_for('list_detail', list_id=list_id))


@app.route('/delete-list/<int:list_id>')
@login_required
@teacher_required
def delete_list(list_id):
    """Soft delete: is_deleted=True. Veri silinmez."""
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        flash("Yetkisiz ilem!", "danger")
        return redirect(url_for('dashboard'))
    if getattr(target_list, 'is_deleted', False):
        flash("Liste zaten cop kutusunda.", "info")
        return redirect(url_for('dashboard'))
    try:
        target_list.is_deleted = True
        db.session.commit()
        flash("Liste Cop Kutusuna tasindi. Geri yuklemek icin cop kutusunu kullanin.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Liste tasinirken hata olutu.", "danger")
    return redirect(url_for('dashboard'))


@app.route('/list-trash')
@login_required
@teacher_required
def list_trash():
    """Cop kutusu: is_deleted=True listeler."""
    deleted_lists = ListVera.query.filter_by(owner_id=current_user.id, is_deleted=True).order_by(ListVera.created_at.desc()).all()
    return render_template('trash.html', deleted_lists=deleted_lists)


@app.route('/restore-list/<int:list_id>', methods=['POST'])
@login_required
@teacher_required
def restore_list(list_id):
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        flash("Yetkisiz.", "danger")
        return redirect(url_for('dashboard'))
    if not getattr(target_list, 'is_deleted', False):
        flash("Liste zaten aktif.", "info")
        return redirect(url_for('dashboard'))
    try:
        target_list.is_deleted = False
        db.session.commit()
        flash("Liste geri yuklendi.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Geri yukleme hatasi.", "danger")
    return redirect(url_for('list_trash'))


@app.route('/permanent-delete-list/<int:list_id>', methods=['POST'])
@login_required
@teacher_required
def permanent_delete_list(list_id):
    """Kalici silme: db.session.delete. Oncesinde cok kesin onay gerekir (frontend)."""
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        flash("Yetkisiz.", "danger")
        return redirect(url_for('dashboard'))
    if not getattr(target_list, 'is_deleted', False):
        flash("Once listeyi cop kutusuna tasiyin.", "warning")
        return redirect(url_for('dashboard'))
    try:
        StudentRecord.query.filter_by(list_id=list_id).delete()
        db.session.delete(target_list)
        db.session.commit()
        flash("Liste kalici olarak silindi.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Kalici silme hatasi.", "danger")
    return redirect(url_for('list_trash'))


@app.route('/purge-all-trash', methods=['POST'])
@login_required
@teacher_required
def purge_all_trash():
    """Tum cop kutusundaki listeleri kalici olarak sil."""
    deleted = ListVera.query.filter_by(owner_id=current_user.id, is_deleted=True).all()
    count = 0
    for lst in deleted:
        try:
            StudentRecord.query.filter_by(list_id=lst.id).delete()
            db.session.delete(lst)
            count += 1
        except Exception:
            pass
    try:
        db.session.commit()
        flash("Çöp kutusu boşaltıldı (%d liste kalıcı olarak silindi)." % count, "success")
    except IntegrityError:
        db.session.rollback()
        flash("İşlem sırasında bir hata oluştu.", "danger")
    return redirect(url_for('list_trash'))


@app.route('/dashboard/bulk-soft-delete', methods=['POST'])
@login_required
@teacher_required
def bulk_soft_delete_lists():
    ids_raw = request.form.getlist('list_ids[]') or (request.get_json(silent=True) or {}).get('list_ids', [])
    ids = [int(x) for x in ids_raw if str(x).isdigit()]
    updated = 0
    for list_id in ids:
        lst = ListVera.query.filter_by(id=list_id, owner_id=current_user.id, is_deleted=False).first()
        if lst:
            lst.is_deleted = True
            updated += 1
    try:
        db.session.commit()
        return jsonify({"ok": True, "updated": updated})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"ok": False, "error": "Hata olustu"})


@app.route('/dashboard/bulk-complete-lists', methods=['POST'])
@login_required
@teacher_required
def bulk_complete_lists():
    """Secilen listelerdeki tum pending ogrencileri onayla."""
    ids_raw = request.form.getlist('list_ids[]') or (request.get_json(silent=True) or {}).get('list_ids', [])
    ids = [int(x) for x in ids_raw if str(x).isdigit()]
    total_approved = 0
    for list_id in ids:
        lst = ListVera.query.filter_by(id=list_id, owner_id=current_user.id, is_deleted=False).first()
        if lst and lst.students:
            for s in lst.students:
                if getattr(s, 'is_deleted', False):
                    continue
                if s.status == 'pending':
                    s.status = 'approved'
                    total_approved += 1
    try:
        db.session.commit()
        return jsonify({"ok": True, "approved": total_approved})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"ok": False, "error": "Hata olustu"})


@app.route('/list-tumunu-tamamla/<int:list_id>', methods=['POST'])
@login_required
@teacher_required
def list_tumunu_tamamla(list_id):
    """Tek listedeki tum pending ogrencileri onayla."""
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        flash("Yetkisiz.", "danger")
        return redirect(url_for('dashboard'))
    if getattr(target_list, 'is_deleted', False):
        abort(404)
    approved = 0
    for s in target_list.students:
        if getattr(s, 'is_deleted', False):
            continue
        if s.status == 'pending':
            s.status = 'approved'
            approved += 1
    try:
        db.session.commit()
        flash("Tum bekleyen ogrenciler onaylandi (%d kayit)." % approved, "success")
    except IntegrityError:
        db.session.rollback()
        flash("Onay sirasinda hata olutu.", "danger")
    return redirect(request.referrer or url_for('list_detail', list_id=list_id))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Kullancnn full_name ve (renciyse) student_number gncellemesi."""
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip() or None
        student_number = request.form.get('student_number', '').strip() or None
        email_val = (request.form.get('email') or '').strip().lower() or None
        if not full_name:
            flash('Ad-Soyad gerekli.', 'warning')
            return redirect(url_for('profile'))
        if current_user.role == 'student' and student_number:
            ok, msg = _validate_student_no(student_number)
            if not ok:
                flash(msg, 'danger')
                return redirect(url_for('profile'))
            other = User.query.filter(
                User.student_number == student_number,
                User.id != current_user.id
            ).first()
            if other:
                flash('Bu renci numaras ile zaten bir kayt mevcut.', 'danger')
                return redirect(url_for('profile'))
        current_user.full_name = full_name
        old_email = current_user.email
        current_user.email = email_val
        if (old_email or '') != (email_val or ''):
            current_user.is_verified = False
        if current_user.role == 'student':
            current_user.student_number = student_number
        try:
            db.session.commit()
            flash('Profiliniz gncellendi.', 'success')
            if (old_email or '') != (email_val or '') and email_val:
                ok, err = send_verification_email(current_user)
                if ok:
                    flash("Dogrulama e-postasi gonderildi. Lutfen e-postanizi kontrol edin.", "success")
                else:
                    flash(f"Dogrulama e-postasi gonderilemedi: {err}", "warning")
        except IntegrityError:
            db.session.rollback()
            flash('Profil gncellenirken hata olutu.', 'danger')
        return redirect(url_for('profile'))
    is_verified = getattr(current_user, 'is_verified', False)
    return render_template('profile.html', is_verified=is_verified)


@app.route('/profile/change-password', methods=['POST'])
@login_required
def change_password():
    """Change password for logged-in user."""
    current_pw = request.form.get('current_password') or ''
    new_pw = request.form.get('new_password') or ''
    confirm_pw = request.form.get('new_password_confirm') or ''
    if not current_pw:
        flash('Mevcut ifre gerekli.', 'warning')
        return redirect(url_for('profile'))
    try:
        current_ok = check_password_hash(current_user.password, current_pw)
    except Exception:
        current_ok = False
    if not current_ok and current_user.password != current_pw:
        flash('Mevcut ifre hatal.', 'danger')
        return redirect(url_for('profile'))
    if not new_pw or len(new_pw) < 4:
        flash('Yeni ifre en az 4 karakter olmaldr.', 'warning')
        return redirect(url_for('profile'))
    if new_pw != confirm_pw:
        flash('Yeni ifreler elemiyor.', 'warning')
        return redirect(url_for('profile'))
    current_user.password = generate_password_hash(new_pw, method='pbkdf2:sha256')
    try:
        db.session.commit()
        flash('ifreniz baaryla gncellendi.', 'success')
    except Exception:
        db.session.rollback()
        flash('ifre gncellenirken hata olutu.', 'danger')
    return redirect(url_for('profile'))


@app.route('/my-records')
@login_required
def my_records():
    """renci: liste kaytlar + kaytl listelerdeki aktif devler. Eitmenler panele ynlendirilir."""
    if getattr(current_user, 'role', None) == 'teacher':
        flash('Bu sayfa renciler iindir. Ynlendirildiniz.', 'info')
        return redirect(url_for('dashboard'))
    records = StudentRecord.query.filter_by(user_id=current_user.id, is_deleted=False).order_by(StudentRecord.id.desc()).all()
    # user_id olmayan ama student_no eslesen kayitlar da goster (giris yapmadan kayit olma senaryosu)
    if current_user.student_number:
        orphan_records = StudentRecord.query.filter(
            StudentRecord.user_id.is_(None),
            StudentRecord.student_no == current_user.student_number,
            StudentRecord.is_deleted == False
        ).order_by(StudentRecord.id.desc()).all()
        seen_list_ids = {r.list_id for r in records}
        for rec in orphan_records:
            if rec.list_id not in seen_list_ids:
                rec.user_id = current_user.id
                records.append(rec)
                seen_list_ids.add(rec.list_id)
        if orphan_records:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
    logger.info("DEBUG my_records: user_id=%s student_number=%s records_count=%s list_ids=%s",
                current_user.id, getattr(current_user, 'student_number', None), len(records), [r.list_id for r in records])
    unique_lists = list({r.parent_list for r in records if r.parent_list})
    record_by_list = {r.list_id: r for r in records}
    submitted_assignments = set()
    revision_requested_for = set()
    withdrawable_for = set()
    grades_by_record = {}
    for lst in unique_lists:
        if lst:
            lst.check_and_mark_expired()
    for lst in unique_lists:
        if not lst or not lst.assignments:
            continue
        for a in lst.assignments:
            sub = Submission.query.filter_by(assignment_id=a.id, user_id=current_user.id).first()
            if sub and getattr(sub, 'file_path', None):
                submitted_assignments.add((lst.id, a.id))
                if getattr(sub, 'revision_requested', False):
                    revision_requested_for.add((lst.id, a.id))
                elif not getattr(sub, 'grade', None):
                    withdrawable_for.add((lst.id, a.id))
    for r in records:
        gl = []
        if not r.parent_list:
            grades_by_record[r.id] = []
            continue
        for a in (r.parent_list.assignments or []):
            sub = Submission.query.filter_by(assignment_id=a.id, user_id=r.user_id).first()
            if sub and getattr(sub, 'grade', None):
                gl.append((a.title, sub.grade))
        grades_by_record[r.id] = gl
    announcements_by_list = {lst.id: getattr(lst, 'announcement', None) for lst in unique_lists}
    now = datetime.utcnow()
    lists_with_new_announcement = set()
    for lst in unique_lists:
        if not lst:
            continue
        at = getattr(lst, 'announcement_updated_at', None)
        if at and announcements_by_list.get(lst.id) and (now - at).total_seconds() < 24 * 3600:
            lists_with_new_announcement.add(lst.id)
    records_sorted = sorted(records, key=lambda r: (0 if (r.parent_list and announcements_by_list.get(r.parent_list.id)) else 1, -r.id))
    # Öğrenci paneli istatistikleri: StudentRecord.status kullan (onaylanan / bekleyen liste sayısı)
    student_stat_registered_lists = len(unique_lists)
    student_stat_approved = sum(1 for r in records if getattr(r, 'status', None) == 'approved')
    student_stat_pending = sum(1 for r in records if getattr(r, 'status', None) in ('pending', 'rejected'))
    student_stat_success_rate = round((student_stat_approved / student_stat_registered_lists * 100) if student_stat_registered_lists else 0)
    is_verified = getattr(current_user, 'is_verified', False)
    return render_template('my_records.html', records=records_sorted, record_by_list=record_by_list, submitted_assignments=submitted_assignments, revision_requested_for=revision_requested_for or set(), withdrawable_for=withdrawable_for or set(), grades_by_record=grades_by_record, announcements_by_list=announcements_by_list, lists_with_new_announcement=lists_with_new_announcement, is_verified=is_verified, student_stat_registered_lists=student_stat_registered_lists, student_stat_approved=student_stat_approved, student_stat_pending=student_stat_pending, student_stat_success_rate=student_stat_success_rate)




@app.route('/my-records/<int:record_id>/edit', methods=['GET', 'POST'])
@login_required
def my_record_edit(record_id):
    """renci: sadece kendi kaydn gncelleyebilir."""
    record = StudentRecord.query.get_or_404(record_id)
    if record.user_id != current_user.id:
        flash('Bu kayd dzenleme yetkiniz yok.', 'danger')
        return redirect(url_for('my_records'))
    target_list = record.parent_list
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        student_no_raw = request.form.get('student_no', '').strip()
        project_title = request.form.get('project_title', '').strip()
        summary = request.form.get('summary', '').strip() or None
        if not name or not project_title:
            flash('Ad soyad ve proje bal gerekli.', 'warning')
            return redirect(url_for('my_record_edit', record_id=record_id))
        ok, result = _validate_student_no(student_no_raw)
        if not ok:
            flash(result, 'danger')
            return redirect(url_for('my_record_edit', record_id=record_id))
        new_student_no = result
        duplicate = StudentRecord.query.filter(
            StudentRecord.list_id == record.list_id,
            StudentRecord.student_no == new_student_no,
            StudentRecord.id != record_id
        ).first()
        if duplicate:
            flash('Bu renci numaras bu listede zaten kaytl.', 'danger')
            return redirect(url_for('my_record_edit', record_id=record_id))
        record.name_surname = name
        record.student_no = new_student_no
        record.project_title = project_title
        record.summary = summary
        was_rejected = record.status == 'rejected'
        if was_rejected:
            record.status = 'pending'
        try:
            db.session.commit()
            flash('Kaydnz gncellendi.' + (' Projeniz tekrar onaya sunuldu.' if was_rejected else ''), 'success')
        except IntegrityError:
            db.session.rollback()
            flash('Kayt gncellenirken hata olutu.', 'danger')
        return redirect(url_for('my_records'))
    return render_template('my_record_edit.html', record=record, target_list=target_list)


# PDF Trke karakter destei - DejaVuSans.ttf
_PDF_FONT_REGISTERED = False
_PDF_FONT_NAME = 'Helvetica'  # Varsaylan: Helvetica (Trke karakterler bozuk olabilir)

DEJAVU_FONT_NAME = 'DejaVuSans'


def _get_dejavu_font_path():
    """DejaVuSans.ttf dosyasnn tam yolunu dndrr. os.path ile Linux/Windows uyumlu."""
    # 1. Proje ana dizini (app.py ile ayn klasr) - Render sunucusu iin
    root_path = os.path.join(basedir, 'DejaVuSans.ttf')
    if os.path.isfile(root_path):
        return root_path
    # 2. fonts/ alt klasr
    fonts_path = os.path.join(basedir, 'fonts', 'DejaVuSans.ttf')
    if os.path.isfile(fonts_path):
        return fonts_path
    # 3. Sistem fontlar (Linux Render ortamnda olmayabilir)
    system_paths = [
        os.path.join('/usr', 'share', 'fonts', 'truetype', 'dejavu', 'DejaVuSans.ttf'),
        os.path.join('/usr', 'share', 'fonts', 'TTF', 'DejaVuSans.ttf'),
        os.path.join('/usr', 'share', 'fonts', 'truetype', 'liberation', 'LiberationSans-Regular.ttf'),
    ]
    for p in system_paths:
        if os.path.isfile(p):
            return p
    return None


def _register_dejavu_font():
    """
    DejaVuSans.ttf fontunu sisteme kaydeder.
    Font bulunamazsa uygulama kmez; Helvetica kullanlr ve log'a uyar yazlr.
    """
    global _PDF_FONT_REGISTERED, _PDF_FONT_NAME
    if _PDF_FONT_REGISTERED or not HAS_REPORTLAB:
        return _PDF_FONT_NAME
    font_path = _get_dejavu_font_path()
    if font_path:
        try:
            pdfmetrics.registerFont(TTFont(DEJAVU_FONT_NAME, font_path))
            _PDF_FONT_NAME = DEJAVU_FONT_NAME
            _PDF_FONT_REGISTERED = True
            logger.info("DejaVuSans.ttf fontu baaryla kaydedildi: %s", font_path)
        except Exception as e:
            logger.warning(
                "DejaVuSans.ttf kaydedilemedi (%s). Helvetica kullanlacak - "
                "Trke karakterler (, , , , , ) bozuk grnebilir. Hata: %s",
                font_path, str(e)
            )
    else:
        logger.warning(
            "DejaVuSans.ttf bulunamad (proje ana dizini veya fonts/ klasr kontrol edildi). "
            "Helvetica kullanlacak - Trke karakterler (, , , , , ) bozuk grnebilir."
        )
    return _PDF_FONT_NAME


@app.route('/download-pdf/<int:list_id>')
@login_required
@teacher_required
def download_pdf(list_id):
    target_list = ListVera.query.get_or_404(list_id)
    if target_list.owner_id != current_user.id:
        return "Yetkisiz ilem!", 403
    if not HAS_REPORTLAB:
        flash("PDF oluturmak iin 'pip install reportlab' ile reportlab kurulmaldr.", "warning")
        return redirect(url_for('list_detail', list_id=list_id))

    # Font kayd (DejaVuSans veya fallback Helvetica) - her PDF ncesi font ayarl
    font_name = _register_dejavu_font()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    elements = []

    # PDF st balk: Listify Report + gncel tarih
    header_style = ParagraphStyle(
        name='HeaderStyle', parent=styles['Normal'],
        fontSize=14, alignment=1, spaceAfter=4, textColor=colors.HexColor('#1e3a5f'),
        fontName=font_name
    )
    report_date_style = ParagraphStyle(
        name='ReportDateStyle', parent=styles['Normal'],
        fontSize=10, alignment=1, spaceAfter=20, textColor=colors.grey,
        fontName=font_name
    )
    elements.append(Paragraph('Listify Report', header_style))
    elements.append(Paragraph(datetime.now().strftime('%d.%m.%Y'), report_date_style))

    # Liste bal ve detay - font 'DejaVuSans' (veya Helvetica)
    title_style = ParagraphStyle(
        name='TitleStyle', parent=styles['Heading1'],
        fontSize=16, alignment=1, spaceAfter=8, textColor=colors.HexColor('#1e3a5f'),
        fontName=font_name
    )
    desc_style = ParagraphStyle(
        name='DescStyle', parent=styles['Normal'],
        fontSize=10, alignment=1, spaceAfter=16, textColor=colors.grey,
        fontName=font_name
    )
    date_style = ParagraphStyle(
        name='DateStyle', parent=styles['Normal'],
        fontSize=9, alignment=2, spaceAfter=20, textColor=colors.grey,
        fontName=font_name
    )

    elements.append(Paragraph(target_list.title, title_style))
    if target_list.description:
        elements.append(Paragraph(target_list.description, desc_style))
    elements.append(Paragraph(f"Dzenlenme Tarihi: {datetime.now().strftime('%d.%m.%Y')}", date_style))

    data = [['Ad Soyad', 'renci No', 'Proje Bal', 'Teslim Durumu', 'Not']]
    for s in target_list.students:
        has_submission = False
        grade_val = ' - '
        if s.user_id and target_list.assignments:
            for a in target_list.assignments:
                for sub in a.submissions:
                    if sub.user_id == s.user_id and sub.file_path:
                        has_submission = True
                        if sub.grade:
                            grade_val = str(sub.grade)
                        break
        teslim = 'Teslim Edildi' if has_submission else 'Teslim Edilmedi'
        data.append([
            s.display_name or '',
            s.display_student_no or '',
            s.project_title or '',
            teslim,
            grade_val
        ])

    col_widths = [4*cm, 2.5*cm, 5*cm, 3.5*cm, 2.5*cm]
    table = Table(data, colWidths=col_widths)
    # Tablo balk ve hcre metinleri iin font ayar
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    elements.append(table)

    try:
        doc.build(elements)
    except Exception as e:
        logger.exception("download_pdf: PDF oluturma hatas: %s", str(e))
        flash("PDF oluturulurken bir hata olutu. Ltfen tekrar deneyin.", "danger")
        return redirect(url_for('list_detail', list_id=list_id))
    buffer.seek(0)
    filename = f"liste_{target_list.unique_code}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return send_file(buffer, mimetype='application/pdf', as_attachment=False, download_name=filename)


# --- SIFRE TOPLU DONUSUM ---
def convert_all_passwords():
    """Duz metin sifreleri pbkdf2:sha256 ile hashleyip veritabanina yazar."""
    users = User.query.all()
    for user in users:
        if not user.password or not isinstance(user.password, str):
            continue
        if not user.password.startswith('pbkdf2:sha256'):
            user.password = generate_password_hash(user.password, method='pbkdf2:sha256')
    try:
        db.session.commit()
        logger.debug("Tum kullanicilarin sifreleri basariyla zirhlandi!")
    except Exception as e:
        db.session.rollback()
        logger.warning("convert_all_passwords commit hatasi: %s", e)


# --- ALITIRMA ---
def _ensure_db_columns():
    """Mevcut tablolara yeni stunlar ekler (migration)."""
    from sqlalchemy import text, inspect
    inspector = inspect(db.engine)
    dialect = db.engine.dialect.name
    try:
        if 'list_vera' in inspector.get_table_names():
            cols = [c['name'] for c in inspector.get_columns('list_vera')]
            if dialect == 'sqlite':
                if 'description' not in cols:
                    db.session.execute(text('ALTER TABLE list_vera ADD COLUMN description VARCHAR(500)'))
                if 'is_completed' not in cols:
                    db.session.execute(text('ALTER TABLE list_vera ADD COLUMN is_completed BOOLEAN DEFAULT 0'))
                if 'created_at' not in cols:
                    db.session.execute(text('ALTER TABLE list_vera ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP'))
                if 'expires_at' not in cols:
                    db.session.execute(text('ALTER TABLE list_vera ADD COLUMN expires_at DATETIME'))
                if 'announcement' not in cols:
                    db.session.execute(text('ALTER TABLE list_vera ADD COLUMN announcement TEXT'))
                if 'announcement_updated_at' not in cols:
                    db.session.execute(text('ALTER TABLE list_vera ADD COLUMN announcement_updated_at DATETIME'))
                if 'is_deleted' not in cols:
                    db.session.execute(text('ALTER TABLE list_vera ADD COLUMN is_deleted BOOLEAN DEFAULT 0'))
            elif dialect == 'postgresql':
                if 'description' not in cols:
                    db.session.execute(text('ALTER TABLE list_vera ADD COLUMN description VARCHAR(500)'))
                if 'is_completed' not in cols:
                    db.session.execute(text('ALTER TABLE list_vera ADD COLUMN is_completed BOOLEAN DEFAULT FALSE'))
                if 'created_at' not in cols:
                    db.session.execute(text('ALTER TABLE list_vera ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP'))
                if 'expires_at' not in cols:
                    db.session.execute(text('ALTER TABLE list_vera ADD COLUMN expires_at TIMESTAMP WITH TIME ZONE'))
                if 'announcement' not in cols:
                    db.session.execute(text('ALTER TABLE list_vera ADD COLUMN announcement TEXT'))
                if 'announcement_updated_at' not in cols:
                    db.session.execute(text('ALTER TABLE list_vera ADD COLUMN announcement_updated_at TIMESTAMP WITH TIME ZONE'))
                if 'is_deleted' not in cols:
                    db.session.execute(text('ALTER TABLE list_vera ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE'))
            db.session.commit()
    except Exception:
        db.session.rollback()
    try:
        if 'submission' in inspector.get_table_names():
            cols = [c['name'] for c in inspector.get_columns('submission')]
            if 'original_filename' not in cols:
                db.session.execute(text('ALTER TABLE submission ADD COLUMN original_filename VARCHAR(255)'))
                db.session.commit()
            if 'revision_requested' not in cols:
                if dialect == 'sqlite':
                    db.session.execute(text('ALTER TABLE submission ADD COLUMN revision_requested BOOLEAN DEFAULT 0'))
                elif dialect == 'postgresql':
                    db.session.execute(text('ALTER TABLE submission ADD COLUMN revision_requested BOOLEAN DEFAULT FALSE'))
                db.session.commit()
    except Exception:
        db.session.rollback()
    try:
        if 'user' in inspector.get_table_names():
            cols = [c['name'] for c in inspector.get_columns('user')]
            if 'role' not in cols:
                sql = "ALTER TABLE user ADD COLUMN role VARCHAR(20) DEFAULT 'student'"
                db.session.execute(text(sql))
                db.session.commit()
            if 'full_name' not in cols:
                db.session.execute(text('ALTER TABLE user ADD COLUMN full_name VARCHAR(200)'))
                db.session.commit()
            if 'student_number' not in cols:
                db.session.execute(text('ALTER TABLE user ADD COLUMN student_number VARCHAR(20)'))
                db.session.commit()
            if 'email' not in cols:
                sql = 'ALTER TABLE "user" ADD COLUMN email VARCHAR(254)' if dialect == 'postgresql' else 'ALTER TABLE user ADD COLUMN email VARCHAR(254)'
                db.session.execute(text(sql))
                db.session.commit()
            if 'is_verified' not in cols:
                if dialect == 'sqlite':
                    db.session.execute(text('ALTER TABLE user ADD COLUMN is_verified BOOLEAN DEFAULT 0'))
                elif dialect == 'postgresql':
                    db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE'))
                db.session.commit()
            try:
                if dialect == 'sqlite':
                    db.session.execute(text('UPDATE user SET is_verified = 1 WHERE is_verified IS NULL'))
                elif dialect == 'postgresql':
                    db.session.execute(text('UPDATE "user" SET is_verified = TRUE WHERE is_verified IS NULL'))
                db.session.commit()
            except Exception:
                db.session.rollback()
            if 'reset_token' not in cols:
                sql = 'ALTER TABLE "user" ADD COLUMN reset_token VARCHAR(64)' if dialect == 'postgresql' else 'ALTER TABLE user ADD COLUMN reset_token VARCHAR(64)'
                db.session.execute(text(sql))
                db.session.commit()
            if 'token_expiry' not in cols:
                if dialect == 'sqlite':
                    db.session.execute(text('ALTER TABLE user ADD COLUMN token_expiry DATETIME'))
                elif dialect == 'postgresql':
                    db.session.execute(text('ALTER TABLE "user" ADD COLUMN token_expiry TIMESTAMP WITH TIME ZONE'))
                db.session.commit()
            if 'verification_code' not in cols:
                sql = 'ALTER TABLE "user" ADD COLUMN verification_code VARCHAR(6)' if dialect == 'postgresql' else 'ALTER TABLE user ADD COLUMN verification_code VARCHAR(6)'
                db.session.execute(text(sql))
                db.session.commit()
            if 'code_expiry' not in cols:
                if dialect == 'sqlite':
                    db.session.execute(text('ALTER TABLE user ADD COLUMN code_expiry DATETIME'))
                elif dialect == 'postgresql':
                    db.session.execute(text('ALTER TABLE "user" ADD COLUMN code_expiry TIMESTAMP WITH TIME ZONE'))
                db.session.commit()
            try:
                if dialect == 'sqlite':
                    db.session.execute(text(
                        'CREATE UNIQUE INDEX IF NOT EXISTS ix_user_student_number ON user(student_number)'
                    ))
                elif dialect == 'postgresql':
                    db.session.execute(text(
                        'CREATE UNIQUE INDEX IF NOT EXISTS ix_user_student_number ON "user"(student_number)'
                    ))
                db.session.commit()
            except Exception:
                db.session.rollback()
    except Exception:
        db.session.rollback()
    try:
        if 'student_record' in inspector.get_table_names():
            cols = [c['name'] for c in inspector.get_columns('student_record')]
            if 'submission_status' not in cols:
                sql = "ALTER TABLE student_record ADD COLUMN submission_status VARCHAR(20) DEFAULT 'pending'"
                db.session.execute(text(sql))
                db.session.commit()
            if 'user_id' not in cols:
                if dialect == 'sqlite':
                    db.session.execute(text('ALTER TABLE student_record ADD COLUMN user_id INTEGER REFERENCES user(id)'))
                elif dialect == 'postgresql':
                    db.session.execute(text('ALTER TABLE student_record ADD COLUMN user_id INTEGER REFERENCES "user"(id)'))
                db.session.commit()
            if 'status' not in cols:
                sql = "ALTER TABLE student_record ADD COLUMN status VARCHAR(20) DEFAULT 'pending'"
                db.session.execute(text(sql))
                db.session.commit()
            if 'teacher_feedback' not in cols:
                if dialect == 'sqlite':
                    db.session.execute(text('ALTER TABLE student_record ADD COLUMN teacher_feedback TEXT'))
                elif dialect == 'postgresql':
                    db.session.execute(text('ALTER TABLE student_record ADD COLUMN teacher_feedback TEXT'))
                db.session.commit()
            if 'is_deleted' not in cols:
                if dialect == 'sqlite':
                    db.session.execute(text('ALTER TABLE student_record ADD COLUMN is_deleted BOOLEAN DEFAULT 0'))
                else:
                    db.session.execute(text('ALTER TABLE student_record ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE'))
                db.session.commit()
    except Exception:
        db.session.rollback()
    try:
        idx_list = ['ix_list_vera_owner_id', 'ix_list_vera_is_deleted', 'ix_student_record_is_deleted']
        for idx_name in idx_list:
            try:
                if dialect == 'sqlite':
                    tbl = 'list_vera' if 'list_vera' in idx_name else 'student_record'
                    col = 'owner_id' if 'owner_id' in idx_name else 'is_deleted'
                    db.session.execute(text(f'CREATE INDEX IF NOT EXISTS {idx_name} ON {tbl}({col})'))
                elif dialect == 'postgresql':
                    if 'list_vera' in idx_name:
                        col = 'owner_id' if 'owner_id' in idx_name else 'is_deleted'
                        db.session.execute(text(f'CREATE INDEX IF NOT EXISTS {idx_name} ON list_vera ({col})'))
                    else:
                        db.session.execute(text('CREATE INDEX IF NOT EXISTS ix_student_record_is_deleted ON student_record (is_deleted)'))
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.debug("Index %s olusturulamadi (muhtemelen mevcut): %s", idx_name, str(e))
    except Exception:
        db.session.rollback()


with app.app_context():
    db.create_all()


if __name__ == '__main__':
    # os.environ.get('PORT') ifadesi tırnak içinde OLMAMALI
    port_str = os.environ.get('PORT', '5000')
    port = int(port_str) 
    app.run(host='0.0.0.0', port=port)

# NOTE: file touched to force deployment diff
