import json
import os
import re
from functools import wraps
from io import BytesIO
import secrets

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, Response, session, send_file
)
from werkzeug.security import generate_password_hash, check_password_hash

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

app = Flask(__name__)
app.secret_key = 'your-super-secret-key-change-this-in-production'

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

STUDENTS_FILE = os.path.join(DATA_DIR, "students.json")
COURSES_FILE = os.path.join(DATA_DIR, "courses.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
UNITS_FILE = os.path.join(DATA_DIR, "units.json")
MARKS_FILE = os.path.join(DATA_DIR, "marks.json")


# ---------- Validation ----------
def validate_reg_no(reg_no):
    if not reg_no or not reg_no.strip():
        return False, "Registration number is required."
    if not re.match(r'^(?=.*[A-Za-z])[A-Za-z0-9/._-]+$', reg_no):
        return False, "Registration number must contain at least one letter (cannot be only numbers)."
    return True, ""


def validate_name(name):
    if not name or not name.strip():
        return False, "Name is required."
    if len(name) > 30:
        return False, "Name is too long (max 30 characters)."
    if not re.match(r'^[A-Za-z\s\-\.]+$', name):
        return False, "Name can only contain letters, spaces, hyphens, and dots."
    return True, ""


def validate_course_code(code):
    if not code or not code.strip():
        return False, "Course code is required."
    if len(code) > 20:
        return False, "Course code too long (max 20 characters)."
    if not re.match(r'^[A-Z0-9\-]+$', code):  # FIXED: Only uppercase, numbers, hyphens
        return False, "Course code can only contain uppercase letters, numbers, and hyphens."
    return True, ""


def validate_unit(unit):
    if not unit or not unit.strip():
        return False, "Unit name is required."
    if len(unit) > 30:
        return False, "Unit name too long (max 30 characters)."
    if not re.match(r'^[A-Za-z0-9\s\-_]+$', unit):
        return False, "Unit name contains invalid characters."
    return True, ""


def validate_course_name(name):
    if not name or not name.strip():
        return False, "Course name is required."
    if len(name) > 30:
        return False, "Course name too long (max 30 characters)."
    # FIXED: Allow spaces, hyphens, underscores, and apostrophes for course names
    if not re.match(r'^[A-Za-z\s\-_\'\.]+$', name):
        return False, "Course name contains invalid characters."
    return True, ""


def validate_lecturer_name(name):
    if not name or not name.strip():
        return False, "Full name is required."
    if len(name) > 20:
        return False, "Full name must be 20 characters or less."
    if not re.match(r'^[A-Za-z\s]+$', name):
        return False, "Full name can only contain letters and spaces."
    return True, ""


def load_json(filepath, default=None):
    if default is None:
        default = {}
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return default


def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)


# ---------- User management ----------
def load_users():
    return load_json(USERS_FILE)


def save_users(users):
    save_json(USERS_FILE, users)


def get_user(username):
    users = load_users()
    return users.get(username)


def create_user(username, password, role, full_name=None):
    users = load_users()
    if username in users:
        return False, "Username already exists."
    user_data = {
        "password_hash": generate_password_hash(password),
        "role": role
    }
    if full_name:
        user_data["full_name"] = full_name
    users[username] = user_data
    save_users(users)
    return True, "User created."


def authenticate(username, password):
    user = get_user(username)
    if user and check_password_hash(user["password_hash"], password):
        return user["role"]
    return None


# ---------- Course management ----------
def load_courses():
    return load_json(COURSES_FILE, {})


def save_courses(courses):
    save_json(COURSES_FILE, courses)


# ---------- Student System ----------
class StudentSystem:
    def __init__(self):
        self.students = load_json(STUDENTS_FILE, {})
        self.courses = load_courses()
        self.units = load_json(UNITS_FILE, {})
        self.marks = load_json(MARKS_FILE, {})

    def save_students(self):
        save_json(STUDENTS_FILE, self.students)

    def save_courses(self):
        save_json(COURSES_FILE, self.courses)

    def save_units(self):
        save_json(UNITS_FILE, self.units)

    def save_marks(self):
        save_json(MARKS_FILE, self.marks)

    # ---------- Course operations ----------
    def add_course(self, code, name):
        valid, msg = validate_course_code(code)
        if not valid:
            return False, msg
        valid, msg = validate_course_name(name)
        if not valid:
            return False, msg
        if code in self.courses:
            return False, f"Course '{code}' already exists."
        self.courses[code] = {"name": name}
        self.save_courses()
        return True, f"Course '{code}' added."

    def remove_course(self, code):
        if code not in self.courses:
            return False, "Course not found."
        del self.courses[code]
        self.save_courses()
        return True, f"Course '{code}' removed."

    def get_course_list(self):
        return list(self.courses.items())

    # ------Unit Operations-----
    def add_unit(self, code, name):
        valid, msg = validate_unit(code)
        if not valid:
            return False, msg
        valid, msg = validate_name(name)
        if not valid:
            return False, msg

        if code in self.units:
            return False, f"Unit '{code}' already exists."

        self.units[code] = {"name": name}
        self.save_units()
        return True, f"Unit '{code}' added."

    def remove_unit(self, code):
        if code not in self.units:
            return False, "Unit not found."
        del self.units[code]
        self.save_units()
        return True, f"Unit '{code}' removed."

    def get_units_list(self):
        return list(self.units.items())

    # ---------- Student operations ----------
    def add_student(self, reg_no, name, course, password):
        valid, msg = validate_reg_no(reg_no)
        if not valid:
            return False, msg
        valid, msg = validate_name(name)
        if not valid:
            return False, msg
        valid, msg = validate_course_code(course)
        if not valid:
            return False, msg

        if reg_no in self.students:
            return False, "Student already exists."
        if course not in self.courses:
            return False, f"Course '{course}' does not exist. Please add it first."

        self.students[reg_no] = {"name": name, "course": course}
        self.save_students()

        success, msg = create_user(reg_no, password, 'student')
        if not success:
            del self.students[reg_no]
            self.save_students()
            return False, f"Student added but user creation failed: {msg}"

        return True, f"Student {name} added. Login: {reg_no} / password: {password}"

    def remove_student(self, reg_no):
        if reg_no not in self.students:
            return False, "Student not found."
        name = self.students[reg_no]["name"]
        del self.students[reg_no]
        self.save_students()

        users = load_users()
        if reg_no in users:
            del users[reg_no]
            save_users(users)

        # Remove marks for this student
        if reg_no in self.marks:
            del self.marks[reg_no]
            self.save_marks()

        return True, f"Student {name} removed (user account also deleted)."

    # ---------- Mark operations ----------
    def add_mark(self, reg_no, unit, marks):
        if reg_no not in self.students:
            return False, "Student not found."

        try:
            marks = float(marks)
        except ValueError:
            return False, "Invalid marks. Please enter a number."

        if unit not in self.units:
            return False, f"Unit '{unit}' does not exist. Please ask the Admin to add it first."

        if not marks.is_integer():
            return False, "Marks must be a whole number (no decimals)."

        marks = int(marks)
        if marks < 0 or marks > 100:
            return False, "Marks must be between 0 and 100."

        # Initialize student marks if not exists
        if reg_no not in self.marks:
            self.marks[reg_no] = {}

        self.marks[reg_no][unit] = marks
        self.save_marks()
        return True, f"Marks for '{unit}' added."

    def get_student_marks(self, reg_no):
        """Get all marks for a student"""
        if reg_no in self.marks:
            return self.marks[reg_no]
        return {}

    def calculate_gpa(self, reg_no):
        """Calculate GPA for a student"""
        if reg_no in self.marks:
            marks = self.marks[reg_no]
            if not marks:
                return 0.0
            avg = sum(marks.values()) / len(marks)
            gpa = (avg / 100) * 4.0
            return round(gpa, 2)
        return 0.0

    def search_student(self, reg_no):
        if reg_no in self.students:
            s = self.students[reg_no]
            gpa = self.calculate_gpa(reg_no)
            marks = self.get_student_marks(reg_no)
            return {
                "reg_no": reg_no,
                "name": s["name"],
                "course": s["course"],
                "marks": marks,
                "gpa": gpa
            }
        return None

    def display_gpa(self, reg_no):
        if reg_no in self.students:
            gpa = self.calculate_gpa(reg_no)
            name = self.students[reg_no]["name"]
            return True, f"GPA for {name} is {gpa:.2f}"
        return False, "Student not found."

    def download_result(self, reg_no=None):
        if reg_no is None:
            lines = []
            for reg, data in self.students.items():
                gpa = self.calculate_gpa(reg)
                lines.append(
                    f"Reg: {reg} | Name: {data['name']} | "
                    f"Course: {data['course']} | GPA: {gpa:.2f}"
                )
            content = "\n".join(lines) if lines else "No students registered."
            filename = "all_students_results.txt"
        else:
            if reg_no not in self.students:
                return None, None
            s = self.students[reg_no]
            gpa = self.calculate_gpa(reg_no)
            marks = self.get_student_marks(reg_no)
            content = (
                f"Reg No: {reg_no}\n"
                f"Name: {s['name']}\n"
                f"Course: {s['course']}\n"
                f"Marks: {marks}\n"
                f"GPA: {gpa:.2f}"
            )
            filename = f"student_{reg_no.replace('/', '_')}_result.txt"
        return content, filename

    def generate_student_pdf(self, reg_no):
        if reg_no not in self.students:
            return None
        data = self.students[reg_no]
        gpa = self.calculate_gpa(reg_no)
        marks = self.get_student_marks(reg_no)

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'],
                                     alignment=1, spaceAfter=12)
        story.append(Paragraph("Student Result Report", title_style))
        story.append(Spacer(1, 0.25 * inch))

        info = [
            ["Registration No.", reg_no],
            ["Name", data['name']],
            ["Course", data['course']],
            ["Marks", ", ".join(f"{u}: {m}" for u, m in marks.items()) if marks else "No marks"],
            ["GPA", f"{gpa:.2f}"]
        ]
        table = Table(info, colWidths=[2 * inch, 3 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.25 * inch))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    def generate_all_students_pdf(self):
        if not self.students:
            return None
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("All Students Results", styles['Heading1']))
        story.append(Spacer(1, 0.25 * inch))

        data = [["Reg No", "Name", "Course", "GPA"]]
        for reg, info in self.students.items():
            gpa = self.calculate_gpa(reg)
            data.append([reg, info['name'], info['course'], f"{gpa:.2f}"])

        table = Table(data, colWidths=[1.5 * inch, 2 * inch, 1.5 * inch, 1 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (3, 0), (3, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(table)

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()


system = StudentSystem()


# ---------- Role-based decorator ----------
def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'username' not in session:
                flash('Please log in.', 'warning')
                return redirect(url_for('login'))
            user_role = session.get('role')
            if user_role not in allowed_roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)

        return decorated

    return decorator


@app.context_processor
def inject_user():
    return {
        'username': session.get('username'),
        'role': session.get('role')
    }


@app.route('/')
def root():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            flash('Username and password are required.', 'danger')
        else:
            role = authenticate(username, password)
            if role:
                session['username'] = username
                session['role'] = role
                if role == 'student':
                    session['reg_no'] = username
                flash(f'Welcome, {username}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    role = session.get('role')

    if role == 'student':
        return redirect(url_for('student_dashboard'))
    elif role == 'lecturer':
        # Lecturer dashboard
        students = []
        for reg, data in system.students.items():
            students.append({
                'id': reg,
                'name': data['name'],
                'course': data['course']
            })

        units = []
        for code, data in system.units.items():
            units.append({
                'id': code,
                'name': data['name'],
                'code': code
            })

        recent_marks = []
        for reg, marks in system.marks.items():
            if reg in system.students:
                student_name = system.students[reg]['name']
                for unit, mark in marks.items():
                    unit_name = system.units.get(unit, {}).get('name', unit)
                    # FIX: Create safe mark_id without slashes
                    safe_reg = reg.replace('/', '_')
                    recent_marks.append({
                        'id': f"{safe_reg}_{unit}",
                        'student_name': student_name,
                        'unit_name': unit_name,
                        'marks': mark,
                        'date_submitted': '2024-08-17'
                    })

        recent_marks = recent_marks[-10:][::-1]
        marks_submitted = sum(len(m) for m in system.marks.values())

        return render_template('lecturer_dashboard.html',
                               students=students,
                               units=units,
                               recent_marks=recent_marks,
                               marks_submitted=marks_submitted,
                               system=system)
    else:
        # Admin dashboard
        users = load_users()
        lecturers = []
        for username, data in users.items():
            if data.get('role') == 'lecturer':
                lecturers.append({
                    'username': username,
                    'full_name': data.get('full_name', username)
                })
        lecturer_count = len(lecturers)

        return render_template('admin_dashboard.html',
                               username=session.get('username'),
                               system=system,
                               lecturers=lecturers,
                               lecturer_count=lecturer_count)


# ---------- Student Dashboard Route ----------
@app.route('/student/dashboard')
@role_required(['student'])
def student_dashboard():
    reg_no = session.get('reg_no')
    if not reg_no:
        flash('Student registration number not found.', 'danger')
        return redirect(url_for('dashboard'))

    # Get student data
    student_data = system.students.get(reg_no)
    student_name = student_data.get('name', reg_no) if student_data else reg_no

    # Get student's marks
    marks = system.get_student_marks(reg_no)
    gpa = system.calculate_gpa(reg_no)
    marks_count = len(marks)

    # Get all units
    units = []
    for code, data in system.units.items():
        units.append({
            'code': code,
            'name': data['name']
        })

    # Get recent marks (last 5)
    recent_marks = []
    for unit, mark in marks.items():
        unit_name = system.units.get(unit, {}).get('name', unit)
        recent_marks.append({
            'unit_name': unit_name,
            'marks': mark
        })
    recent_marks = recent_marks[-5:][::-1]

    return render_template('student_dashboard.html',
                           student_name=student_name,
                           username=session.get('username'),
                           gpa=gpa,
                           marks_count=marks_count,
                           units=units,
                           recent_marks=recent_marks)


# ---------- Admin routes ----------
@app.route('/admin/students/add', methods=['GET', 'POST'])
@role_required(['admin'])
def admin_add_student():
    if request.method == 'POST':
        reg_no = request.form.get('reg_no', '').strip()
        name = request.form.get('name', '').strip()
        course = request.form.get('course', '').strip()
        password = request.form.get('password', '').strip()

        if not password:
            flash('A password is required for the student.', 'danger')
        elif len(password) < 4:
            flash('Password must be at least 4 characters.', 'danger')
        else:
            success, msg = system.add_student(reg_no, name, course, password)
            flash(msg, 'success' if success else 'danger')
        return redirect(url_for('admin_add_student'))
    courses = system.get_course_list()
    return render_template('add_student.html', courses=courses, system=system)


@app.route('/admin/students/remove', methods=['GET', 'POST'])
@role_required(['admin'])
def admin_remove_student():
    if request.method == 'POST':
        reg_no = request.form.get('reg_no', '').strip()

        if not reg_no:
            flash('Please select a student to remove.', 'danger')
        else:
            # Load students and check if they exist
            students = system.students  # Assuming your system object has a students dictionary
            if reg_no in students:
                # Remove student from dictionary
                del students[reg_no]
                system.save_students()  # Save changes to file/db
                flash(f'Student "{reg_no}" has been removed successfully.', 'success')
                return redirect(url_for('admin_view_students'))
            else:
                flash('Student not found.', 'danger')

    # GET request: Load the students dictionary to display in the dropdown
    students = system.students
    return render_template('remove_student.html', students=students)


# ---------- Admin Unit Routes ----------
@app.route('/admin/units/add', methods=['GET', 'POST'])
@role_required(['admin'])
def admin_add_unit():
    if request.method == 'POST':
        unit_code = request.form.get('unit_code', '').strip().upper()
        unit_name = request.form.get('unit_name', '').strip()

        # --- VALIDATION CHECKS ---

        # 1. Check if fields are empty
        if not unit_code or not unit_name:
            flash('Please fill in all fields.', 'danger')

        # 2. NEW CHECK: Reject pure numbers for Unit Code
        elif unit_code.isdigit():
            flash('Invalid Unit Code. It cannot consist of numbers only (e.g., use "BIT112" instead of "112").',
                  'danger')

        # 3. NEW CHECK: Limit Unit Name to 20 characters
        elif len(unit_name) > 20:
            flash('Unit Name must be 20 characters or less.', 'danger')

        # 4. Check if Unit Code already exists
        elif unit_code in system.units:
            flash(f'Unit "{unit_code}" already exists.', 'danger')

        # --- IF ALL CHECKS PASS ---
        else:
            system.units[unit_code] = {
                'name': unit_name,
                'course': None  # Or whatever default you use in your system
            }
            system.save_units()
            flash(f'Unit "{unit_code}" added.', 'success')
            return redirect(url_for('admin_add_unit'))

    return render_template('add_unit.html')


@app.route('/admin/units/remove', methods=['GET', 'POST'])
@role_required(['admin'])
def admin_remove_unit():
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        if not code:
            flash('Unit code is required.', 'danger')
        else:
            success, msg = system.remove_unit(code)
            flash(msg, 'success' if success else 'danger')
        return redirect(url_for('admin_remove_unit'))
    units = system.get_units_list()
    return render_template('remove_unit.html', units=units)


@app.route('/admin/units/view')
@role_required(['admin'])
def admin_view_units():
    units = system.get_units_list()
    return render_template('view_units.html', units=units)


# ---------- FIXED: Admin Add Course Route ----------
@app.route('/admin/courses/add', methods=['GET', 'POST'])
@role_required(['admin'])
def admin_add_course():
    if request.method == 'POST':
        course_code = request.form.get('code', '').strip().upper()  # FIXED: Changed from 'course_code' to 'code'
        course_name = request.form.get('name', '').strip()  # FIXED: Changed from 'course_name' to 'name'

        # --- VALIDATION CHECKS ---

        # 1. Check if fields are empty
        if not course_code or not course_name:
            flash('Please fill in all fields.', 'danger')
            return render_template('add_course.html')  # FIXED: Return to form instead of redirect

        # 2. NEW CHECK: Reject pure numbers for Course Code
        elif course_code.isdigit():
            flash('Invalid Course Code. It cannot consist of numbers only (e.g., use "CS101" instead of "1111").',
                  'danger')
            return render_template('add_course.html')  # FIXED: Return to form instead of redirect

        # 3. NEW CHECK: Limit Course Name to 30 characters
        elif len(course_name) > 30:
            flash('Course Name must be 30 characters or less.', 'danger')
            return render_template('add_course.html')  # FIXED: Return to form instead of redirect

        # 4. Check if Course Code already exists
        elif course_code in system.courses:
            flash(f'Course "{course_code}" already exists.', 'danger')
            return render_template('add_course.html')  # FIXED: Return to form instead of redirect

        # 5. Validate course code format (uppercase, numbers, hyphens only)
        elif not re.match(r'^[A-Z0-9\-]+$', course_code):
            flash('Course code must contain only uppercase letters, numbers, and hyphens.', 'danger')
            return render_template('add_course.html')  # FIXED: Return to form instead of redirect

        # --- IF ALL CHECKS PASS ---
        else:
            system.courses[course_code] = {
                'name': course_name
            }
            system.save_courses()
            flash(f'Course "{course_code}" added successfully!', 'success')
            return redirect(url_for('admin_add_course'))

    # GET request - show the form
    return render_template('add_course.html')


@app.route('/admin/courses/remove', methods=['GET', 'POST'])
@role_required(['admin'])
def admin_remove_course():
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        if not code:
            flash('Course code is required.', 'danger')
        else:
            success, msg = system.remove_course(code)
            flash(msg, 'success' if success else 'danger')
        return redirect(url_for('admin_remove_course'))
    courses = system.get_course_list()
    return render_template('remove_course.html', courses=courses)


@app.route('/admin/courses/view')
@role_required(['admin'])
def admin_view_courses():
    courses = system.get_course_list()
    return render_template('view_courses.html', courses=courses)


@app.route('/admin/change_password', methods=['GET', 'POST'])
@role_required(['admin'])
def admin_change_password():
    if request.method == 'POST':
        role = request.form.get('role', '').strip()
        username = request.form.get('username', '').strip()
        new_password = request.form.get('new_password', '').strip()

        if not role or not username or not new_password:
            flash('Please fill in all fields.', 'danger')
        else:
            users = load_users()
            if username in users and users[username].get('role') == role:
                # Update the password
                users[username]['password_hash'] = generate_password_hash(new_password)  # FIXED: Hash the password
                save_users(users)
                flash(f'Password for {role} "{username}" updated successfully!', 'success')
                return redirect(url_for('admin_change_password'))
            else:
                flash(f'User "{username}" not found with role "{role}".', 'danger')

    return render_template('edit_password.html')


@app.route('/admin/lecturers/add', methods=['GET', 'POST'])
@role_required(['admin'])
def admin_add_lecturer():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '').strip()

        if not full_name or not password:
            flash('Full name and password are required.', 'danger')
            return redirect(url_for('admin_add_lecturer'))

        valid, msg = validate_lecturer_name(full_name)
        if not valid:
            flash(msg, 'danger')
            return redirect(url_for('admin_add_lecturer'))

        if len(password) < 4:
            flash('Password must be at least 4 characters.', 'danger')
            return redirect(url_for('admin_add_lecturer'))

        base_username = full_name.lower().replace(' ', '')
        username = base_username

        users = load_users()
        counter = 1
        while username in users:
            username = f"{base_username}{counter}"
            counter += 1
        success, msg = create_user(username, password, 'lecturer', full_name=full_name)

        if success:
            flash(f'Lecturer created successfully! Username: "{username}"', 'success')
        else:
            flash(msg, 'danger')

        return redirect(url_for('admin_add_lecturer'))

    return render_template('add_lecturer.html')


@app.route('/admin/lecturers/view')
@role_required(['admin'])
def admin_view_lecturers():
    users = load_users()
    lecturers = []
    for username, data in users.items():
        if data.get('role') == 'lecturer':
            lecturers.append({
                'username': username,
                'full_name': data.get('full_name', username)
            })
    return render_template('view_lecturers.html', lecturers=lecturers)


@app.route('/admin/lecturers/remove', methods=['GET', 'POST'])
@role_required(['admin'])
def admin_remove_lecturer():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        if not username:
            flash('Please select a lecturer to remove.', 'danger')
        else:
            users = load_users()
            if username in users and users[username].get('role') == 'lecturer':
                del users[username]
                save_users(users)
                flash(f'Lecturer "{username}" has been removed.', 'success')
            else:
                flash('Lecturer not found.', 'danger')
        return redirect(url_for('admin_view_lecturers'))

    users = load_users()
    lecturers = []
    for username, data in users.items():
        if data.get('role') == 'lecturer':
            lecturers.append({
                'username': username,
                'full_name': data.get('full_name', username)
            })
    return render_template('remove_lecturer.html', lecturers=lecturers)


# ---------- Lecturer routes ----------
@app.route('/lecturer/add_marks', methods=['GET', 'POST'])
@role_required(['lecturer'])
def lecturer_add_marks():
    # Get all students from the system
    students = []
    for reg, data in system.students.items():
        students.append({
            'id': reg,
            'name': data['name'],
            'course': data['course']
        })

    # Get all units from the system
    units = []
    for code, data in system.units.items():
        units.append({
            'id': code,
            'name': data['name'],
            'code': code
        })

    # Get recent marks
    recent_marks = []
    for reg, marks in system.marks.items():
        if reg in system.students:
            student_name = system.students[reg]['name']
            for unit, mark in marks.items():
                unit_name = system.units.get(unit, {}).get('name', unit)
                # FIX: Create safe mark_id without slashes
                safe_reg = reg.replace('/', '_')
                recent_marks.append({
                    'id': f"{safe_reg}_{unit}",
                    'student_name': student_name,
                    'unit_name': unit_name,
                    'marks': mark,
                    'date_submitted': '2024-08-17'
                })

    # Sort recent marks by date (most recent first) and limit to 10
    recent_marks = recent_marks[-10:][::-1]

    # Calculate total marks submitted
    marks_submitted = sum(len(m) for m in system.marks.values())

    if request.method == 'POST':
        reg_no = request.form.get('student_id', '').strip()
        unit = request.form.get('unit_id', '').strip()
        marks = request.form.get('marks', '').strip()

        if not reg_no or not unit or not marks:
            flash('All fields are required.', 'danger')
        else:
            success, msg = system.add_mark(reg_no, unit, marks)
            flash(msg, 'success' if success else 'danger')
        return redirect(url_for('lecturer_add_marks'))

    # FIX: Added system=system to the render_template call
    return render_template('lecturer_dashboard.html',
                           students=students,
                           units=units,
                           recent_marks=recent_marks,
                           marks_submitted=marks_submitted,
                           system=system)

@app.route('/lecturer/view_marks')
@role_required(['lecturer'])
def lecturer_view_marks():
    marks_data = []
    for reg, marks in system.marks.items():
        if reg in system.students:
            student_name = system.students[reg]['name']
            for unit, mark in marks.items():
                # FIX: Create safe mark_id without slashes
                safe_reg = reg.replace('/', '_')
                marks_data.append({
                    'student_reg': reg,
                    'student_name': student_name,
                    'unit': unit,
                    'unit_name': system.units.get(unit, {}).get('name', unit),
                    'marks': mark,
                    'id': f"{safe_reg}_{unit}"  # Add id for edit link
                })
    return render_template('view_marks.html', marks=marks_data)


@app.route('/lecturer/edit_mark/<string:mark_id>', methods=['GET', 'POST'])
@role_required(['lecturer'])
def lecturer_edit_mark(mark_id):
    # Split the string by underscore
    parts = mark_id.split('_')

    # If there are less than 2 parts, it's definitely broken
    if len(parts) < 2:
        flash('Invalid mark ID format.', 'danger')
        return redirect(url_for('lecturer_view_marks'))

    # The unit code is ALWAYS the LAST part
    unit = parts[-1]

    # Everything before the last part is the student registration (replace underscores back with slashes)
    reg_no = '_'.join(parts[:-1]).replace('_', '/')

    # Check if the mark exists
    if reg_no not in system.marks or unit not in system.marks[reg_no]:
        flash('Mark not found.', 'danger')
        return redirect(url_for('lecturer_view_marks'))

    if request.method == 'POST':
        new_marks = request.form.get('marks', '').strip()
        if not new_marks:
            flash('Marks are required.', 'danger')
        else:
            try:
                marks_value = int(new_marks)
                if 0 <= marks_value <= 100:
                    system.marks[reg_no][unit] = marks_value
                    system.save_marks()
                    flash('Mark updated successfully!', 'success')
                    return redirect(url_for('lecturer_view_marks'))
                else:
                    flash('Marks must be between 0 and 100.', 'danger')
            except ValueError:
                flash('Invalid marks. Please enter a number.', 'danger')

    return render_template('edit_mark.html',
                           reg_no=reg_no,
                           unit=unit,
                           unit_name=system.units.get(unit, {}).get('name', unit),
                           current_marks=system.marks[reg_no][unit])


@app.route('/lecturer/manage_courses')
@role_required(['lecturer'])
def lecturer_manage_courses():
    courses = system.get_course_list()
    return render_template('lecturer_courses.html', courses=courses)


# ---------- View Students (Admin & Lecturer) ----------
@app.route('/view_students')
@role_required(['admin', 'lecturer'])
def view_students():
    students_list = []
    for reg, data in system.students.items():
        gpa = system.calculate_gpa(reg)
        students_list.append({
            'reg_no': reg,
            'name': data['name'],
            'course': data['course'],
            'marks_count': len(system.get_student_marks(reg)),
            'gpa': gpa
        })
    students_list.sort(key=lambda s: s['name'])
    return render_template('view_students.html', students=students_list)


# ---------- Student & common routes ----------
@app.route('/student/view_gpa', methods=['GET', 'POST'])
@role_required(['student', 'admin', 'lecturer'])
def student_view_gpa():
    result = None
    reg_no = request.args.get('reg_no', '').strip()
    if reg_no:
        success, msg = system.display_gpa(reg_no)
        if success:
            result = msg
        else:
            flash(msg, 'danger')
    if request.method == 'POST':
        reg_no = request.form.get('reg_no', '').strip()
        if reg_no:
            success, msg = system.display_gpa(reg_no)
            if success:
                result = msg
            else:
                flash(msg, 'danger')
        else:
            flash('Registration number is required.', 'danger')
    return render_template('gpa.html', result=result)


@app.route('/student/change_password', methods=['GET', 'POST'])
@role_required(['student'])
def student_change_password():
    if request.method == 'POST':
        current = request.form.get('current_password')
        new = request.form.get('new_password')
        confirm = request.form.get('confirm_password')

        if not current or not new or not confirm:
            flash('All fields are required.', 'danger')
        elif new != confirm:
            flash('New passwords do not match.', 'danger')
        elif len(new) < 4:
            flash('Password must be at least 4 characters.', 'danger')
        else:
            username = session['username']
            users = load_users()
            user = users.get(username)
            if user and check_password_hash(user['password_hash'], current):
                user['password_hash'] = generate_password_hash(new)
                save_users(users)
                flash('Password changed successfully!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Current password is incorrect.', 'danger')
    return render_template('change_password.html')


# ---------- Student routes ----------
@app.route('/student/view_marks')
@role_required(['student'])
def student_view_marks():
    reg_no = session.get('reg_no')
    if not reg_no:
        flash('Student registration number not found.', 'danger')
        return redirect(url_for('dashboard'))

    # Get student's marks
    marks = system.get_student_marks(reg_no)
    student_data = system.students.get(reg_no)

    marks_data = []
    for unit, mark in marks.items():
        unit_name = system.units.get(unit, {}).get('name', unit)
        marks_data.append({
            'unit_code': unit,
            'unit_name': unit_name,
            'marks': mark
        })

    gpa = system.calculate_gpa(reg_no)

    return render_template('student_marks.html',
                           marks=marks_data,
                           gpa=gpa,
                           student_name=student_data.get('name', '') if student_data else '')


@app.route('/student/view_units')
@role_required(['student'])
def student_view_units():
    units = system.get_units_list()
    return render_template('student_units.html', units=units)


@app.route('/student/download_my_results')
@role_required(['student'])
def student_download_my_results():
    reg_no = session.get('reg_no')
    if not reg_no:
        flash('Student registration number not found.', 'danger')
        return redirect(url_for('dashboard'))

    fmt = request.args.get('format', 'pdf').lower()
    if fmt == 'text':
        content, filename = system.download_result(reg_no)
        if content is None:
            flash('No results found.', 'danger')
            return redirect(url_for('dashboard'))
        return Response(content, mimetype='text/plain',
                        headers={'Content-Disposition': f'attachment; filename={filename}'})
    else:
        pdf_bytes = system.generate_student_pdf(reg_no)
        if pdf_bytes is None:
            flash('No results found.', 'danger')
            return redirect(url_for('dashboard'))
        filename = f"student_{reg_no.replace('/', '_')}_result.pdf"
        return send_file(BytesIO(pdf_bytes), as_attachment=True,
                         download_name=filename, mimetype='application/pdf')


@app.route('/student/download', methods=['GET'])
@role_required(['student', 'admin'])
def student_download():
    reg_no = request.args.get('reg_no', '').strip()
    if not reg_no:
        flash('Registration number is required.', 'danger')
        return redirect(url_for('dashboard'))

    if session.get('role') == 'student':
        if session.get('reg_no') != reg_no:
            flash('You can only download your own result.', 'danger')
            return redirect(url_for('dashboard'))

    fmt = request.args.get('format', 'pdf').lower()
    if fmt == 'text':
        content, filename = system.download_result(reg_no)
        if content is None:
            flash('Student not found.', 'danger')
            return redirect(url_for('dashboard'))
        return Response(content, mimetype='text/plain',
                        headers={'Content-Disposition': f'attachment; filename={filename}'})
    else:
        pdf_bytes = system.generate_student_pdf(reg_no)
        if pdf_bytes is None:
            flash('Student not found.', 'danger')
            return redirect(url_for('dashboard'))
        filename = f"student_{reg_no.replace('/', '_')}_result.pdf"
        return send_file(BytesIO(pdf_bytes), as_attachment=True,
                         download_name=filename, mimetype='application/pdf')


# ---------- Download All Students Route ----------
@app.route('/student/download_all', methods=['GET'])
@role_required(['admin', 'lecturer'])
def student_download_all():
    fmt = request.args.get('format', 'pdf').lower()

    if not system.students:
        flash('No students available to download.', 'warning')
        return redirect(url_for('view_students'))

    if fmt == 'text':
        content, filename = system.download_result()
        return Response(content, mimetype='text/plain',
                        headers={'Content-Disposition': f'attachment; filename={filename}'})
    else:
        pdf_bytes = system.generate_all_students_pdf()
        filename = "all_students_results.pdf"
        return send_file(BytesIO(pdf_bytes), as_attachment=True,
                         download_name=filename, mimetype='application/pdf')


# ---------- Seed initial data ----------
def seed_initial_data():
    users = load_users()
    if not users:
        # Set to what you want!
        default_admin_password = "admin123"
        default_lecturer_password = "lecturer123"

        create_user('admin', default_admin_password, 'admin')
        create_user('lecturer', default_lecturer_password, 'lecturer')

        print("============================================================")
        print("🚀 FIRST TIME SETUP: Default users created!")
        print(f"🔑 Admin User:     admin / Password: {default_admin_password}")
        print(f"🔑 Lecturer User:  lecturer / Password: {default_lecturer_password}")
        print("============================================================")


seed_initial_data()
# ---------- Run ----------
if __name__ == '__main__':
    app.run(debug=True)