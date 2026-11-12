"""
Run this script to create demo login accounts and sample data.
Usage:
    python manage.py shell < create_demo_data.py
OR:
    python create_demo_data.py   (from inside manage.py shell)
"""

import os
import django
import sys

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import CustomUser
from employees.models import Employee, Department, Shift
from datetime import date, time

print("=" * 60)
print("  SmartHR Demo Data Setup")
print("=" * 60)

# ─── 1. DEPARTMENTS ────────────────────────────────────────────
dept_names = ['IT', 'Human Resources', 'Finance', 'Sales', 'Operations']
depts = {}
for name in dept_names:
    dept, created = Department.objects.get_or_create(name=name)
    depts[name] = dept
    if created:
        print(f"  [+] Department created: {name}")
    else:
        print(f"  [=] Department exists: {name}")

# ─── 2. SHIFTS ─────────────────────────────────────────────────
shift, created = Shift.objects.get_or_create(
    name='General Shift',
    defaults={
        'start_time': time(9, 0),
        'end_time': time(18, 0),
        'grace_period_minutes': 15,
    }
)
if created:
    print(f"  [+] Shift created: General Shift (09:00 AM – 06:00 PM, grace 15 min)")
else:
    print(f"  [=] Shift exists: General Shift")

# ─── 3. HR / ADMIN LOGIN ───────────────────────────────────────
print()
print("Creating HR / Admin account...")

if not CustomUser.objects.filter(username='admin').exists():
    admin = CustomUser.objects.create_superuser(
        username='admin',
        password='admin@123',
        first_name='Admin',
        last_name='User',
        email='admin@company.com',
        role='admin',
    )
    print("  [+] Admin account created")
else:
    admin = CustomUser.objects.get(username='admin')
    print("  [=] Admin account already exists")

if not CustomUser.objects.filter(username='hr').exists():
    hr_user = CustomUser.objects.create_user(
        username='hr',
        password='hr@123',
        first_name='Priya',
        last_name='Sharma',
        email='hr@company.com',
        role='hr',
        phone='9876543210',
    )
    print("  [+] HR account created")
else:
    print("  [=] HR account already exists")

# ─── 4. EMPLOYEE ACCOUNTS ──────────────────────────────────────
print()
print("Creating employee accounts...")

employees_data = [
    {
        'username': 'emp001',
        'password': 'emp@123',
        'first_name': 'Ashik',
        'last_name': 'T',
        'email': 'ashik@company.com',
        'phone': '9000000001',
        'employee_id': 'EMP001',
        'department': 'IT',
        'designation': 'Software Engineer',
    },
    {
        'username': 'emp002',
        'password': 'emp@123',
        'first_name': 'Ananya',
        'last_name': 'Nair',
        'email': 'ananya@company.com',
        'phone': '9000000002',
        'employee_id': 'EMP002',
        'department': 'Human Resources',
        'designation': 'HR Executive',
    },
    {
        'username': 'emp003',
        'password': 'emp@123',
        'first_name': 'Rahul',
        'last_name': 'Verma',
        'email': 'rahul@company.com',
        'phone': '9000000003',
        'employee_id': 'EMP003',
        'department': 'Finance',
        'designation': 'Accounts Manager',
    },
    {
        'username': 'emp004',
        'password': 'emp@123',
        'first_name': 'Meera',
        'last_name': 'Joseph',
        'email': 'meera@company.com',
        'phone': '9000000004',
        'employee_id': 'EMP004',
        'department': 'Sales',
        'designation': 'Sales Executive',
    },
    {
        'username': 'emp005',
        'password': 'emp@123',
        'first_name': 'Kiran',
        'last_name': 'Pillai',
        'email': 'kiran@company.com',
        'phone': '9000000005',
        'employee_id': 'EMP005',
        'department': 'IT',
        'designation': 'UI/UX Designer',
    },
]

for data in employees_data:
    if not CustomUser.objects.filter(username=data['username']).exists():
        user = CustomUser.objects.create_user(
            username=data['username'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            email=data['email'],
            phone=data['phone'],
            role='employee',
        )
        emp = Employee.objects.create(
            user=user,
            employee_id=data['employee_id'],
            department=depts[data['department']],
            shift=shift,
            designation=data['designation'],
            joining_date=date(2024, 1, 15),
            status='active',
        )
        print(f"  [+] Employee created: {data['first_name']} {data['last_name']} ({data['employee_id']})")
    else:
        print(f"  [=] Employee exists: {data['username']}")


print()
print("=" * 60)
print("  SETUP COMPLETE — LOGIN CREDENTIALS")
print("=" * 60)
print()
print("  ADMIN / HR LOGIN:")
print("  ┌─────────────┬──────────────┬────────────────────────┐")
print("  │ Role        │ Username     │ Password               │")
print("  ├─────────────┼──────────────┼────────────────────────┤")
print("  │ Admin       │ admin        │ admin@123              │")
print("  │ HR Manager  │ hr           │ hr@123                 │")
print("  └─────────────┴──────────────┴────────────────────────┘")
print()
print("  EMPLOYEE LOGIN (all use password: emp@123)")
print("  ┌────────────┬──────────────┬───────────────────────────────┐")
print("  │ Emp ID     │ Username     │ Name                          │")
print("  ├────────────┼──────────────┼───────────────────────────────┤")
print("  │ EMP001     │ emp001       │ Ashik T (IT)                  │")
print("  │ EMP002     │ emp002       │ Ananya Nair (HR)              │")
print("  │ EMP003     │ emp003       │ Rahul Verma (Finance)         │")
print("  │ EMP004     │ emp004       │ Meera Joseph (Sales)          │")
print("  │ EMP005     │ emp005       │ Kiran Pillai (IT)             │")
print("  └────────────┴──────────────┴───────────────────────────────┘")
print()
print("  LOGIN URL:  http://127.0.0.1:8000/accounts/login/")
print("  ADMIN SITE: http://127.0.0.1:8000/admin/")
print()
print("  To start the server:")
print("  python manage.py runserver")
print()
