import csv
import io
from datetime import date, datetime

from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app import db
from app.models import Attendance, Employee, User

admin_bp = Blueprint("admin", __name__)


def require_admin():
    if not current_user.is_admin:
        abort(403)


@admin_bp.route("/dashboard")
@login_required
def dashboard():
    require_admin()
    today = date.today()
    total_employees = Employee.query.filter_by(is_active=True).count()

    today_records = Attendance.query.filter_by(date=today).all()
    present_today = sum(1 for r in today_records if r.status == "Present")
    leave_today = sum(1 for r in today_records if r.status == "Leave")
    marked_ids = {r.employee_id for r in today_records}
    absent_today = total_employees - len(marked_ids)

    departments = {}
    for e in Employee.query.filter_by(is_active=True).all():
        departments[e.department] = departments.get(e.department, 0) + 1

    recent_activity = (
        Attendance.query.filter(Attendance.check_in.isnot(None))
        .order_by(Attendance.check_in.desc())
        .limit(8)
        .all()
    )

    return render_template(
        "admin/dashboard.html",
        total_employees=total_employees,
        present_today=present_today,
        absent_today=max(absent_today, 0),
        leave_today=leave_today,
        departments=departments,
        recent_activity=recent_activity,
        today=today,
    )


# ---------- Employee management ----------

@admin_bp.route("/employees")
@login_required
def employees():
    require_admin()
    dept = request.args.get("department", "")
    query = Employee.query
    if dept:
        query = query.filter_by(department=dept)
    all_employees = query.order_by(Employee.name).all()
    all_departments = sorted({e.department for e in Employee.query.all()})
    return render_template(
        "admin/employees.html",
        employees=all_employees,
        departments=all_departments,
        selected_department=dept,
    )


@admin_bp.route("/employees/new", methods=["GET", "POST"])
@login_required
def new_employee():
    require_admin()
    if request.method == "POST":
        return _save_employee()
    return render_template("admin/employee_form.html", employee=None)


@admin_bp.route("/employees/<int:employee_id>/edit", methods=["GET", "POST"])
@login_required
def edit_employee(employee_id):
    require_admin()
    employee = Employee.query.get_or_404(employee_id)
    if request.method == "POST":
        return _save_employee(employee)
    return render_template("admin/employee_form.html", employee=employee)


def _save_employee(employee=None):
    code = request.form.get("employee_code", "").strip()
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    department = request.form.get("department", "").strip()
    designation = request.form.get("designation", "").strip()

    if not all([code, name, email, department, designation]):
        flash("All fields are required.", "error")
        return redirect(request.url)

    is_new = employee is None
    if is_new:
        employee = Employee(employee_code=code)
        db.session.add(employee)

    employee.employee_code = code
    employee.name = name
    employee.email = email
    employee.department = department
    employee.designation = designation

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Employee code or email already in use.", "error")
        return redirect(request.url)

    if is_new:
        # Auto-create a login for the new employee: username = employee_code,
        # temporary passcode = employee_code + '123' (they should be told to change it)
        temp_password = f"{code}123"
        user = User(
            username=code,
            role="employee",
            employee_id=employee.id,
        )
        user.set_password(temp_password)
        db.session.add(user)
        db.session.commit()
        flash(
            f"Employee added. Login ID: {code} — temporary passcode: {temp_password}",
            "success",
        )
    else:
        flash("Employee record updated.", "success")

    return redirect(url_for("admin.employees"))


@admin_bp.route("/employees/<int:employee_id>/deactivate", methods=["POST"])
@login_required
def deactivate_employee(employee_id):
    require_admin()
    employee = Employee.query.get_or_404(employee_id)
    employee.is_active = False
    db.session.commit()
    flash(f"{employee.name} marked inactive.", "notice")
    return redirect(url_for("admin.employees"))


@admin_bp.route("/employees/<int:employee_id>/activate", methods=["POST"])
@login_required
def activate_employee(employee_id):
    require_admin()
    employee = Employee.query.get_or_404(employee_id)
    employee.is_active = True
    db.session.commit()
    flash(f"{employee.name} reactivated.", "notice")
    return redirect(url_for("admin.employees"))


# ---------- Attendance ledger ----------

@admin_bp.route("/attendance")
@login_required
def attendance():
    require_admin()
    selected_date = request.args.get("date", date.today().isoformat())
    dept = request.args.get("department", "")

    try:
        parsed_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
    except ValueError:
        parsed_date = date.today()
        selected_date = parsed_date.isoformat()

    query = Attendance.query.filter_by(date=parsed_date).join(Employee)
    if dept:
        query = query.filter(Employee.department == dept)
    records = query.order_by(Employee.name).all()

    marked_employee_ids = {r.employee_id for r in records}
    unmarked_query = Employee.query.filter(Employee.is_active.is_(True))
    if marked_employee_ids:
        unmarked_query = unmarked_query.filter(~Employee.id.in_(marked_employee_ids))
    if dept:
        unmarked_query = unmarked_query.filter(Employee.department == dept)
    unmarked = unmarked_query.order_by(Employee.name).all()

    all_departments = sorted({e.department for e in Employee.query.all()})

    return render_template(
        "admin/attendance.html",
        records=records,
        unmarked=unmarked,
        selected_date=selected_date,
        departments=all_departments,
        selected_department=dept,
    )


@admin_bp.route("/attendance/mark", methods=["POST"])
@login_required
def mark_attendance():
    require_admin()
    employee_id = request.form.get("employee_id")
    record_date = request.form.get("date")
    status = request.form.get("status")

    parsed_date = datetime.strptime(record_date, "%Y-%m-%d").date()
    record = Attendance.query.filter_by(employee_id=employee_id, date=parsed_date).first()
    if not record:
        record = Attendance(employee_id=employee_id, date=parsed_date)
        db.session.add(record)

    record.status = status
    db.session.commit()
    flash("Attendance updated.", "success")
    return redirect(url_for("admin.attendance", date=record_date))


@admin_bp.route("/attendance/export")
@login_required
def export_attendance():
    require_admin()
    selected_date = request.args.get("date", date.today().isoformat())
    parsed_date = datetime.strptime(selected_date, "%Y-%m-%d").date()

    records = (
        Attendance.query.filter_by(date=parsed_date).join(Employee).order_by(Employee.name).all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Employee Code", "Name", "Department", "Status", "Check In", "Check Out", "Hours"])
    for r in records:
        writer.writerow(
            [
                r.employee.employee_code,
                r.employee.name,
                r.employee.department,
                r.status,
                r.check_in.strftime("%H:%M:%S") if r.check_in else "",
                r.check_out.strftime("%H:%M:%S") if r.check_out else "",
                r.hours_worked or "",
            ]
        )

    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=attendance_{selected_date}.csv"
    return response
