from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import Attendance

employee_bp = Blueprint("employee", __name__)


def require_employee():
    if current_user.is_admin or not current_user.employee_id:
        abort(403)


@employee_bp.route("/dashboard")
@login_required
def dashboard():
    require_employee()
    employee = current_user.employee
    today_record = employee.today_record()
    recent = (
        employee.attendance_records.order_by(Attendance.date.desc()).limit(7).all()
    )
    return render_template(
        "employee/dashboard.html",
        employee=employee,
        today_record=today_record,
        recent=recent,
        today=date.today(),
    )


@employee_bp.route("/punch-in", methods=["POST"])
@login_required
def punch_in():
    require_employee()
    employee = current_user.employee
    record = employee.today_record()

    if record and record.check_in:
        flash("You've already punched in today.", "notice")
        return redirect(url_for("employee.dashboard"))

    if not record:
        record = Attendance(employee_id=employee.id, date=date.today(), status="Present")
        db.session.add(record)

    record.check_in = datetime.now()
    record.status = "Present"
    db.session.commit()
    flash("Punched in. Have a good shift.", "success")
    return redirect(url_for("employee.dashboard"))


@employee_bp.route("/punch-out", methods=["POST"])
@login_required
def punch_out():
    require_employee()
    employee = current_user.employee
    record = employee.today_record()

    if not record or not record.check_in:
        flash("Punch in before you punch out.", "error")
        return redirect(url_for("employee.dashboard"))

    if record.check_out:
        flash("You've already punched out today.", "notice")
        return redirect(url_for("employee.dashboard"))

    record.check_out = datetime.now()
    db.session.commit()
    flash("Punched out. Record saved.", "success")
    return redirect(url_for("employee.dashboard"))


@employee_bp.route("/history")
@login_required
def history():
    require_employee()
    employee = current_user.employee

    month = request.args.get("month")  # format YYYY-MM
    query = employee.attendance_records.order_by(Attendance.date.desc())
    if month:
        year, mon = month.split("-")
        query = employee.attendance_records.filter(
            db.extract("year", Attendance.date) == int(year),
            db.extract("month", Attendance.date) == int(mon),
        ).order_by(Attendance.date.desc())

    records = query.all()
    return render_template(
        "employee/history.html", employee=employee, records=records, month=month
    )
