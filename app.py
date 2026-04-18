import json
import os
import re
import secrets
import smtplib
import ssl
import time
import urllib.error
import urllib.request
from io import BytesIO
from datetime import datetime
from email.message import EmailMessage
from functools import wraps

from flask import Flask, abort, flash, make_response, redirect, render_template, request, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import check_password_hash, generate_password_hash

try:
    from authlib.integrations.flask_client import OAuth
except ImportError:
    OAuth = None

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
except ImportError:
    A4 = None
    canvas = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "login"
RATE_LIMIT_STATE = {}
POST_RATE_WINDOWS = {
    "resume_builder": (10, 3600),
    "career_lab": (10, 3600),
    "resume_score": (12, 3600),
    "interview_prep": (12, 3600),
    "cover_letter": (8, 3600),
}

ROLE_LIBRARY = {
    "Software Engineer": ["DSA", "Java or Python", "OOP", "DBMS", "SQL", "Git", "Problem Solving", "Projects", "Aptitude"],
    "Frontend Developer": ["HTML", "CSS", "JavaScript", "React", "Responsive Design", "Git", "APIs", "UI Projects", "Deployment"],
    "Backend Developer": ["Java or Python", "Node.js", "APIs", "SQL", "DBMS", "Authentication", "Git", "Deployment", "System Design Basics"],
    "Data Analyst": ["Excel", "SQL", "Python", "Pandas", "Data Cleaning", "Power BI", "Statistics", "Dashboards", "Communication"],
    "Data Scientist": ["Python", "Pandas", "NumPy", "Statistics", "Machine Learning", "SQL", "EDA", "Model Evaluation", "Projects"],
    "Product Analyst": ["SQL", "Excel", "Statistics", "A/B Testing", "Product Sense", "Dashboards", "Communication", "Experimentation"],
}

ROLE_ROADMAP_LIBRARY = {
    "Software Engineer": "Revise core CS subjects, build 2 projects, and practice coding rounds.",
    "Frontend Developer": "Polish responsive React projects, API usage, and UI explanation skills.",
    "Backend Developer": "Build auth-enabled APIs, understand SQL deeply, and revise backend architecture basics.",
    "Data Analyst": "Practice dashboard work, SQL queries, and business communication with clear insights.",
    "Data Scientist": "Build ML projects, strengthen statistics, and explain models with business impact.",
    "Product Analyst": "Practice metrics, funnel analysis, experimentation, and product case interviews.",
}

COMPANY_LIBRARY = {
    "google": {"emphasis": ["DSA", "Problem Solving", "Projects", "System Thinking", "Strong Fundamentals"], "note": "Top product companies usually expect excellent coding rounds and strong project depth."},
    "amazon": {"emphasis": ["DSA", "Problem Solving", "Leadership Stories", "Projects", "CS Fundamentals"], "note": "Behavioral preparation matters along with coding and project impact."},
    "microsoft": {"emphasis": ["DSA", "OOP", "Projects", "Problem Solving", "CS Fundamentals"], "note": "Balanced preparation across coding, implementation clarity, and project explanations helps."},
    "tcs": {"emphasis": ["Aptitude", "Communication", "Basic Coding", "Core Subjects", "Consistency"], "note": "Service companies often value aptitude, communication, and strong basics."},
    "infosys": {"emphasis": ["Aptitude", "Communication", "Basic Coding", "DBMS", "Projects"], "note": "A balanced beginner-friendly resume and clean fundamentals are useful here."},
    "wipro": {"emphasis": ["Aptitude", "Communication", "Basic Coding", "Projects", "Consistency"], "note": "Focus on fundamentals, aptitude, and interview communication."},
}

PACKAGE_LIBRARY = {
    "4-8 LPA": {"expected": "Build solid basics, one language, aptitude prep, and 1-2 simple projects.", "multiplier": 0.8},
    "8-12 LPA": {"expected": "Show stronger projects, coding practice, and clearer specialization.", "multiplier": 1.0},
    "12-20 LPA": {"expected": "Expect stronger DSA, project depth, and role-specific knowledge.", "multiplier": 1.15},
    "20+ LPA": {"expected": "High package roles usually need top-tier problem solving, standout projects, and strong fundamentals.", "multiplier": 1.3},
}

VIDEO_LIBRARY = {
    "DSA": {"title": "Data Structures and Algorithms Full Course", "channel": "Apna College / Love Babbar style track", "url": "https://www.youtube.com/results?search_query=data+structures+and+algorithms+full+course"},
    "React": {"title": "React Project-Based Learning Track", "channel": "CodeWithHarry / freeCodeCamp style track", "url": "https://www.youtube.com/results?search_query=react+project+based+course"},
    "SQL": {"title": "SQL for Interviews and Projects", "channel": "Alex The Analyst / freeCodeCamp style track", "url": "https://www.youtube.com/results?search_query=sql+full+course+for+beginners"},
    "Python": {"title": "Python for Placement Preparation", "channel": "Programming with Mosh / freeCodeCamp style track", "url": "https://www.youtube.com/results?search_query=python+full+course+for+beginners"},
    "Machine Learning": {"title": "Machine Learning Roadmap Course", "channel": "CampusX / Krish Naik style track", "url": "https://www.youtube.com/results?search_query=machine+learning+roadmap+course"},
    "Aptitude": {"title": "Placement Aptitude Preparation", "channel": "Freshersworld / Placement Prep style track", "url": "https://www.youtube.com/results?search_query=placement+aptitude+preparation"},
    "Power BI": {"title": "Power BI Dashboard Project Course", "channel": "Alex The Analyst style track", "url": "https://www.youtube.com/results?search_query=power+bi+project+course"},
    "Node.js": {"title": "Node.js Backend Development Course", "channel": "Hitesh Choudhary / freeCodeCamp style track", "url": "https://www.youtube.com/results?search_query=nodejs+backend+course"},
    "Statistics": {"title": "Statistics for Data Roles", "channel": "StatQuest / CampusX style track", "url": "https://www.youtube.com/results?search_query=statistics+for+data+science+beginners"},
}

ROADMAP_DURATIONS = [
    "1 month",
    "3 months",
    "6 months",
    "1 year",
    "2 years",
    "5 years",
    "7 years",
    "8 years",
    "10 years",
]

COMPANY_SOURCE_LIBRARY = {
    "google": {"label": "Google Careers", "domain": "careers.google.com", "homepage": "https://careers.google.com/"},
    "amazon": {"label": "Amazon Jobs", "domain": "amazon.jobs", "homepage": "https://www.amazon.jobs/"},
    "microsoft": {"label": "Microsoft Careers", "domain": "careers.microsoft.com", "homepage": "https://careers.microsoft.com/"},
    "tcs": {"label": "TCS Careers", "domain": "tcs.com/careers", "homepage": "https://www.tcs.com/careers"},
    "infosys": {"label": "Infosys Careers", "domain": "careers.infosys.com", "homepage": "https://www.infosys.com/careers.html"},
    "wipro": {"label": "Wipro Careers", "domain": "careers.wipro.com", "homepage": "https://careers.wipro.com/"},
}

RESUME_THEMES = {
    "classic": {
        "name": "Classic Pro",
        "tagline": "Clean, recruiter-friendly, and ATS-safe.",
        "pdf_rgb": (0.12, 0.20, 0.35),
    },
    "modern": {
        "name": "Modern Edge",
        "tagline": "Bold header with sharper section hierarchy.",
        "pdf_rgb": (0.52, 0.18, 0.14),
    },
    "minimal": {
        "name": "Minimal Mono",
        "tagline": "Simple layout focused on clarity and whitespace.",
        "pdf_rgb": (0.18, 0.18, 0.18),
    },
}


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)
    google_id = db.Column(db.String(255), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Resume(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    theme = db.Column(db.String(64), nullable=False, default="classic")
    payload_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def create_app():
    app = Flask(__name__)
    secret_key = os.getenv("SECRET_KEY")
    if os.getenv("FLASK_ENV") == "production" and not secret_key:
        raise RuntimeError("SECRET_KEY must be set in production.")
    app.config["SECRET_KEY"] = secret_key or "resume-spark-dev-secret"
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'resumespark.db')}")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["ANTHROPIC_MODEL"] = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
    db.init_app(app)
    login_manager.init_app(app)

    oauth = None
    if OAuth is not None:
        oauth = OAuth(app)
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        if client_id and client_secret:
            oauth.register(
                name="google",
                client_id=client_id,
                client_secret=client_secret,
                server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
                client_kwargs={"scope": "openid email profile"},
            )
    app.extensions["oauth_client"] = oauth

    app.config["DB_INIT_ERROR"] = None
    with app.app_context():
        try:
            db.create_all()
        except Exception as exc:
            app.config["DB_INIT_ERROR"] = str(exc)

    @app.context_processor
    def inject_template_helpers():
        return {
            "csrf_token": csrf_token,
            "is_ai_configured": is_ai_configured,
        }

    @app.before_request
    def protect_post_routes():
        if request.method == "POST":
            validate_csrf()

    register_routes(app)
    return app


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def register_routes(app):
    @app.route("/")
    def index():
        return redirect(url_for("dashboard")) if current_user.is_authenticated else render_template("index.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")
            if not name or not email or not password:
                flash("Please fill in name, email, and password.", "error")
            elif len(password) < 8:
                flash("Password must be at least 8 characters long.", "error")
            elif password != confirm_password:
                flash("Passwords do not match.", "error")
            elif User.query.filter_by(email=email).first():
                flash("An account with that email already exists.", "error")
            else:
                user = User(name=name, email=email, password_hash=generate_password_hash(password))
                db.session.add(user)
                db.session.commit()
                login_user(user)
                flash("Your account has been created.", "success")
                return redirect(url_for("dashboard"))
        return render_template("signup.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()
            if user and user.password_hash and check_password_hash(user.password_hash, password):
                login_user(user, remember=True)
                flash("Welcome back to ResumeSpark.", "success")
                return redirect(url_for("dashboard"))
            flash("Invalid email or password.", "error")
        return render_template("login.html", google_ready=is_google_ready(app))

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been signed out.", "success")
        return redirect(url_for("login"))

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        reset_link = None
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            user = User.query.filter_by(email=email).first()
            if user:
                token = generate_reset_token(app, user.email)
                reset_link = url_for("reset_password", token=token, _external=True)
                if send_password_reset_email(user.email, reset_link):
                    flash("Password reset email sent.", "success")
                else:
                    flash("Reset link generated. Configure SMTP to send it automatically.", "success")
            else:
                flash("No account found with that email.", "error")
        return render_template("forgot_password.html", reset_link=reset_link)

    @app.route("/reset-password/<token>", methods=["GET", "POST"])
    def reset_password(token):
        email = verify_reset_token(app, token)
        if not email:
            flash("That reset link is invalid or expired.", "error")
            return redirect(url_for("forgot_password"))
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("Account not found.", "error")
            return redirect(url_for("signup"))
        if request.method == "POST":
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")
            if not password:
                flash("Password cannot be empty.", "error")
            elif password != confirm_password:
                flash("Passwords do not match.", "error")
            else:
                user.password_hash = generate_password_hash(password)
                db.session.commit()
                flash("Password updated successfully. Please sign in.", "success")
                return redirect(url_for("login"))
        return render_template("reset_password.html")

    @app.route("/login/google")
    def google_login():
        oauth = app.extensions.get("oauth_client")
        if not is_google_ready(app):
            flash("Google login is not configured yet. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to enable it.", "error")
            return redirect(url_for("login"))
        return oauth.google.authorize_redirect(url_for("google_callback", _external=True))

    @app.route("/auth/google/callback")
    def google_callback():
        oauth = app.extensions.get("oauth_client")
        if not is_google_ready(app):
            flash("Google login is not configured yet.", "error")
            return redirect(url_for("login"))
        token = oauth.google.authorize_access_token()
        user_info = token.get("userinfo") or oauth.google.userinfo()
        email = user_info["email"].strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(name=user_info.get("name", email.split("@")[0]), email=email, google_id=user_info.get("sub"))
            db.session.add(user)
        else:
            user.google_id = user_info.get("sub")
        db.session.commit()
        login_user(user, remember=True)
        flash("Signed in with Google.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        recent_resumes = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.created_at.desc()).limit(5).all()
        return render_template(
            "dashboard.html",
            db_init_error=app.config.get("DB_INIT_ERROR"),
            recent_resumes=recent_resumes,
        )

    @app.route("/resume-builder", methods=["GET", "POST"])
    @login_required
    @rate_limit_route("resume_builder")
    def resume_builder():
        generated_resume = None
        generated_resume_html = None
        form_data = {}
        loaded_resume = None
        resume_id = request.args.get("resume_id", type=int)
        if request.method == "GET" and resume_id:
            loaded_resume = Resume.query.filter_by(id=resume_id, user_id=current_user.id).first_or_404()
            form_data = json.loads(loaded_resume.payload_json)
            normalize_payload_projects(form_data)
            generated_resume, generated_resume_html = generate_resume_bundle(form_data)
        if request.method == "POST":
            form_data = request.form.to_dict()
            normalize_payload_projects(form_data)
            generated_resume, generated_resume_html = generate_resume_bundle(form_data)
            saved_resume = save_resume_record(current_user.id, form_data)
            loaded_resume = saved_resume
            flash("Resume draft created and saved to your profile.", "success")
        return render_template(
            "create_resume.html",
            generated_resume=generated_resume,
            generated_resume_html=generated_resume_html,
            form_data=form_data,
            role_options=get_role_options(),
            resume_themes=RESUME_THEMES,
            loaded_resume=loaded_resume,
        )

    @app.route("/resume-builder/pdf", methods=["POST"])
    @login_required
    def resume_builder_pdf():
        if canvas is None or A4 is None:
            flash("PDF support is not installed yet. Run `python -m pip install -r requirements.txt` to add ReportLab.", "error")
            return redirect(url_for("resume_builder"))
        payload = request.form.to_dict()
        normalize_payload_projects(payload)
        resume_text = build_resume_draft(payload)
        pdf_bytes = generate_resume_pdf(resume_text, payload)
        filename = safe_filename(request.form.get("studentName", "resume")) + ".pdf"
        response = make_response(pdf_bytes.getvalue())
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @app.route("/career-lab", methods=["GET", "POST"])
    @login_required
    @rate_limit_route("career_lab")
    def career_lab():
        analysis = None
        form_data = {}
        if request.method == "POST":
            form_data = request.form.to_dict()
            analysis = analyze_profile(form_data)
            flash("Career roadmap generated.", "success")
        return render_template(
            "career_lab.html",
            analysis=analysis,
            form_data=form_data,
            role_options=get_role_options(),
            roadmap_durations=ROADMAP_DURATIONS,
        )

    @app.route("/resume-score", methods=["GET", "POST"])
    @login_required
    @rate_limit_route("resume_score")
    def resume_score():
        form_data = {}
        score = None
        if request.method == "POST":
            form_data = request.form.to_dict()
            uploaded_file = request.files.get("resumeFile")
            if uploaded_file and uploaded_file.filename:
                extracted_text, extraction_message = extract_resume_text_from_file(uploaded_file)
                if extraction_message:
                    flash(extraction_message, "error")
                elif extracted_text:
                    form_data["resumeText"] = extracted_text
                    flash("Resume file uploaded and parsed successfully.", "success")
            if not form_data.get("resumeText", "").strip():
                flash("Please paste resume text or upload a supported resume file.", "error")
                return render_template("resume_score.html", form_data=form_data, score=None, role_options=get_role_options())
            score = score_resume_payload(form_data)
            flash("Resume score generated.", "success")
        return render_template("resume_score.html", form_data=form_data, score=score, role_options=get_role_options())

    @app.route("/interview-prep", methods=["GET", "POST"])
    @login_required
    @rate_limit_route("interview_prep")
    def interview_prep():
        form_data = request.args.to_dict() if request.method == "GET" else request.form.to_dict()
        result = None
        if form_data.get("targetRole") or form_data.get("targetRoleCustom"):
            result = generate_interview_prep(form_data)
            if request.method == "POST":
                flash("Interview preparation set generated.", "success")
        return render_template("interview_prep.html", form_data=form_data, result=result, role_options=get_role_options())

    @app.route("/cover-letter", methods=["GET", "POST"])
    @login_required
    @rate_limit_route("cover_letter")
    def cover_letter():
        form_data = {}
        draft = None
        if request.method == "POST":
            form_data = request.form.to_dict()
            normalize_payload_projects(form_data)
            draft = generate_cover_letter(form_data)
            flash("Cover letter created.", "success")
        return render_template("cover_letter.html", form_data=form_data, draft=draft, role_options=get_role_options())

    @app.route("/cover-letter/pdf", methods=["POST"])
    @login_required
    def cover_letter_pdf():
        if canvas is None or A4 is None:
            flash("PDF support is not installed yet. Run `python -m pip install -r requirements.txt` to add ReportLab.", "error")
            return redirect(url_for("cover_letter"))
        payload = request.form.to_dict()
        normalize_payload_projects(payload)
        draft = generate_cover_letter(payload)
        pdf_bytes = generate_letter_pdf(draft, payload)
        filename = safe_filename(payload.get("studentName", "cover-letter")) + "-cover-letter.pdf"
        response = make_response(pdf_bytes.getvalue())
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

def is_google_ready(app):
    oauth = app.extensions.get("oauth_client")
    return oauth is not None and hasattr(oauth, "google")


def generate_reset_token(app, email):
    return URLSafeTimedSerializer(app.config["SECRET_KEY"]).dumps(email, salt="password-reset")


def verify_reset_token(app, token, max_age=3600):
    serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
    try:
        return serializer.loads(token, salt="password-reset", max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def validate_csrf():
    token = request.form.get("csrf_token")
    if not token or token != session.get("_csrf_token"):
        abort(400, "Missing or invalid CSRF token.")


def rate_limit_route(limit_key):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if request.method != "POST":
                return func(*args, **kwargs)
            limit_count, window_seconds = POST_RATE_WINDOWS[limit_key]
            identifier = f"{limit_key}:{current_user.get_id() if current_user.is_authenticated else request.remote_addr}"
            now = time.time()
            timestamps = [stamp for stamp in RATE_LIMIT_STATE.get(identifier, []) if now - stamp < window_seconds]
            if len(timestamps) >= limit_count:
                flash("Too many requests in a short time. Please wait a bit and try again.", "error")
                return redirect(request.referrer or url_for("dashboard"))
            timestamps.append(now)
            RATE_LIMIT_STATE[identifier] = timestamps
            return func(*args, **kwargs)
        return wrapper
    return decorator


def is_ai_configured():
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def call_claude_json(system_prompt, user_prompt, fallback=None):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return fallback
    payload = {
        "model": os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
        "max_tokens": 1400,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    request_data = json.dumps(payload).encode("utf-8")
    http_request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=request_data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(http_request, timeout=30) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return fallback

    blocks = response_payload.get("content", [])
    text_parts = [block.get("text", "") for block in blocks if isinstance(block, dict) and block.get("type") == "text"]
    raw_text = "\n".join(text_parts).strip()
    if not raw_text:
        return fallback
    try:
        return json.loads(extract_json_block(raw_text))
    except json.JSONDecodeError:
        return fallback


def extract_json_block(text):
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


def send_password_reset_email(recipient, reset_link):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_sender = os.getenv("SMTP_SENDER")
    if not all([smtp_host, smtp_port, smtp_user, smtp_password, smtp_sender]):
        return False

    message = EmailMessage()
    message["Subject"] = "ResumeSpark password reset"
    message["From"] = smtp_sender
    message["To"] = recipient
    message.set_content(
        f"Use the link below to reset your ResumeSpark password:\n\n{reset_link}\n\n"
        "If you did not request this, you can ignore this email."
    )
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_password)
            server.send_message(message)
        return True
    except Exception:
        return False


def save_resume_record(user_id, payload):
    title = payload.get("resumeTitle", "").strip() or f"{payload.get('studentName', 'Resume').strip() or 'Resume'} Resume"
    record = Resume(
        user_id=user_id,
        title=title,
        theme=(payload.get("resumeTheme", "classic") or "classic").strip(),
        payload_json=json.dumps(payload),
    )
    db.session.add(record)
    db.session.commit()
    return record


def clean_project_entry(raw_value):
    text = str(raw_value or "").strip()
    if not text:
        return ""
    text = re.sub(r"^\s*(?:[-*]|\u2022|[0-9]+[.)-]?)\s*", "", text)
    return text.strip()


def extract_projects(payload, target_role=None, include_defaults=True):
    projects = []

    def add_project(raw_value):
        cleaned = clean_project_entry(raw_value)
        if cleaned and cleaned not in projects:
            projects.append(cleaned)

    projects_text = payload.get("projectsText", "")
    if isinstance(projects_text, str):
        normalized_text = projects_text.strip()
        lines = normalized_text.splitlines() if normalized_text else []
        if len(lines) == 1 and "," in lines[0]:
            lines = lines[0].split(",")
        for line in lines:
            add_project(line)

    raw_projects = payload.get("projects")
    if isinstance(raw_projects, list):
        for item in raw_projects:
            add_project(item)

    add_project(payload.get("projectOne", ""))
    add_project(payload.get("projectTwo", ""))

    if not projects and include_defaults:
        role_name = target_role or resolve_target_role(payload)
        projects = [f"{role_name} Project", "Practice / Academic Project"]
    return projects


def normalize_payload_projects(payload, target_role=None):
    projects = extract_projects(payload, target_role=target_role, include_defaults=False)
    payload["projectsText"] = "\n".join(projects)
    payload["projectOne"] = projects[0] if projects else ""
    payload["projectTwo"] = projects[1] if len(projects) > 1 else ""
    return projects


def generate_resume_bundle(payload):
    preview = build_resume_preview(payload)
    draft = build_resume_draft(payload)
    ai_result = enhance_resume_with_ai(payload) if payload.get("aiEnhance") == "on" else None
    if ai_result:
        preview["summary"] = ai_result.get("summary", preview["summary"])
        projects = ai_result.get("projects")
        if isinstance(projects, list):
            refined_projects = []
            for item in projects:
                cleaned = clean_project_entry(item)
                if cleaned and cleaned not in refined_projects:
                    refined_projects.append(cleaned)
            if refined_projects:
                preview["projects"] = refined_projects
        preview["internship"] = ai_result.get("experience", preview["internship"])
        draft_payload = {
            **payload,
            "summary": preview["summary"],
            "projectsText": "\n".join(preview["projects"]),
            "internship": preview["internship"],
        }
        normalize_payload_projects(draft_payload, target_role=preview["role"])
        draft = build_resume_draft(
            draft_payload
        )
    return draft, preview


def enhance_resume_with_ai(payload):
    fallback = None
    return call_claude_json(
        "You rewrite student resume content. Return only compact JSON with keys summary, projects, experience.",
        json.dumps(
            {
                "target_role": resolve_target_role(payload),
                "target_company": payload.get("targetCompany", ""),
                "summary": payload.get("summary", ""),
                "projects": extract_projects(payload, include_defaults=False),
                "internship": payload.get("internship", ""),
                "skills": payload.get("skills", ""),
            }
        ),
        fallback=fallback,
    )


def extract_resume_text_from_file(uploaded_file):
    filename = (uploaded_file.filename or "").lower()
    if not filename:
        return "", "No file selected."
    content = uploaded_file.read()
    if not content:
        return "", "Uploaded file is empty."

    if filename.endswith((".txt", ".md", ".json", ".csv")):
        return content.decode("utf-8", errors="ignore"), None

    if filename.endswith(".pdf"):
        if PdfReader is None:
            return "", "PDF upload needs `pypdf`. Run `python -m pip install -r requirements.txt`."
        try:
            reader = PdfReader(BytesIO(content))
            text = "\n".join([(page.extract_text() or "") for page in reader.pages]).strip()
            if not text:
                return "", "No text could be extracted from that PDF."
            return text, None
        except Exception:
            return "", "Could not parse that PDF. Try another file or paste resume text."

    return "", "Unsupported file type. Upload .txt, .md, .json, .csv, or .pdf."


def score_resume_payload(payload):
    resume_text = payload.get("resumeText", "").strip()
    target_role = resolve_target_role(payload)
    target_company = payload.get("targetCompany", "").strip()
    role_skills = ROLE_LIBRARY.get(target_role, infer_custom_role_skills(target_role))
    company_data = COMPANY_LIBRARY.get(target_company.lower(), {"emphasis": ["Projects", "Communication", "Problem Solving"], "note": ""})
    required_skills = unique_list(role_skills + company_data["emphasis"])
    bank = resume_text.lower()
    matched = [skill for skill in required_skills if has_skill_match(skill, bank)]
    keyword_score = round((len(matched) / max(len(required_skills), 1)) * 100)
    readability = min(100, max(30, 100 - abs(len(resume_text.split()) - 350) // 3))
    section_bonus = 0
    for section in ["summary", "skills", "project", "education", "experience", "achievement"]:
        if section in bank:
            section_bonus += 8
    overall = min(100, round((keyword_score * 0.55) + (readability * 0.25) + min(section_bonus, 20)))
    tips = []
    if len(matched) < len(required_skills) // 2:
        tips.append("Add more target-role keywords and tools directly into your resume bullets.")
    if "project" not in bank:
        tips.append("Add a projects section with measurable outcomes and technologies used.")
    if len(resume_text.split()) < 180:
        tips.append("The resume looks too short. Add stronger detail for projects, experience, and achievements.")
    if len(resume_text.split()) > 650:
        tips.append("The resume is too long for a fresher profile. Tighten bullets and remove repetition.")
    if not tips:
        tips.append("The structure is solid. Focus next on sharper achievements and job-specific tailoring.")
    return {
        "overall": overall,
        "keyword_score": keyword_score,
        "readability": readability,
        "matched_skills": matched[:10],
        "missing_skills": [skill for skill in required_skills if skill not in matched][:10],
        "tips": tips,
    }


def generate_interview_prep(payload):
    fallback = build_fallback_interview_prep(payload)
    ai_result = call_claude_json(
        "You create realistic interview prep sets for students. Return JSON with keys: "
        "company_focus, technical_questions, behavioral_questions, scenario_questions, "
        "preparation_tips, mock_plan. Each key except company_focus must contain a list of strings.",
        json.dumps(
            {
                "role": resolve_target_role(payload),
                "company": payload.get("targetCompany", ""),
                "package": payload.get("targetPackage", ""),
                "skills": payload.get("skills", ""),
                "resume_text": payload.get("resumeText", ""),
                "difficulty": payload.get("difficulty", "Intermediate"),
            }
        ),
        fallback=None,
    )
    if not ai_result:
        return fallback
    required = ["technical_questions", "behavioral_questions", "scenario_questions", "preparation_tips", "mock_plan"]
    if not all(isinstance(ai_result.get(key), list) for key in required):
        return fallback
    ai_result["company_focus"] = ai_result.get("company_focus") or fallback["company_focus"]
    return ai_result


def build_fallback_interview_prep(payload):
    role = resolve_target_role(payload)
    company = payload.get("targetCompany", "").strip() or "your target company"
    difficulty = payload.get("difficulty", "Intermediate")
    company_focus = (
        f"{company} interviewers usually evaluate role fundamentals, project clarity, and communication depth. "
        f"Use {difficulty.lower()}-level examples and explain impact with measurable outcomes."
    )
    technical = [
        f"Walk me through a project that best prepares you for a {role} role.",
        f"What are the most important skills for a {role}, and how have you practiced them?",
        f"How would you solve a common {role} problem under time pressure?",
        f"What tradeoffs would you consider when working on a project for {company}?",
        f"If your first approach fails during a {role} interview round, how would you recover?",
    ]
    behavioral = [
        "Tell me about yourself and why you are applying for this role.",
        f"Why do you want to work at {company}?",
        "Describe a time you learned something difficult quickly.",
        "Tell me about a challenge, mistake, or conflict and how you handled it.",
        "Give an example of how you handled feedback and improved your work.",
    ]
    scenario = [
        f"You are given a production issue in a {role} task with a tight deadline. What is your response plan?",
        f"Your interviewer challenges one of your project decisions. How do you defend or adjust your approach?",
        f"You have two offers: one higher pay and one better learning. How would you choose and justify it?",
    ]
    tips = [
        "Prepare one strong story each for learning, teamwork, ownership, and problem-solving.",
        "Practice explaining projects using Problem, Action, Stack, Impact, and Lessons.",
        "Revise role-specific fundamentals and keep one whiteboard-style explanation ready.",
        "Use STAR format for behavioral answers and keep each response under 90 seconds.",
    ]
    mock_plan = [
        "Round 1: 20 minutes technical screening with project and fundamentals.",
        "Round 2: 25 minutes problem-solving round under time pressure.",
        "Round 3: 20 minutes behavioral and culture-fit discussion.",
        "Round 4: 10 minutes final questions for interviewer and role expectations.",
    ]
    return {
        "company_focus": company_focus,
        "technical_questions": technical,
        "behavioral_questions": behavioral,
        "scenario_questions": scenario,
        "preparation_tips": tips,
        "mock_plan": mock_plan,
    }


def generate_cover_letter(payload):
    fallback = build_cover_letter_fallback(payload)
    ai_result = call_claude_json(
        "You write fresher-friendly cover letters. Return JSON with one key cover_letter containing the full letter.",
        json.dumps(
            {
                "student_name": payload.get("studentName", ""),
                "role": resolve_target_role(payload),
                "company": payload.get("targetCompany", ""),
                "skills": payload.get("skills", ""),
                "summary": payload.get("summary", ""),
                "projects": extract_projects(payload, include_defaults=False),
                "experience": payload.get("internship", ""),
            }
        ),
        fallback=None,
    )
    return ai_result.get("cover_letter") if ai_result and ai_result.get("cover_letter") else fallback


def build_cover_letter_fallback(payload):
    student_name = payload.get("studentName", "").strip() or "Student Name"
    role = resolve_target_role(payload)
    company = payload.get("targetCompany", "").strip() or "the company"
    skills = payload.get("skills", "").strip() or "problem solving, communication, and practical project work"
    projects = ", ".join(extract_projects(payload, include_defaults=False)) or "practical student projects"
    return (
        f"Dear Hiring Team,\n\n"
        f"I am writing to apply for the {role} opportunity at {company}. I am a motivated student who has been building hands-on experience through {projects} and strengthening skills in {skills}.\n\n"
        f"What attracts me most to {company} is the chance to learn quickly, contribute with ownership, and grow in a strong team environment. I enjoy turning ideas into practical work, explaining what I build clearly, and continuously improving based on feedback.\n\n"
        f"I would value the opportunity to contribute as a fresher who is eager to learn fast and deliver meaningful work. Thank you for your time and consideration.\n\n"
        f"Sincerely,\n{student_name}"
    )


def generate_ai_career_analysis(payload):
    result = call_claude_json(
        "You generate career plans for students. Return JSON with keys required_skills, roadmap, video_tracks, package_expectation, company_note. "
        "Each video_tracks item must have keys skill, title, channel, url.",
        json.dumps(
            {
                "role": resolve_target_role(payload),
                "company": payload.get("targetCompany", ""),
                "package": payload.get("targetPackage", ""),
                "skills": payload.get("skills", ""),
                "resume_text": payload.get("resumeText", ""),
                "roadmap_duration": payload.get("roadmapDuration", ""),
            }
        ),
        fallback=None,
    )
    if not result:
        return None
    if not isinstance(result.get("required_skills"), list) or not isinstance(result.get("roadmap"), list):
        return None
    result["video_tracks"] = result.get("video_tracks") or []
    return result


def analyze_profile(payload):
    target_company = payload.get("targetCompany", "").strip()
    target_role = resolve_target_role(payload)
    target_package = payload.get("targetPackage", "8-12 LPA")
    skills = payload.get("skills", "")
    resume_text = payload.get("resumeText", "")
    ai_analysis = generate_ai_career_analysis(payload) if is_ai_configured() else None
    company_data = COMPANY_LIBRARY.get(target_company.lower(), {"emphasis": ["Projects", "Communication", "Problem Solving"], "note": "Different companies ask for different strengths, so tailor your resume to the role and application."})
    package_data = PACKAGE_LIBRARY.get(target_package, PACKAGE_LIBRARY["8-12 LPA"])
    role_skills = ai_analysis.get("required_skills") if ai_analysis else ROLE_LIBRARY.get(target_role, infer_custom_role_skills(target_role))
    required_skills = unique_list(role_skills + ([] if ai_analysis else company_data["emphasis"]))
    bank = f"{skills} {resume_text}".lower()
    matched = [skill for skill in required_skills if has_skill_match(skill, bank)]
    missing = [skill for skill in required_skills if not has_skill_match(skill, bank)]
    fit_score = min(100, max(18, round((len(matched) / max(len(required_skills), 1)) * 100 * package_data["multiplier"])))
    return {
        "target_role": target_role,
        "required_skills": required_skills,
        "matched_skills": matched,
        "missing_skills": missing,
        "fit_score": fit_score,
        "package_expectation": ai_analysis.get("package_expectation") if ai_analysis else package_data["expected"],
        "company_note": ai_analysis.get("company_note") if ai_analysis else company_data["note"],
        "roadmap": ai_analysis.get("roadmap") if ai_analysis else build_roadmap(payload, missing, company_data),
        "video_tracks": ai_analysis.get("video_tracks") if ai_analysis else build_video_tracks(missing, required_skills),
        "skill_sources": build_skill_sources(required_skills, target_company, target_role),
        "resume_draft": build_resume_draft(payload),
    }


def has_skill_match(skill, text):
    aliases = {
        "Java or Python": ["java", "python"],
        "OOP": ["oop", "object oriented"],
        "DBMS": ["dbms", "database"],
        "Problem Solving": ["problem solving", "leetcode", "coding"],
        "Projects": ["project", "projects"],
        "Aptitude": ["aptitude", "quant", "reasoning"],
        "Responsive Design": ["responsive", "media query"],
        "UI Projects": ["ui", "frontend project", "portfolio"],
        "APIs": ["api", "rest api"],
        "System Design Basics": ["system design", "scalability"],
        "Machine Learning": ["machine learning", "ml"],
        "Data Cleaning": ["data cleaning", "cleaning"],
        "Power BI": ["power bi", "dashboard"],
        "A/B Testing": ["a/b testing", "ab testing", "experimentation"],
        "Leadership Stories": ["leadership", "teamwork"],
        "Strong Fundamentals": ["dbms", "oops", "os", "networking"],
        "System Thinking": ["system design", "architecture"],
        "Communication": ["communication", "presentation", "speaker"],
    }
    return any(term in text for term in aliases.get(skill, [skill.lower()]))


def unique_list(items):
    output = []
    seen = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output


def build_roadmap(payload, missing, company_data):
    top_missing = missing[:4]
    role = resolve_target_role(payload)
    target_company = payload.get("targetCompany", "").strip() or "your target company"
    duration = payload.get("roadmapDuration", "6 months")
    timeline_labels = build_timeline_labels(duration)
    projects = {
        "Software Engineer": "a full-stack student portal and a placement tracker",
        "Frontend Developer": "a portfolio landing page and a responsive job dashboard",
        "Backend Developer": "an auth-enabled REST API and a resume analysis backend",
        "Data Analyst": "a sales dashboard and a hiring trend analysis report",
        "Data Scientist": "a salary prediction model and a resume classification project",
        "Product Analyst": "a funnel analysis dashboard and an A/B test case study",
    }
    return [
        {"title": f"{timeline_labels[0]}: Build your core", "text": f"Focus on {', '.join(top_missing[:2]) or 'the fundamentals for your role'} and create a realistic weekly study routine that fits your selected timeline of {duration}."},
        {"title": f"{timeline_labels[1]}: Make projects visible", "text": f"Build or improve {projects.get(role, f'two role-specific projects for {role}')}. Show outcomes, tech stack, and what problem each project solves."},
        {"title": f"{timeline_labels[2]}: Interview prep", "text": f"{ROLE_ROADMAP_LIBRARY.get(role, f'Revise the fundamentals and practical tools used by {role}s.')} Also rehearse answers around {', '.join(company_data['emphasis'][:3])}."},
        {"title": f"{timeline_labels[3]}: Application push", "text": f"Tailor your resume to {target_company}, update LinkedIn, and apply with measurable projects plus concise resume bullets."},
    ]


def build_video_tracks(missing, required):
    focus = unique_list(missing + required)[:5]
    tracks = []
    for skill in focus:
        resource = VIDEO_LIBRARY.get(skill) or VIDEO_LIBRARY.get(skill.split(" ")[0]) or {
            "title": f"{skill} learning track",
            "channel": "YouTube search results",
            "url": f"https://www.youtube.com/results?search_query={skill.replace(' ', '+')}+course+for+beginners",
        }
        tracks.append({"skill": skill, **resource})
    return tracks


def build_resume_draft(payload):
    student_name = payload.get("studentName", "").strip() or "Student Name"
    degree = payload.get("degree", "").strip() or "Degree / Branch"
    target_role = resolve_target_role(payload)
    target_company = payload.get("targetCompany", "").strip() or "top companies"
    college = payload.get("college", "").strip() or "Add college name"
    graduation_year = payload.get("graduationYear", "").strip() or "Add graduation year"
    phone = payload.get("phone", "").strip()
    email = payload.get("contactEmail", "").strip() or payload.get("email", "").strip()
    city = payload.get("city", "").strip()
    linkedin = payload.get("linkedin", "").strip()
    github = payload.get("github", "").strip()
    summary = payload.get("summary", "").strip()
    internship = payload.get("internship", "").strip()
    certifications = payload.get("certifications", "").strip()
    skills = ", ".join([item.strip() for item in payload.get("skills", "").split(",") if item.strip()][:8]) or "Add your technical skills here"
    projects = extract_projects(payload, target_role=target_role)
    achievements = payload.get("achievements", "").strip() or "Add coding profiles, certifications, hackathons, or strong coursework here."
    contact_line = " | ".join([item for item in [phone, email, city, linkedin, github] if item]) or "Add phone, email, city, LinkedIn, and GitHub"
    project_lines = []
    for index, project in enumerate(projects, start=1):
        project_lines.append(f"{index}. {project}")
        project_lines.append("Built a practical project using relevant tools for the target role and explained the problem, solution, and impact in concise bullets.")
        project_lines.append("")
    return "\n".join([
        student_name,
        contact_line,
        f"{degree} | Target Role: {target_role}",
        "",
        "Professional Summary",
        summary or f"Motivated candidate aiming for {target_role} opportunities at {target_company}. Focused on building practical projects, strengthening fundamentals, and becoming interview-ready for entry-level roles.",
        "",
        "Skills",
        skills,
        "",
        "Projects",
        *project_lines,
        "Internship / Experience",
        internship or "Add internships, freelance work, training, or team contributions here.",
        "",
        "Education",
        f"{degree} | {college} | {graduation_year}",
        "",
        "Certifications",
        certifications or "Add certifications, coursework, or workshops here.",
        "",
        "Achievements",
        achievements,
    ])


def build_resume_preview(payload):
    target_role = resolve_target_role(payload)
    theme_key, theme = resolve_resume_theme(payload)
    header_links = [item for item in [
        payload.get("phone", "").strip(),
        payload.get("contactEmail", "").strip() or payload.get("email", "").strip(),
        payload.get("city", "").strip(),
        payload.get("linkedin", "").strip(),
        payload.get("github", "").strip(),
    ] if item]
    skills = [item.strip() for item in payload.get("skills", "").split(",") if item.strip()]
    projects = extract_projects(payload, target_role=target_role)
    return {
        "theme_key": theme_key,
        "theme_name": theme["name"],
        "tagline": theme["tagline"],
        "name": payload.get("studentName", "").strip() or "Student Name",
        "role": target_role,
        "degree": payload.get("degree", "").strip() or "Degree / Branch",
        "company": payload.get("targetCompany", "").strip() or "Dream Company",
        "contact_items": header_links,
        "summary": payload.get("summary", "").strip() or f"Motivated candidate targeting {target_role} opportunities and ready to build strong projects with industry-focused skills.",
        "skills": skills or ["Add your technical skills here"],
        "projects": projects,
        "internship": payload.get("internship", "").strip() or "Add internships, freelance work, training, or team contributions here.",
        "education": f"{payload.get('degree', '').strip() or 'Degree / Branch'} | {payload.get('college', '').strip() or 'College Name'} | {payload.get('graduationYear', '').strip() or 'Passing Year'}",
        "certifications": payload.get("certifications", "").strip() or "Add certifications, workshops, or role-specific courses here.",
        "achievements": payload.get("achievements", "").strip() or "Add achievements, hackathons, coding profiles, or awards here.",
    }


def build_resume_content(payload):
    preview = build_resume_preview(payload)
    return {
        "name": preview["name"],
        "role": preview["role"],
        "degree": preview["degree"],
        "company": preview["company"],
        "contact_items": preview["contact_items"],
        "summary": preview["summary"],
        "skills": preview["skills"],
        "projects": preview["projects"],
        "internship": split_resume_points(preview["internship"]),
        "education": split_resume_points(preview["education"]),
        "certifications": split_resume_points(preview["certifications"]),
        "achievements": split_resume_points(preview["achievements"]),
    }


def resolve_target_role(payload):
    selected_role = payload.get("targetRole", "Software Engineer").strip() or "Software Engineer"
    if selected_role == "Other":
        return payload.get("targetRoleCustom", "").strip() or "Custom Professional Role"
    return selected_role


def get_role_options():
    return list(ROLE_LIBRARY.keys()) + ["Other"]


def get_resume_theme_options():
    return RESUME_THEMES


def resolve_resume_theme(payload):
    theme_key = (payload.get("resumeTheme", "classic") or "classic").strip().lower()
    return theme_key, RESUME_THEMES.get(theme_key, RESUME_THEMES["classic"])


def infer_custom_role_skills(role):
    lowered = role.lower()
    common = ["Communication", "Projects", "Problem Solving", "Git"]
    if "ai" in lowered or "ml" in lowered:
        return ["Python", "Machine Learning", "Deep Learning", "MLOps", "SQL", "Projects"] + common
    if "data" in lowered:
        return ["Python", "SQL", "Statistics", "Dashboards", "Projects"] + common
    if "frontend" in lowered:
        return ["HTML", "CSS", "JavaScript", "React", "Responsive Design", "Projects"] + common
    if "backend" in lowered:
        return ["Python or Java", "APIs", "SQL", "System Design Basics", "Projects"] + common
    return unique_list([role, "Problem Solving", "Projects", "Communication", "Domain Knowledge", "Portfolio"])


def build_timeline_labels(duration):
    months = duration_to_months(duration)
    checkpoints = [1, max(1, months // 4), max(2, months // 2), months]
    return [format_duration_window(checkpoints[0]), format_duration_window(checkpoints[1]), format_duration_window(checkpoints[2]), format_duration_window(checkpoints[3])]


def duration_to_months(duration):
    duration = (duration or "6 months").lower()
    if "month" in duration:
        return int(duration.split()[0])
    if "year" in duration:
        return int(duration.split()[0]) * 12
    return 6


def format_duration_window(months):
    if months < 12:
        label = "Month" if months == 1 else "Months"
        return f"{label} 1-{months}"
    years = months / 12
    if years.is_integer():
        years = int(years)
    label = "Year" if years == 1 else "Years"
    return f"{label} 1-{years}"


def build_skill_sources(skills, company, role):
    normalized = company.strip().lower()
    company_info = COMPANY_SOURCE_LIBRARY.get(normalized)
    sources = []
    for skill in skills:
        if company_info:
            query = f"site:{company_info['domain']} {role} {skill}"
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            label = f"{company_info['label']} mention"
            homepage = company_info["homepage"]
        else:
            query = f"{company or 'company'} {role} {skill} careers"
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            label = "Search company source"
            homepage = None
        sources.append({"skill": skill, "url": url, "label": label, "homepage": homepage})
    return sources


def generate_resume_pdf(resume_text, payload):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    _, theme = resolve_resume_theme(payload)
    content = build_resume_content(payload)
    pdf.setTitle(f"{payload.get('studentName', 'Resume')} - ResumeSpark")
    y = draw_resume_pdf_header(pdf, width, height, theme, content)
    y = draw_resume_pdf_section(pdf, width, height, y, theme, "Professional Summary", [content["summary"]], bullet=False)
    y = draw_resume_pdf_section(pdf, width, height, y, theme, "Skills", [", ".join(content["skills"])], bullet=False)
    y = draw_resume_pdf_section(
        pdf,
        width,
        height,
        y,
        theme,
        "Projects",
        [f"{index}. {project}" for index, project in enumerate(content["projects"], start=1)],
        bullet=False,
    )
    y = draw_resume_pdf_section(pdf, width, height, y, theme, "Internship / Experience", content["internship"])
    y = draw_resume_pdf_section(pdf, width, height, y, theme, "Education", content["education"])
    y = draw_resume_pdf_section(pdf, width, height, y, theme, "Certifications", content["certifications"])
    draw_resume_pdf_section(pdf, width, height, y, theme, "Achievements", content["achievements"])
    pdf.save()
    buffer.seek(0)
    return buffer


def generate_letter_pdf(letter_text, payload):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    _, theme = resolve_resume_theme(payload)
    r, g, b = theme["pdf_rgb"]
    pdf.setFillColorRGB(r, g, b)
    pdf.rect(0, height - 92, width, 92, fill=1, stroke=0)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(42, height - 50, payload.get("studentName", "Cover Letter"))
    pdf.setFont("Helvetica", 11)
    pdf.drawString(42, height - 70, f"Cover Letter | {resolve_target_role(payload)}")

    pdf.setFillColorRGB(0.18, 0.14, 0.12)
    pdf.setFont("Helvetica", 10.5)
    y = height - 120
    for paragraph in [block.strip() for block in letter_text.split("\n\n") if block.strip()]:
        for line in wrap_pdf_line(paragraph, 90):
            if y < 70:
                pdf.showPage()
                y = height - 50
                pdf.setFont("Helvetica", 10.5)
                pdf.setFillColorRGB(0.18, 0.14, 0.12)
            pdf.drawString(42, y, line)
            y -= 14
        y -= 10
    pdf.save()
    buffer.seek(0)
    return buffer


def draw_resume_pdf_header(pdf, width, height, theme, content):
    r, g, b = theme["pdf_rgb"]
    pdf.setFillColorRGB(r, g, b)
    pdf.rect(0, height - 108, width, 108, fill=1, stroke=0)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(42, height - 52, content["name"])
    pdf.setFont("Helvetica", 11)
    pdf.drawString(42, height - 74, f"{content['role']} | {content['degree']}")
    pdf.drawRightString(width - 42, height - 52, content["company"])

    pdf.setFillColorRGB(0.18, 0.14, 0.12)
    pdf.setFont("Helvetica", 9.5)
    contact_lines = wrap_pdf_line(" | ".join(content["contact_items"]) or "Add phone, email, LinkedIn, and portfolio", 98)
    y = height - 126
    for chunk in contact_lines:
        pdf.drawString(42, y, chunk)
        y -= 12

    pdf.setStrokeColorRGB(r, g, b)
    pdf.setLineWidth(1.5)
    pdf.line(42, y - 4, width - 42, y - 4)
    return y - 24


def draw_resume_pdf_section(pdf, width, height, y, theme, title, lines, bullet=True):
    y = ensure_pdf_space(pdf, width, height, y, theme)
    r, g, b = theme["pdf_rgb"]
    pdf.setFillColorRGB(r, g, b)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(42, y, title.upper())
    y -= 18

    pdf.setFillColorRGB(0.18, 0.14, 0.12)
    pdf.setFont("Helvetica", 10.5)
    for item in normalize_pdf_lines(lines):
        wrapped = wrap_pdf_line(item, 88)
        for index, chunk in enumerate(wrapped):
            y = ensure_pdf_space(pdf, width, height, y, theme)
            if bullet and index == 0:
                pdf.drawString(45, y, "-")
                pdf.drawString(56, y, chunk)
            else:
                pdf.drawString(56 if bullet else 42, y, chunk)
            y -= 14
        y -= 6
    return y - 4


def ensure_pdf_space(pdf, width, height, y, theme):
    if y >= 72:
        return y
    pdf.showPage()
    r, g, b = theme["pdf_rgb"]
    pdf.setStrokeColorRGB(r, g, b)
    pdf.setLineWidth(2)
    pdf.line(42, height - 36, width - 42, height - 36)
    return height - 56


def normalize_pdf_lines(lines):
    normalized = []
    for line in lines:
        text = str(line).strip()
        if text:
            normalized.append(text)
    return normalized or ["Add details here."]


def wrap_pdf_line(text, limit):
    words = text.split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= limit:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def split_resume_points(text):
    if not text:
        return []
    items = [text]
    for separator in ["\n", ";", "|"]:
        expanded = []
        for item in items:
            expanded.extend(item.split(separator))
        items = expanded
    cleaned = [item.strip(" -\t") for item in items if item.strip(" -\t")]
    return cleaned or [text.strip()]


def safe_filename(name):
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_")).strip()
    return cleaned or "resume"


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
