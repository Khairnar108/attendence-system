"""
Run once after first install to set up the admin account and (optionally)
a few sample employees so you have something to click around:

    python seed.py
"""
from datetime import date

from app import create_app, db
from app.models import Employee, User

app = create_app()

SAMPLE_EMPLOYEES = [
    dict(employee_code="EMP-001", name="Aditi Rao", email="aditi.rao@example.com",
         department="Operations", designation="Floor Supervisor"),
    dict(employee_code="EMP-002", name="Rahul Mehta", email="rahul.mehta@example.com",
         department="Engineering", designation="Backend Developer"),
    dict(employee_code="EMP-003", name="Sneha Kulkarni", email="sneha.kulkarni@example.com",
         department="Human Resources", designation="HR Executive"),
]

with app.app_context():
    db.create_all()

    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        print("Created admin login  ->  username: admin   passcode: admin123")
    else:
        print("Admin user already exists, skipping.")

    for data in SAMPLE_EMPLOYEES:
        if Employee.query.filter_by(employee_code=data["employee_code"]).first():
            continue
        emp = Employee(date_joined=date.today(), **data)
        db.session.add(emp)
        db.session.flush()  # get emp.id before creating the user

        temp_password = f"{data['employee_code']}123"
        user = User(username=data["employee_code"], role="employee", employee_id=emp.id)
        user.set_password(temp_password)
        db.session.add(user)
        print(f"Created employee {data['name']}  ->  login: {data['employee_code']}   passcode: {temp_password}")

    db.session.commit()
    print("\nSeed complete. Change these passcodes after first login.")
