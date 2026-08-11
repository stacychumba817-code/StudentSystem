import json
import os
from flask import Flask, render_template, request, redirect, url_for, flash, Response

DATA_FILE = "students.json"

class StudentSystem:
    def __init__(self):
        self.students = self.load_students()

    def load_students(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        return {}

    def save_students(self):
        with open(DATA_FILE, 'w') as f:
            json.dump(self.students, f, indent=4)

    def add_student(self, reg_no, name, course):
        if reg_no in self.students:
            return False, "Student already exists."
        self.students[reg_no] = {"name": name, "course": course, "marks": {}}
        self.save_students()
        return True, f"Student {name} added successfully."

    def remove_student(self, reg_no):
        if reg_no in self.students:
            name = self.students[reg_no]["name"]
            del self.students[reg_no]
            self.save_students()
            return True, f"Student {name} (Reg: {reg_no}) removed successfully."
        return False, "Student not found."

    def add_mark(self, reg_no, unit, marks):
        if reg_no not in self.students:
            return False, "Student not found."
        try:
            marks = float(marks)
        except ValueError:
            return False, "Invalid marks. Please enter a number."
        self.students[reg_no]["marks"][unit] = marks
        self.save_students()
        return True, f"Marks for {unit} added successfully."

    def calculate_gpa(self, reg_no):
        if reg_no in self.students:
            marks = self.students[reg_no]["marks"]
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
            return {
                "reg_no": reg_no,
                "name": s["name"],
                "course": s["course"],
                "marks": s["marks"],
                "gpa": gpa
            }
        return None

    def display_gpa(self, reg_no):
        if reg_no in self.students:
            gpa = self.calculate_gpa(reg_no)
            name = self.students[reg_no]["name"]
            return True, f"GPA for {name} (Reg: {reg_no}) is {gpa}"
        return False, "Student not found."

    def download_result(self, reg_no=None):
        if reg_no is None:
            lines = []
            for reg, data in self.students.items():
                gpa = self.calculate_gpa(reg)
                lines.append(
                    f"Reg: {reg} | Name: {data['name']} | Course: {data['course']} | GPA: {gpa}"
                )
            content = "\n".join(lines) if lines else "No students registered."
            filename = "all_students_results.txt"
        else:
            if reg_no not in self.students:
                return None, None
            s = self.students[reg_no]
            gpa = self.calculate_gpa(reg_no)
            content = (
                f"Reg No: {reg_no}\n"
                f"Name: {s['name']}\n"
                f"Course: {s['course']}\n"
                f"Marks: {s['marks']}\n"
                f"GPA: {gpa}"
            )
            filename = f"student_{reg_no}_result.txt"
        return content, filename

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

system = StudentSystem()

@app.route('/')
def index():
    return render_template('index.html', system=system)

@app.route('/add', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        reg_no = request.form.get('reg_no', '').strip()
        name = request.form.get('name', '').strip()
        course = request.form.get('course', '').strip()
        if not reg_no or not name or not course:
            flash('All fields are required.', 'danger')
        else:
            success, msg = system.add_student(reg_no, name, course)
            flash(msg, 'success' if success else 'danger')
        return redirect(url_for('add_student'))
    return render_template('add_student.html')

@app.route('/remove', methods=['GET', 'POST'])
def remove_student():
    if request.method == 'POST':
        reg_no = request.form.get('reg_no', '').strip()
        if not reg_no:
            flash('Registration number is required.', 'danger')
        else:
            success, msg = system.remove_student(reg_no)
            flash(msg, 'success' if success else 'danger')
        return redirect(url_for('remove_student'))
    return render_template('remove_student.html')

@app.route('/search', methods=['GET', 'POST'])
def search_student():
    student = None
    if request.method == 'POST':
        reg_no = request.form.get('reg_no', '').strip()
        if reg_no:
            student = system.search_student(reg_no)
            if not student:
                flash('Student not found.', 'danger')
        else:
            flash('Registration number is required.', 'danger')
    return render_template('search_student.html', student=student)

@app.route('/add_marks', methods=['GET', 'POST'])
def add_marks():
    if request.method == 'POST':
        reg_no = request.form.get('reg_no', '').strip()
        unit = request.form.get('unit', '').strip()
        marks = request.form.get('marks', '').strip()
        if not reg_no or not unit or not marks:
            flash('All fields are required.', 'danger')
        else:
            success, msg = system.add_mark(reg_no, unit, marks)
            flash(msg, 'success' if success else 'danger')
        return redirect(url_for('add_marks'))
    return render_template('add_marks.html')

@app.route('/gpa', methods=['GET', 'POST'])
def gpa():
    result = None
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

@app.route('/download/<reg_no>')
def download_student(reg_no):
    content, filename = system.download_result(reg_no)
    if content is None:
        flash('Student not found.', 'danger')
        return redirect(url_for('index'))
    response = Response(content, status=200, mimetype='text/plain')
    response.headers.set('Content-Disposition', 'attachment', filename=filename)
    return response

@app.route('/download_all')
def download_all():
    content, filename = system.download_result()
    response = Response(content, status=200, mimetype='text/plain')
    response.headers.set('Content-Disposition', 'attachment', filename=filename)
    return response

if __name__ == '__main__':
    app.run(debug=True)