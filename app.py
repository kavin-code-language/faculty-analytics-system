HEAD
import os
import csv
from io import StringIO
from fpdf import FPDF
from flask import Flask, render_template, request, redirect, session, make_response, flash  # type: ignore
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy  # type: ignore
from werkzeug.security import generate_password_hash, check_password_hash  # type: ignore
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect
from forms import LoginForm, AddUserForm, FeedbackForm, MarkForm, SettingsForm

# ================= APP =================
app = Flask(__name__)
app.secret_key = "super_secret_faculty_key"
csrf = CSRFProtect(app)

UPLOAD_FOLDER = 'static/uploads/profile_photos'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ================= DATABASE =================
# Ensure absolute path with forward slashes for Windows compatibility
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if not os.path.exists(os.path.join(BASE_DIR, 'instance')):
    os.makedirs(os.path.join(BASE_DIR, 'instance'))

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'faculty.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False) # admin, teacher, student
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    mobile = db.Column(db.String(20))
    year = db.Column(db.String(20)) # For students
    photo_url = db.Column(db.String(200)) # Path to profile photo
    theme = db.Column(db.String(50), default="theme-light")

    def __init__(self, username=None, password_hash=None, role=None, full_name=None, email=None, mobile=None, year=None, photo_url=None, **kwargs):
        super().__init__(**kwargs)
        if username is not None: self.username = username
        if password_hash is not None: self.password_hash = password_hash
        if role is not None: self.role = role
        if full_name is not None: self.full_name = full_name
        if email is not None: self.email = email
        if mobile is not None: self.mobile = mobile
        if year is not None: self.year = year
        if photo_url is not None: self.photo_url = photo_url
        if 'theme' in kwargs: self.theme = kwargs['theme']

# ================= HELPERS =================

def get_teacher_list():
    """Dynamically fetch teacher usernames from the User table."""
    teachers = User.query.filter_by(role="teacher").all()
    return [t.username for t in teachers]

# ================= SQL TABLE =================

class Mark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_username = db.Column(db.String(100), nullable=False)
    teacher_username = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    semester = db.Column(db.String(50), nullable=False)
    score = db.Column(db.String(20), nullable=False)
    date_added = db.Column(db.String(50))

    def __init__(self, student_username=None, teacher_username=None, subject=None, semester=None, score=None, date_added=None, **kwargs):
        super().__init__(**kwargs)
        if student_username is not None: self.student_username = student_username
        if teacher_username is not None: self.teacher_username = teacher_username
        if subject is not None: self.subject = subject
        if semester is not None: self.semester = semester
        if score is not None: self.score = score
        if date_added is not None: self.date_added = date_added

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student = db.Column(db.String(50))
    department = db.Column(db.String(50))
    teacher = db.Column(db.String(50))
    subject = db.Column(db.String(50))
    rating = db.Column(db.Integer)
    comment = db.Column(db.String(500))
    date = db.Column(db.String(50))
    is_anonymous = db.Column(db.Boolean, default=False)

    def __init__(self, student=None, department=None, teacher=None, subject=None, rating=None, comment=None, date=None, is_anonymous=False, **kwargs):
        super().__init__(**kwargs)
        if student is not None: self.student = student
        if department is not None: self.department = department
        if teacher is not None: self.teacher = teacher
        if subject is not None: self.subject = subject
        if rating is not None: self.rating = rating
        if comment is not None: self.comment = comment
        if date is not None: self.date = date
        if is_anonymous is not None: self.is_anonymous = is_anonymous

# ================================================================
# HELPERS
# ================================================================

def get_teacher_avg():
    result = {}
    all_feedbacks = Feedback.query.all()
    for t in get_teacher_list():
        rates = [float(f.rating) for f in all_feedbacks if f.teacher == t]
        result[t] = round(sum(rates) / len(rates), 2) if rates else 0.0  # type: ignore
    return result

# ================================================================
# AUTH & ROLES
# ================================================================

@app.route("/", methods=["GET", "POST"])
def login():
    if "user" in session:
        role = session.get("role")
        if role == "admin":
            return redirect("/admin")
        elif role == "teacher":
            return redirect("/dashboard")
        elif role == "student":
            return redirect("/student_dashboard")

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            session["user"] = username
            session["role"] = user.role
            session["theme"] = user.theme or "theme-light"
            
            if user.role == "admin":
                return redirect("/admin")
            elif user.role == "teacher":
                return redirect("/dashboard")
            else:
                return redirect("/student_dashboard")
        
        return render_template("login.html", error="Invalid credentials.", form=form)

    return render_template("login.html", error=None, form=form)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ================================================================
# STUDENT — PAGES
# ================================================================

@app.route("/student_dashboard")
def student_dashboard():
    if session.get("role") != "student":
        return redirect("/")

    student_name = session["user"]
    student_user = User.query.filter_by(username=student_name).first()
    marks = Mark.query.filter_by(student_username=student_name).all()

    return render_template(
        "student_dashboard.html",
        student=student_user,
        username=student_name,
        theme=session.get("theme", "theme-light"),
        marks=marks
    )

@app.route("/student_settings", methods=["GET", "POST"])
def student_settings():
    if session.get("role") != "student":
        return redirect("/")

    student = session["user"]
    student_user = User.query.filter_by(username=student).first()
    message = None
    theme = session.get("theme", "theme-light")

    if request.method == "POST":
        action = request.form.get("action")

        if action == "password":
            old_pw = request.form.get("old_password", "")
            new_pw = request.form.get("new_password", "")
            
            user = User.query.filter_by(username=student).first()
            if user and check_password_hash(user.password_hash, old_pw):
                user.password_hash = generate_password_hash(new_pw)
                db.session.commit()
                message = "Password updated successfully!"
            else:
                message = "Incorrect current password."

        elif action == "theme":
            theme            = request.form.get("theme", "theme-light")
            session["theme"] = theme
            if student_user:
                student_user.theme = theme
                db.session.commit()
            message          = "Theme saved!"

    return render_template("student_settings.html", student=student_user, username=student, message=message, theme=theme)

@app.route("/student_feedbacks")
def student_feedbacks():
    if session.get("role") != "student":
        return redirect("/")

    student_name = session["user"]
    student_user = User.query.filter_by(username=student_name).first()
    feedbacks = Feedback.query.filter_by(student=student_name).all()

    return render_template(
        "student_feedbacks.html",
        student=student_user,
        username=student_name,
        feedbacks=feedbacks,
        theme=session.get("theme", "theme-light")
    )

@app.route("/feedback")
def feedback():
    if session.get("role") != "student":
        return redirect("/")
    
    student_name = session["user"]
    student_user = User.query.filter_by(username=student_name).first()
    
    return render_template("feedback.html", 
                           teachers=get_teacher_list(), 
                           theme=session.get("theme", "theme-light"), 
                           username=student_name,
                           student=student_user)

@app.route("/submit_feedback", methods=["POST"])
def submit_feedback():
    if session.get("role") != "student":
        return redirect("/")

    form = FeedbackForm()
    if form.validate_on_submit():
        new_feedback = Feedback(
            student=session.get("user", "Unknown"),
            department=form.department.data,
            teacher=form.teacher.data,
            subject=form.subject.data,
            rating=form.rating.data,
            comment=form.comment.data,
            date=datetime.now().strftime("%d %b %Y, %I:%M %p"),
            is_anonymous=form.is_anonymous.data
        )

        db.session.add(new_feedback)
        db.session.commit()

        theme = session.get("theme", "theme-light")
        return render_template("success.html", theme=theme, feedback_id=new_feedback.id)
    return redirect("/feedback")

@app.route("/view_feedback/<int:id>")
def view_feedback(id):
    if session.get("role") != "student":
        return redirect("/")
    
    fb = Feedback.query.get(id)
    # verify ownership unless anonymous (though the student should still be able to view their own if they have the link session immediately after in theory, but let's just make sure it's somewhat restricted or assume they own it if they have the exact ID and are logged in as that student)
    if not fb or (fb.student != session.get("user", "Unknown")):
        return redirect("/")

    return render_template("view_feedback.html", fb=fb, theme=session.get("theme", "theme-light"))

# ================================================================
# TEACHER — PAGES
# ================================================================

@app.route("/dashboard")
def dashboard():
    if session.get("role") != "teacher":
        return redirect("/")

    teacher_name = session["user"]
    teacher_user = User.query.filter_by(username=teacher_name).first()
    data = Feedback.query.filter_by(teacher=teacher_name).all()
    
    ratings = [f.rating for f in data]
    # Respect anonymity in chart labels
    students = ["Anonymous" if f.is_anonymous else f.student for f in data]

    avg = round(sum(ratings) / len(ratings), 2) if ratings else 0.0  # type: ignore
    ai_score = round(avg * 20.0, 1)  # type: ignore

    # Chart.js data
    rating_distribution = [ratings.count(i) for i in range(1, 6)]

    teacher_avg = get_teacher_avg()
    sorted_teachers = sorted(teacher_avg.keys(), key=lambda t: teacher_avg[t], reverse=True)
    rank = sorted_teachers.index(teacher_name) + 1 if teacher_name in sorted_teachers else "-"

    return render_template(
        "dashboard.html",
        teacher=teacher_user,
        feedbacks=data,
        avg=avg,
        rank=rank,
        ratings=ratings,
        students=students,
        ai_score=ai_score,
        rating_distribution=rating_distribution,
        theme=session.get("theme", "theme-light")
    )

@app.route("/teacher_feedback")
def teacher_feedback_page():
    if session.get("role") != "teacher":
        return redirect("/")

    teacher = session["user"]
    data = Feedback.query.filter_by(teacher=teacher).all()

    return render_template(
        "teacher_feedback.html",
        teacher=teacher,
        feedbacks=data,
        theme=session.get("theme", "theme-light")
    )

@app.route("/teacher_marks", methods=["GET", "POST"])
def teacher_marks():
    if session.get("role") != "teacher":
        return redirect("/")

    teacher = session["user"]
    message = None
    
    form = MarkForm()
    if request.method == "POST" and form.validate_on_submit():
        student_username = form.student.data
        subject = form.subject.data
        semester = form.semester.data
        score = form.score.data
        
        new_mark = Mark(
            student_username=student_username,
            teacher_username=teacher,
            subject=subject,
            semester=semester,
            score=score,
            date_added=datetime.now().strftime("%d %b %Y, %I:%M %p")
        )
        db.session.add(new_mark)
        db.session.commit()
        message = "Mark added successfully!"
            
    # GET display data
    teacher_marks = Mark.query.filter_by(teacher_username=teacher).all()
    students = User.query.filter_by(role="student").all()
    
    return render_template(
        "teacher_marks.html",
        teacher=teacher,
        marks=teacher_marks,
        students=students,
        message=message,
        theme=session.get("theme", "theme-light")
    )

@app.route("/delete_mark/<int:id>", methods=["POST"])
def delete_mark(id):
    if session.get("role") != "teacher" and session.get("role") != "admin":
        return redirect("/")

    mark = Mark.query.get(id)
    if mark:
        # Check permissions for teacher
        if session.get("role") == "teacher" and mark.teacher_username != session.get("user"):
            return redirect("/teacher_marks")
            
        db.session.delete(mark)
        db.session.commit()

    return redirect("/teacher_marks")

@app.route("/edit_mark/<int:id>", methods=["POST"])
def edit_mark(id):
    if session.get("role") != "teacher":
        return redirect("/")

    mark = Mark.query.get(id)
    if not mark or mark.teacher_username != session.get("user"):
        return redirect("/teacher_marks")

    subject = request.form.get("subject")
    semester = request.form.get("semester")
    score = request.form.get("score")

    if subject:
        mark.subject = subject
    if semester:
        mark.semester = semester
    if score:
        mark.score = score

    db.session.commit()
    return redirect("/teacher_marks")

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if session.get("role") != "teacher":
        return redirect("/")

    teacher = session["user"]
    message = None
    theme = session.get("theme", "theme-light")

    if request.method == "POST":
        action = request.form.get("action")

        if action == "password":
            old_pw = request.form.get("old_password", "")
            new_pw = request.form.get("new_password", "")
            
            user = User.query.filter_by(username=teacher).first()
            if user and check_password_hash(user.password_hash, old_pw):
                user.password_hash = generate_password_hash(new_pw)
                db.session.commit()
                message = "Password updated successfully!"
            else:
                message = "Incorrect current password."

        elif action == "theme":
            theme            = request.form.get("theme", "theme-light")
            session["theme"] = theme
            user = User.query.filter_by(username=teacher).first()
            if user:
                user.theme = theme
                db.session.commit()
            message          = "Theme saved!"

    return render_template("settings.html", teacher=teacher, message=message, theme=theme)

# ================================================================
# ADMIN — PAGES
# ================================================================

@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect("/")

    admin_name = session.get("user")
    admin_user = User.query.filter_by(username=admin_name).first()
    all_feedbacks = Feedback.query.all()
    teacher_avg = get_teacher_avg()
    highest = max(teacher_avg, key=lambda t: teacher_avg[t]) if teacher_avg else "N/A"
    lowest = min(teacher_avg, key=lambda t: teacher_avg[t]) if teacher_avg else "N/A"
    
    ratings = [f.rating for f in all_feedbacks]
    overall_avg = round(sum(ratings) / len(ratings), 2) if ratings else 0.0  # type: ignore

    return render_template(
        "admin_dashboard.html",
        admin=admin_user,
        feedbacks=all_feedbacks,
        teacher_avg=teacher_avg,
        highest=highest,
        lowest=lowest,
        overall_avg=overall_avg,
        theme=session.get("theme", "theme-light")
    )

@app.route("/admin_users", methods=["GET"])
def admin_users_page():
    if "user" not in session or session.get("role") != "admin":
        return redirect("/")
    users = User.query.all()
    return render_template("admin_users.html", user=session["user"], current_theme=session.get("theme", "theme-light"), users=users)

@app.route("/add_user", methods=["POST"])
def add_user():
    if "user" not in session or session.get("role") != "admin":
        return redirect("/")
    
    form = AddUserForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data.strip()
        role = form.role.data.strip()
        full_name = form.full_name.data.strip()
        email = form.email.data.strip()
        mobile = form.mobile.data.strip()
        year = form.year.data.strip() if form.year.data else ""
        
        # Validation: Ensure year is present if role is student
        if role == "student" and not year:
            flash("Student year is required.", "error")
            return redirect("/admin_users")
        
        # Determine photo URL
        photo_url = "/static/uploads/profile_photos/default.png"
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                if not os.path.exists(app.config['UPLOAD_FOLDER']):
                    os.makedirs(app.config['UPLOAD_FOLDER'])
                
                filename = secure_filename(f"{username}_{file.filename}")
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                photo_url = f"/static/uploads/profile_photos/{filename}"

        if role in ["admin", "teacher", "student"]:
            existing = User.query.filter_by(username=username).first()
            if not existing:
                hashed_pw = generate_password_hash(password)
                new_user = User(
                    username=username, 
                    password_hash=hashed_pw, 
                    role=role,
                    full_name=full_name,
                    email=email,
                    mobile=mobile,
                    year=year,
                    photo_url=photo_url
                )
                db.session.add(new_user)
                db.session.commit()
                flash(f"User {username} created successfully!", "success")
            else:
                flash(f"Error: Username '{username}' already exists.", "error")
        else:
            flash("Error: Invalid role selected.", "error")
    else:
        # If form validation failed, report specific errors
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", "error")

    return redirect("/admin_users")

@app.route("/delete_user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    if "user" not in session or session.get("role") != "admin":
        return redirect("/")
    user_to_delete = User.query.get(user_id)
    if user_to_delete and user_to_delete.username != session["user"]:
        db.session.delete(user_to_delete)
        db.session.commit()
    return redirect("/admin_users")

@app.route("/admin_feedback")
def admin_feedback():
    if session.get("role") != "admin":
        return redirect("/")
    all_feedbacks = Feedback.query.all()
    return render_template("admin_feedback.html", feedbacks=all_feedbacks, theme=session.get("theme", "theme-light"))

@app.route("/admin_reports")
def admin_reports():
    if session.get("role") != "admin":
        return redirect("/")

    all_feedbacks = Feedback.query.all()
    teacher_avg = get_teacher_avg()
    total_feedback = len(all_feedbacks)
    
    ratings = [f.rating for f in all_feedbacks]
    overall_avg = round(sum(ratings) / len(ratings), 2) if ratings else 0.0  # type: ignore

    return render_template(
        "admin_reports.html",
        teacher_avg=teacher_avg,
        total_feedback=total_feedback,
        overall_avg=overall_avg,
        indexed_feedbacks=all_feedbacks,
        theme=session.get("theme", "theme-light")
    )

@app.route("/admin_settings", methods=["GET", "POST"])
def admin_settings():
    if session.get("role") != "admin":
        return redirect("/")

    admin = session["user"]
    message = None
    theme = session.get("theme", "theme-light")

    if request.method == "POST":
        action = request.form.get("action")

        if action == "password":
            old_pw = request.form.get("old_password", "")
            new_pw = request.form.get("new_password", "")
            
            user = User.query.filter_by(username=admin).first()
            if user and check_password_hash(user.password_hash, old_pw):
                user.password_hash = generate_password_hash(new_pw)
                db.session.commit()
                message = "Password updated successfully!"
            else:
                message = "Incorrect current password."

        elif action == "theme":
            theme            = request.form.get("theme", "theme-light")
            session["theme"] = theme
            user = User.query.filter_by(username=admin).first()
            if user:
                user.theme = theme
                db.session.commit()
            message          = "Theme saved!"

    return render_template("admin_settings.html", admin=admin, message=message, theme=theme)

@app.route("/delete_feedback/<int:id>", methods=["POST"])
def delete_feedback(id):
    if session.get("role") != "admin":
        return redirect("/")

    fb = Feedback.query.get(id)
    if fb:
        db.session.delete(fb)
        db.session.commit()

    return redirect("/admin_reports")

@app.route("/faculty/<name>")
def faculty_detail(name):
    if session.get("role") != "admin":
        return redirect("/")

    teacher_user = User.query.filter_by(username=name).first()
    teacher_feedbacks = Feedback.query.filter_by(teacher=name).all()
    ratings = [f.rating for f in teacher_feedbacks]

    avg = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
    high = sum(1 for r in ratings if r >= 4)
    low = sum(1 for r in ratings if r <= 2)

    comments = [{"student": "Anonymous Student" if f.is_anonymous else f.student, "comment": f.comment} for f in teacher_feedbacks]

    return render_template(
        "faculty_detail.html",
        name=name,
        teacher=teacher_user,
        avg=avg,
        high=high,
        low=low,
        comments=comments,
        theme=session.get("theme", "theme-light")
    )

@app.route("/user_profile/<username>")
def user_profile(username):
    if "user" not in session:
        return redirect("/")
    
    user = User.query.filter_by(username=username).first()
    theme = session.get("theme", "theme-light")

    if not user:
        # Instead of redirecting to login, show a friendly error template
        return render_template("user_not_found.html", username=username, theme=theme)
    
    marks = Mark.query.filter_by(student_username=username).all() if user.role == 'student' else []
    
    return render_template("user_profile.html", profile_user=user, theme=theme, marks=marks)

@app.route("/export_csv")
def export_csv():
    if session.get("role") != "admin":
        return redirect("/")

    feedbacks = Feedback.query.all()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["ID", "Student", "Department", "Teacher", "Subject", "Rating", "Comment", "Date", "Is Anonymous"])
    
    for f in feedbacks:
        cw.writerow([
            f.id,
            "Anonymous" if f.is_anonymous else f.student,
            f.department,
            f.teacher,
            f.subject,
            f.rating,
            f.comment.replace('\n', ' ').replace('\r', ''),
            f.date,
            "Yes" if f.is_anonymous else "No"
        ])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=faculty_analytics_report.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route("/export_pdf")
def export_pdf():
    if session.get("role") != "admin":
        return redirect("/")

    feedbacks = Feedback.query.all()
    
    pdf = FPDF()
    pdf.add_page(orientation='L')
    pdf.set_font("Arial", size=10)
    
    pdf.set_font("Arial", style='B', size=16)
    pdf.cell(0, 10, "Faculty Analytics - Institutional Report", ln=1, align='C')
    pdf.ln(5)
    
    pdf.set_font("Arial", style='B', size=9)
    # 277 total width roughly in Landscape
    col_widths = [10, 35, 30, 30, 45, 15, 80, 25]  # Adjusted to fit A4 Landscape
    headers = ["ID", "Student", "Dept", "Faculty", "Subject", "Rate", "Comment Snippet", "Date"]
    
    for i in range(len(headers)):
        pdf.cell(col_widths[i], 8, headers[i], border=1, align='C')
    pdf.ln()
    
    pdf.set_font("Arial", size=8)
    for f in feedbacks:
        student_name = "Anonymous" if f.is_anonymous else f.student
        
        # safely truncate strings if too long
        student_name = student_name[:15] + ".." if len(student_name) > 17 else student_name  # type: ignore
        dept = (f.department or "")[:12]  # type: ignore
        teach = (f.teacher or "")[:12]  # type: ignore
        subj = (f.subject or "")[:20]  # type: ignore
        date_str = (f.date or "").split(',')[0]  # type: ignore
        comment = (f.comment or "").replace('\n', ' ').replace('\r', '')
        comment = comment[:50] + ".." if len(comment) > 52 else comment  # type: ignore

        pdf.cell(col_widths[0], 8, str(f.id), border=1, align='C')
        pdf.cell(col_widths[1], 8, str(student_name), border=1)
        pdf.cell(col_widths[2], 8, str(dept), border=1)
        pdf.cell(col_widths[3], 8, str(teach), border=1)
        pdf.cell(col_widths[4], 8, str(subj), border=1)
        pdf.cell(col_widths[5], 8, str(f.rating), border=1, align='C')
        pdf.cell(col_widths[6], 8, str(comment), border=1)
        pdf.cell(col_widths[7], 8, str(date_str), border=1, align='C')
        pdf.ln()

    # encode and return
    response = make_response(pdf.output(dest='S').encode('latin-1'))
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=faculty_analytics_report.pdf'
    return response

# ================================================================
# CREATE DATABASE
# ================================================================

with app.app_context():
    db.create_all()
    # Create default admin if DB is newly created and empty
    if not User.query.filter_by(username="admin").first():
        hashed = generate_password_hash("admin123")
        admin_user = User(username="admin", password_hash=hashed, role="admin")
        db.session.add(admin_user)
        db.session.commit()
        print("Default admin created: admin / admin123")

# ================================================================
# RUN
# ================================================================

if __name__ == "__main__":
=======
import os
import csv
from io import StringIO
from fpdf import FPDF
from flask import Flask, render_template, request, redirect, session, make_response  # type: ignore
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy  # type: ignore
from werkzeug.security import generate_password_hash, check_password_hash  # type: ignore
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect
from forms import LoginForm, AddUserForm, FeedbackForm, MarkForm, SettingsForm

# ================= APP =================
app = Flask(__name__)
app.secret_key = "super_secret_faculty_key"
csrf = CSRFProtect(app)

UPLOAD_FOLDER = 'static/uploads/profile_photos'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ================= DATABASE =================
# Ensure absolute path with forward slashes for Windows compatibility
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if not os.path.exists(os.path.join(BASE_DIR, 'instance')):
    os.makedirs(os.path.join(BASE_DIR, 'instance'))

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'faculty.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False) # admin, teacher, student
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    mobile = db.Column(db.String(20))
    year = db.Column(db.String(20)) # For students
    photo_url = db.Column(db.String(200)) # Path to profile photo

    def __init__(self, username=None, password_hash=None, role=None, full_name=None, email=None, mobile=None, year=None, photo_url=None, **kwargs):
        super().__init__(**kwargs)
        if username is not None: self.username = username
        if password_hash is not None: self.password_hash = password_hash
        if role is not None: self.role = role
        if full_name is not None: self.full_name = full_name
        if email is not None: self.email = email
        if mobile is not None: self.mobile = mobile
        if year is not None: self.year = year
        if photo_url is not None: self.photo_url = photo_url

# ================= HELPERS =================

def get_teacher_list():
    """Dynamically fetch teacher usernames from the User table."""
    teachers = User.query.filter_by(role="teacher").all()
    return [t.username for t in teachers]

# ================= SQL TABLE =================

class Mark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_username = db.Column(db.String(100), nullable=False)
    teacher_username = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    semester = db.Column(db.String(50), nullable=False)
    score = db.Column(db.String(20), nullable=False)
    date_added = db.Column(db.String(50))

    def __init__(self, student_username=None, teacher_username=None, subject=None, semester=None, score=None, date_added=None, **kwargs):
        super().__init__(**kwargs)
        if student_username is not None: self.student_username = student_username
        if teacher_username is not None: self.teacher_username = teacher_username
        if subject is not None: self.subject = subject
        if semester is not None: self.semester = semester
        if score is not None: self.score = score
        if date_added is not None: self.date_added = date_added

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student = db.Column(db.String(50))
    department = db.Column(db.String(50))
    teacher = db.Column(db.String(50))
    subject = db.Column(db.String(50))
    rating = db.Column(db.Integer)
    comment = db.Column(db.String(500))
    date = db.Column(db.String(50))
    is_anonymous = db.Column(db.Boolean, default=False)

    def __init__(self, student=None, department=None, teacher=None, subject=None, rating=None, comment=None, date=None, is_anonymous=False, **kwargs):
        super().__init__(**kwargs)
        if student is not None: self.student = student
        if department is not None: self.department = department
        if teacher is not None: self.teacher = teacher
        if subject is not None: self.subject = subject
        if rating is not None: self.rating = rating
        if comment is not None: self.comment = comment
        if date is not None: self.date = date
        if is_anonymous is not None: self.is_anonymous = is_anonymous

# ================================================================
# HELPERS
# ================================================================

def get_teacher_avg():
    result = {}
    all_feedbacks = Feedback.query.all()
    for t in get_teacher_list():
        rates = [float(f.rating) for f in all_feedbacks if f.teacher == t]
        result[t] = round(sum(rates) / len(rates), 2) if rates else 0.0  # type: ignore
    return result

# ================================================================
# AUTH & ROLES
# ================================================================

@app.route("/", methods=["GET", "POST"])
def login():
    if "user" in session:
        role = session.get("role")
        if role == "admin":
            return redirect("/admin")
        elif role == "teacher":
            return redirect("/dashboard")
        elif role == "student":
            return redirect("/student_dashboard")

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            session["user"] = username
            session["role"] = user.role
            session["theme"] = "theme-light"  # Default Professional Light for all
            
            if user.role == "admin":
                return redirect("/admin")
            elif user.role == "teacher":
                return redirect("/dashboard")
            else:
                return redirect("/student_dashboard")
        
        return render_template("login.html", error="Invalid credentials.", form=form)

    return render_template("login.html", error=None, form=form)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ================================================================
# STUDENT — PAGES
# ================================================================

@app.route("/student_dashboard")
def student_dashboard():
    if session.get("role") != "student":
        return redirect("/")

    student_name = session["user"]
    student_user = User.query.filter_by(username=student_name).first()
    marks = Mark.query.filter_by(student_username=student_name).all()

    return render_template(
        "student_dashboard.html",
        student=student_user,
        username=student_name,
        theme=session.get("theme", "theme-light"),
        marks=marks
    )

@app.route("/student_settings", methods=["GET", "POST"])
def student_settings():
    if session.get("role") != "student":
        return redirect("/")

    student = session["user"]
    student_user = User.query.filter_by(username=student).first()
    message = None
    theme = session.get("theme", "theme-light")

    if request.method == "POST":
        action = request.form.get("action")

        if action == "password":
            old_pw = request.form.get("old_password", "")
            new_pw = request.form.get("new_password", "")
            
            user = User.query.filter_by(username=student).first()
            if user and check_password_hash(user.password_hash, old_pw):
                user.password_hash = generate_password_hash(new_pw)
                db.session.commit()
                message = "Password updated successfully!"
            else:
                message = "Incorrect current password."

        elif action == "theme":
            theme            = request.form.get("theme", "theme-light")
            session["theme"] = theme
            message          = "Theme saved!"

    return render_template("student_settings.html", student=student_user, username=student, message=message, theme=theme)

@app.route("/student_feedbacks")
def student_feedbacks():
    if session.get("role") != "student":
        return redirect("/")

    student_name = session["user"]
    student_user = User.query.filter_by(username=student_name).first()
    feedbacks = Feedback.query.filter_by(student=student_name).all()

    return render_template(
        "student_feedbacks.html",
        student=student_user,
        username=student_name,
        feedbacks=feedbacks,
        theme=session.get("theme", "theme-light")
    )

@app.route("/feedback")
def feedback():
    if session.get("role") != "student":
        return redirect("/")
    
    student_name = session["user"]
    student_user = User.query.filter_by(username=student_name).first()
    
    return render_template("feedback.html", 
                           teachers=get_teacher_list(), 
                           theme=session.get("theme", "theme-light"), 
                           username=student_name,
                           student=student_user)

@app.route("/submit_feedback", methods=["POST"])
def submit_feedback():
    if session.get("role") != "student":
        return redirect("/")

    form = FeedbackForm()
    if form.validate_on_submit():
        new_feedback = Feedback(
            student=session.get("user", "Unknown"),
            department=form.department.data,
            teacher=form.teacher.data,
            subject=form.subject.data,
            rating=form.rating.data,
            comment=form.comment.data,
            date=datetime.now().strftime("%d %b %Y, %I:%M %p"),
            is_anonymous=form.is_anonymous.data
        )

        db.session.add(new_feedback)
        db.session.commit()

        theme = session.get("theme", "theme-light")
        return render_template("success.html", theme=theme, feedback_id=new_feedback.id)
    return redirect("/feedback")

    theme = session.get("theme", "theme-light")
    return render_template("success.html", theme=theme, feedback_id=new_feedback.id)

@app.route("/view_feedback/<int:id>")
def view_feedback(id):
    if session.get("role") != "student":
        return redirect("/")
    
    fb = Feedback.query.get(id)
    # verify ownership unless anonymous (though the student should still be able to view their own if they have the link session immediately after in theory, but let's just make sure it's somewhat restricted or assume they own it if they have the exact ID and are logged in as that student)
    if not fb or (fb.student != session.get("user", "Unknown")):
        return redirect("/")

    return render_template("view_feedback.html", fb=fb, theme=session.get("theme", "theme-light"))

# ================================================================
# TEACHER — PAGES
# ================================================================

@app.route("/dashboard")
def dashboard():
    if session.get("role") != "teacher":
        return redirect("/")

    teacher_name = session["user"]
    teacher_user = User.query.filter_by(username=teacher_name).first()
    data = Feedback.query.filter_by(teacher=teacher_name).all()
    
    ratings = [f.rating for f in data]
    students = [f.student for f in data]

    avg = round(sum(ratings) / len(ratings), 2) if ratings else 0.0  # type: ignore
    ai_score = round(avg * 20.0, 1)  # type: ignore

    # Chart.js data
    rating_distribution = [ratings.count(i) for i in range(1, 6)]

    teacher_avg = get_teacher_avg()
    sorted_teachers = sorted(teacher_avg.keys(), key=lambda t: teacher_avg[t], reverse=True)
    rank = sorted_teachers.index(teacher_name) + 1 if teacher_name in sorted_teachers else "-"

    return render_template(
        "dashboard.html",
        teacher=teacher_user,
        feedbacks=data,
        avg=avg,
        rank=rank,
        ratings=ratings,
        students=students,
        ai_score=ai_score,
        rating_distribution=rating_distribution,
        theme=session.get("theme", "theme-light")
    )

@app.route("/teacher_feedback")
def teacher_feedback_page():
    if session.get("role") != "teacher":
        return redirect("/")

    teacher = session["user"]
    data = Feedback.query.filter_by(teacher=teacher).all()

    return render_template(
        "teacher_feedback.html",
        teacher=teacher,
        feedbacks=data,
        theme=session.get("theme", "theme-light")
    )

@app.route("/teacher_marks", methods=["GET", "POST"])
def teacher_marks():
    if session.get("role") != "teacher":
        return redirect("/")

    teacher = session["user"]
    message = None
    
    form = MarkForm()
    if request.method == "POST" and form.validate_on_submit():
        student_username = form.student.data
        subject = form.subject.data
        semester = form.semester.data
        score = form.score.data
        
        new_mark = Mark(
            student_username=student_username,
            teacher_username=teacher,
            subject=subject,
            semester=semester,
            score=score,
            date_added=datetime.now().strftime("%d %b %Y, %I:%M %p")
        )
        db.session.add(new_mark)
        db.session.commit()
        message = "Mark added successfully!"
            
    # GET display data
    teacher_marks = Mark.query.filter_by(teacher_username=teacher).all()
    students = User.query.filter_by(role="student").all()
    
    return render_template(
        "teacher_marks.html",
        teacher=teacher,
        marks=teacher_marks,
        students=students,
        message=message,
        theme=session.get("theme", "theme-light")
    )

@app.route("/delete_mark/<int:id>", methods=["POST"])
def delete_mark(id):
    if session.get("role") != "teacher" and session.get("role") != "admin":
        return redirect("/")

    mark = Mark.query.get(id)
    if mark:
        # Check permissions for teacher
        if session.get("role") == "teacher" and mark.teacher_username != session.get("user"):
            return redirect("/teacher_marks")
            
        db.session.delete(mark)
        db.session.commit()

    return redirect("/teacher_marks")

@app.route("/edit_mark/<int:id>", methods=["POST"])
def edit_mark(id):
    if session.get("role") != "teacher":
        return redirect("/")

    mark = Mark.query.get(id)
    if not mark or mark.teacher_username != session.get("user"):
        return redirect("/teacher_marks")

    subject = request.form.get("subject")
    semester = request.form.get("semester")
    score = request.form.get("score")

    if subject:
        mark.subject = subject
    if semester:
        mark.semester = semester
    if score:
        mark.score = score

    db.session.commit()
    return redirect("/teacher_marks")

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if session.get("role") != "teacher":
        return redirect("/")

    teacher = session["user"]
    message = None
    theme = session.get("theme", "theme-light")

    if request.method == "POST":
        action = request.form.get("action")

        if action == "password":
            old_pw = request.form.get("old_password", "")
            new_pw = request.form.get("new_password", "")
            
            user = User.query.filter_by(username=teacher).first()
            if user and check_password_hash(user.password_hash, old_pw):
                user.password_hash = generate_password_hash(new_pw)
                db.session.commit()
                message = "Password updated successfully!"
            else:
                message = "Incorrect current password."

        elif action == "theme":
            theme            = request.form.get("theme", "theme-light")
            session["theme"] = theme
            message          = "Theme saved!"

    return render_template("settings.html", teacher=teacher, message=message, theme=theme)

# ================================================================
# ADMIN — PAGES
# ================================================================

@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect("/")

    admin_name = session.get("user")
    admin_user = User.query.filter_by(username=admin_name).first()
    all_feedbacks = Feedback.query.all()
    teacher_avg = get_teacher_avg()
    highest = max(teacher_avg, key=lambda t: teacher_avg[t]) if teacher_avg else "N/A"
    lowest = min(teacher_avg, key=lambda t: teacher_avg[t]) if teacher_avg else "N/A"
    
    ratings = [f.rating for f in all_feedbacks]
    overall_avg = round(sum(ratings) / len(ratings), 2) if ratings else 0.0  # type: ignore

    return render_template(
        "admin_dashboard.html",
        admin=admin_user,
        feedbacks=all_feedbacks,
        teacher_avg=teacher_avg,
        highest=highest,
        lowest=lowest,
        overall_avg=overall_avg,
        theme=session.get("theme", "theme-light")
    )

@app.route("/admin_users", methods=["GET"])
def admin_users_page():
    if "user" not in session or session.get("role") != "admin":
        return redirect("/")
    users = User.query.all()
    return render_template("admin_users.html", user=session["user"], current_theme=session.get("theme", "theme-light"), users=users)

@app.route("/add_user", methods=["POST"])
def add_user():
    if "user" not in session or session.get("role") != "admin":
        return redirect("/")
    
    form = AddUserForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data.strip()
        role = form.role.data.strip()
        full_name = form.full_name.data.strip()
        email = form.email.data.strip()
        mobile = form.mobile.data.strip()
        year = form.year.data.strip() if form.year.data else ""
        
        # Validation: Ensure year is present if role is student
        if role == "student" and not year:
            return redirect("/admin_users")
        
        # Validation: Ensure photo is uploaded
        if 'photo' not in request.files:
            return redirect("/admin_users")
        
        file = request.files['photo']
        if not (file and file.filename != '' and allowed_file(file.filename)):
            return redirect("/admin_users")

        if role in ["admin", "teacher", "student"]:
            existing = User.query.filter_by(username=username).first()
            if not existing:
                hashed_pw = generate_password_hash(password)
                
                # Save the photofile
                filename = secure_filename(f"{username}_{file.filename}")
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                photo_url = f"/static/uploads/profile_photos/{filename}"
                
                new_user = User(
                    username=username, 
                    password_hash=hashed_pw, 
                    role=role,
                    full_name=full_name,
                    email=email,
                    mobile=mobile,
                    year=year,
                    photo_url=photo_url
                )
                db.session.add(new_user)
                db.session.commit()
    return redirect("/admin_users")

@app.route("/delete_user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    if "user" not in session or session.get("role") != "admin":
        return redirect("/")
    user_to_delete = User.query.get(user_id)
    if user_to_delete and user_to_delete.username != session["user"]:
        db.session.delete(user_to_delete)
        db.session.commit()
    return redirect("/admin_users")

@app.route("/admin_feedback")
def admin_feedback():
    if session.get("role") != "admin":
        return redirect("/")
    all_feedbacks = Feedback.query.all()
    return render_template("admin_feedback.html", feedbacks=all_feedbacks, theme=session.get("theme", "theme-light"))

@app.route("/admin_reports")
def admin_reports():
    if session.get("role") != "admin":
        return redirect("/")

    all_feedbacks = Feedback.query.all()
    teacher_avg = get_teacher_avg()
    total_feedback = len(all_feedbacks)
    
    ratings = [f.rating for f in all_feedbacks]
    overall_avg = round(sum(ratings) / len(ratings), 2) if ratings else 0.0  # type: ignore

    return render_template(
        "admin_reports.html",
        teacher_avg=teacher_avg,
        total_feedback=total_feedback,
        overall_avg=overall_avg,
        indexed_feedbacks=all_feedbacks,
        theme=session.get("theme", "theme-light")
    )

@app.route("/admin_settings", methods=["GET", "POST"])
def admin_settings():
    if session.get("role") != "admin":
        return redirect("/")

    admin = session["user"]
    message = None
    theme = session.get("theme", "theme-light")

    if request.method == "POST":
        action = request.form.get("action")

        if action == "password":
            old_pw = request.form.get("old_password", "")
            new_pw = request.form.get("new_password", "")
            
            user = User.query.filter_by(username=admin).first()
            if user and check_password_hash(user.password_hash, old_pw):
                user.password_hash = generate_password_hash(new_pw)
                db.session.commit()
                message = "Password updated successfully!"
            else:
                message = "Incorrect current password."

        elif action == "theme":
            theme            = request.form.get("theme", "theme-light")
            session["theme"] = theme
            message          = "Theme saved!"

    return render_template("admin_settings.html", admin=admin, message=message, theme=theme)

@app.route("/delete_feedback/<int:id>", methods=["POST"])
def delete_feedback(id):
    if session.get("role") != "admin":
        return redirect("/")

    fb = Feedback.query.get(id)
    if fb:
        db.session.delete(fb)
        db.session.commit()

    return redirect("/admin_reports")

@app.route("/faculty/<name>")
def faculty_detail(name):
    if session.get("role") != "admin":
        return redirect("/")

    teacher_user = User.query.filter_by(username=name).first()
    teacher_feedbacks = Feedback.query.filter_by(teacher=name).all()
    ratings = [f.rating for f in teacher_feedbacks]

    avg = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
    high = sum(1 for r in ratings if r >= 4)
    low = sum(1 for r in ratings if r <= 2)

    comments = [{"student": "Anonymous Student" if f.is_anonymous else f.student, "comment": f.comment} for f in teacher_feedbacks]

    return render_template(
        "faculty_detail.html",
        name=name,
        teacher=teacher_user,
        avg=avg,
        high=high,
        low=low,
        comments=comments,
        theme=session.get("theme", "theme-light")
    )

@app.route("/user_profile/<username>")
def user_profile(username):
    if "user" not in session:
        return redirect("/")
    
    user = User.query.filter_by(username=username).first()
    theme = session.get("theme", "theme-light")

    if not user:
        # Instead of redirecting to login, show a friendly error template
        return render_template("user_not_found.html", username=username, theme=theme)
    
    marks = Mark.query.filter_by(student_username=username).all() if user.role == 'student' else []
    
    return render_template("user_profile.html", profile_user=user, theme=theme, marks=marks)

@app.route("/export_csv")
def export_csv():
    if session.get("role") != "admin":
        return redirect("/")

    feedbacks = Feedback.query.all()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["ID", "Student", "Department", "Teacher", "Subject", "Rating", "Comment", "Date", "Is Anonymous"])
    
    for f in feedbacks:
        cw.writerow([
            f.id,
            "Anonymous" if f.is_anonymous else f.student,
            f.department,
            f.teacher,
            f.subject,
            f.rating,
            f.comment.replace('\n', ' ').replace('\r', ''),
            f.date,
            "Yes" if f.is_anonymous else "No"
        ])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=faculty_analytics_report.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route("/export_pdf")
def export_pdf():
    if session.get("role") != "admin":
        return redirect("/")

    feedbacks = Feedback.query.all()
    
    pdf = FPDF()
    pdf.add_page(orientation='L')
    pdf.set_font("Arial", size=10)
    
    pdf.set_font("Arial", style='B', size=16)
    pdf.cell(0, 10, "Faculty Analytics - Institutional Report", ln=1, align='C')
    pdf.ln(5)
    
    pdf.set_font("Arial", style='B', size=9)
    # 277 total width roughly in Landscape
    col_widths = [10, 35, 30, 30, 45, 15, 80, 25]  # Adjusted to fit A4 Landscape
    headers = ["ID", "Student", "Dept", "Faculty", "Subject", "Rate", "Comment Snippet", "Date"]
    
    for i in range(len(headers)):
        pdf.cell(col_widths[i], 8, headers[i], border=1, align='C')
    pdf.ln()
    
    pdf.set_font("Arial", size=8)
    for f in feedbacks:
        student_name = "Anonymous" if f.is_anonymous else f.student
        
        # safely truncate strings if too long
        student_name = student_name[:15] + ".." if len(student_name) > 17 else student_name  # type: ignore
        dept = (f.department or "")[:12]  # type: ignore
        teach = (f.teacher or "")[:12]  # type: ignore
        subj = (f.subject or "")[:20]  # type: ignore
        date_str = (f.date or "").split(',')[0]  # type: ignore
        comment = (f.comment or "").replace('\n', ' ').replace('\r', '')
        comment = comment[:50] + ".." if len(comment) > 52 else comment  # type: ignore

        pdf.cell(col_widths[0], 8, str(f.id), border=1, align='C')
        pdf.cell(col_widths[1], 8, str(student_name), border=1)
        pdf.cell(col_widths[2], 8, str(dept), border=1)
        pdf.cell(col_widths[3], 8, str(teach), border=1)
        pdf.cell(col_widths[4], 8, str(subj), border=1)
        pdf.cell(col_widths[5], 8, str(f.rating), border=1, align='C')
        pdf.cell(col_widths[6], 8, str(comment), border=1)
        pdf.cell(col_widths[7], 8, str(date_str), border=1, align='C')
        pdf.ln()

    # encode and return
    response = make_response(pdf.output(dest='S').encode('latin-1'))
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=faculty_analytics_report.pdf'
    return response

# ================================================================
# CREATE DATABASE
# ================================================================

with app.app_context():
    db.create_all()
    # Create default admin if DB is newly created and empty
    if not User.query.filter_by(username="admin").first():
        hashed = generate_password_hash("admin123")
        admin_user = User(username="admin", password_hash=hashed, role="admin")
        db.session.add(admin_user)
        db.session.commit()
        print("Default admin created: admin / admin123")

# ================================================================
# RUN
# ================================================================

if __name__ == "__main__": 
    app.run(debug=True)