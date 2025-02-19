
from flask_login import login_required, current_user
from flask import Flask, render_template, flash, redirect, url_for
from flask import render_template
from flask import request, jsonify
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import sqlite3
import hashlib
import os
from flask_sqlalchemy import SQLAlchemy
import pyotp
import requests
import glob
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from config import Config
# from models.models import User
from flask_socketio import SocketIO, send
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from typing import Optional

app = Flask(__name__)
app.config.from_object(Config)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
socketio = SocketIO(app, cors_allowed_origins="*")


class User(UserMixin):
    def __init__(self, id: int, username: str, password: str, email: str,
                 branch: Optional[str] = None, is_admin: bool = False,
                 role_default: Optional[int] = 0):
        self.id = id
        self.username = username
        self.password = password
        self.email = email
        self.branch = branch
        self.is_admin = is_admin
        self.role_default = role_default

    def get_id(self):
        """Override get_id method to work with Flask-Login."""
        return str(self.id)

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@socketio.on("message")
def handle_message(msg):
    print(f"Message: {msg}")
    send(msg, broadcast=True)  # Broadcast message to all clients


def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database and create tables if they don't exist."""
    with get_db_connection() as conn:
        # Create users table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Hash TEXT,
                CreatedAt TEXT DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt TEXT DEFAULT CURRENT_TIMESTAMP,
                UserName TEXT UNIQUE NOT NULL,
                Password TEXT NOT NULL,
                Email TEXT UNIQUE NOT NULL,
                FirstNameKh TEXT,
                LastNameKh TEXT,
                FirstNameEn TEXT,
                LastNameEn TEXT,
                Branch TEXT,
                IsAdmin INTEGER DEFAULT 0,
                DisplayName TEXT,
                LoginName TEXT,
                StartDate TEXT,
                EndDate TEXT,
                Mobile1 TEXT,
                Mobile2 TEXT,
                Active INTEGER DEFAULT 1,
                Menu TEXT,
                Language TEXT DEFAULT 'en',
                Status TEXT,
                Note TEXT,
                RequestRole TEXT,
                RoleDefault INTEGER DEFAULT 0,
                AcceptedTerms INTEGER DEFAULT 0
            )
        ''')

        # Create employees table with foreign key to position
        conn.execute('''
             CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER NOT NULL CHECK(age >= 18 AND age <= 100),
                department TEXT NOT NULL,
                salary REAL NOT NULL CHECK(salary > 0),
                position_id INTEGER,  -- Reference to the position table
                joining_date TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT CHECK(status IN ('Active', 'Inactive', 'On Leave')) DEFAULT 'Active',
                branch TEXT,  -- Branch of the employee
                user_id INTEGER,  -- Reference to the user table
                phone_number TEXT,  -- Contact number of the employee
                email TEXT UNIQUE,  -- Email address of the employee
                address TEXT,  -- Employee address
                emergency_contact_name TEXT,
                emergency_contact_phone TEXT,
                FOREIGN KEY (user_id) REFERENCES users(ID),
                FOREIGN KEY (position_id) REFERENCES positions(ID)
            )
        ''')

        # Create payroll table for employee payments
        conn.execute('''
            CREATE TABLE IF NOT EXISTS payroll (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                period_start_date TEXT NOT NULL,
                period_end_date TEXT NOT NULL,
                base_salary REAL NOT NULL,
                bonus REAL DEFAULT 0,
                deductions REAL DEFAULT 0,
                tax REAL DEFAULT 0,
                total_salary REAL NOT NULL,
                payment_date TEXT DEFAULT CURRENT_DATE,
                FOREIGN KEY (employee_id) REFERENCES employees (id)
            )
        ''')

        # Create branches table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS branches (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                Status TEXT CHECK(Status IN ('Active', 'Inactive')) DEFAULT 'Active',
                CreateDate DATETIME,
                StartDate DATETIME,
                Description TEXT,
                Branch TEXT NOT NULL,
                BranchManagerName TEXT,
                ContactNumber TEXT,
                Address TEXT,
                DistrictProvince TEXT,
                RegisterDate DATETIME,
                LocalDescription TEXT,
                LocalAddress TEXT,
                LocalBranchManagerName TEXT,
                BranchProjectId TEXT,
                CapitalInjectionId TEXT,
                GroupID TEXT,
                MemberID TEXT
            )
        ''')

        # Create roles table to manage user roles and related info
        conn.execute('''
            CREATE TABLE IF NOT EXISTS roles (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                UserID INTEGER NOT NULL,
                Role TEXT NOT NULL,
                RoleNumber INTEGER NOT NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                Status TEXT CHECK(Status IN ('Active', 'Inactive')) DEFAULT 'Active',
                Description TEXT,
                FOREIGN KEY (UserID) REFERENCES users(ID) ON DELETE CASCADE
            )
        ''')

        # Create user_branches table (many-to-many relationship between users and branches)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_branches (
                user_id INTEGER,
                branch_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (ID) ON DELETE CASCADE,
                FOREIGN KEY (branch_id) REFERENCES branches (ID) ON DELETE CASCADE,
                PRIMARY KEY (user_id, branch_id)
            )
        ''')

        # Create login_logs table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS login_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ip_address TEXT NOT NULL,
                city TEXT,
                region TEXT,
                country TEXT,
                user_agent TEXT,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (ID)
            )
        ''')

        # Create online_users table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS online_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (ID)
            )
        ''')

        # Create attendance table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS Attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT NOT NULL,
                date TEXT NOT NULL DEFAULT CURRENT_DATE,
                status TEXT NOT NULL,
                checkin_time TEXT,
                checkout_time TEXT,
                total_hours REAL DEFAULT 0,
                workday_count REAL DEFAULT 0
            )
        ''')

        # Create role table on user
        conn.execute('''
            CREATE TABLE IF NOT EXISTS role (
                UserID INTEGER NOT NULL,
                UserRoleID INTEGER NOT NULL,
                PRIMARY KEY (UserID, UserRoleID),
                FOREIGN KEY (UserID) REFERENCES users (ID) ON DELETE CASCADE,
                FOREIGN KEY (UserRoleID) REFERENCES roles (ID) ON DELETE CASCADE
            )
        ''')

        # Create messages table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create departments table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS departments (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT NOT NULL,
                Description TEXT,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create positions table with a foreign key reference to departments
        conn.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                PositionName TEXT NOT NULL UNIQUE,  -- Name of the position (e.g., Manager, Developer)
                Description TEXT,  -- Description of the position
                department_id INTEGER,  -- Reference to the departments table
                FOREIGN KEY (department_id) REFERENCES departments(ID)  -- Foreign key to departments
            )
        ''')

        # Create leave table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS leaves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                leave_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                reason TEXT NOT NULL,
                start_date_obj DATE,
                end_date_obj DATE,
                service_count INTEGER,
                status TEXT DEFAULT 'Pending',
                FOREIGN KEY (employee_id) REFERENCES employees(ID) ON DELETE CASCADE
            )
        ''')

        # Create bankstatement table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS bankstatement (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                employee_id INTEGER NOT NULL,
                employee_name TEXT NOT NULL,
                account_name TEXT NOT NULL,
                account_number TEXT NOT NULL,
                bank_name TEXT NOT NULL,
                salary REAL NOT NULL,
                transaction_date DATE NOT NULL,
                transaction_type TEXT CHECK(transaction_type IN ('Credit', 'Debit')) NOT NULL,
                FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
            )
        ''')

        conn.commit()


@app.route('/list-accepted-terms')
def list_accepted_terms():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE AcceptedTerms = 1')
        users = cursor.fetchall()

    return render_template('/terms/list_accepted_terms.html', users=users)


@app.route('/accept-terms', methods=['GET', 'POST'])
@login_required
def accept_terms():
    # Redirect non-admin users to their specific check-ins page
    if current_user.is_admin == 0:  # Non-admin users
        return redirect(url_for('term_user_id', user_id=current_user.id))

    email = current_user.email
    user_id = current_user.id  # Defining user_id from current_user

    if request.method == 'POST':
        with get_db_connection() as conn:
            cursor = conn.cursor()

            if current_user.is_admin == 0:  # Regular user
                cursor.execute(
                    'UPDATE users SET AcceptedTerms = 1 WHERE ID = ?', (user_id,))
            # If it's an admin (or any user with admin rights), update by email
            else:
                cursor.execute(
                    'UPDATE users SET AcceptedTerms = 1 WHERE Email = ?', (email,))

            conn.commit()
            flash('You have successfully accepted the Terms of Service.', 'success')
            return redirect(url_for('list_accepted_terms'))

    # If it's a GET request, render the terms page
    return render_template('terms/terms_of_service.html')


@app.route('/term_user_id/<int:user_id>', methods=['GET', 'POST'])
@login_required
def term_user_id(user_id):
    # Ensure that the current user is accessing their own page
    if user_id != current_user.id:
        flash('You cannot access another user\'s terms.', 'danger')
        return redirect(url_for('dashboard'))

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT AcceptedTerms FROM users WHERE ID = ?', (user_id,))
        accepted_terms = cursor.fetchone()[0]

    # Handle POST request for accepting terms
    if request.method == 'POST':
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE users SET AcceptedTerms = 1 WHERE ID = ?', (user_id,))
            conn.commit()
            flash('You have successfully accepted the Terms of Service.', 'success')
            return redirect(url_for('dashboard'))

    # Render the page showing terms of service for this user
    return render_template('/terms/accepted_terms.html', user_id=user_id, accepted_terms=accepted_terms)


@app.route('/privacy-policy')
def privacy_policy():
    return render_template('/policy/privacy_policy.html')

# Route to create a bank statement


@app.route('/bankstatement/add', methods=['GET', 'POST'])
def create_bankstatement():
    if request.method == 'GET':
        # For GET requests, render the form and get the employees for the dropdown
        with get_db_connection() as conn:
            employees = conn.execute(
                'SELECT id, name FROM employees').fetchall()
        return render_template('/bankstatements/add_bankstatement.html', employees=employees)

    # Handle POST request to get form data and insert into database
    employee_id = request.form.get('employee_id')
    employee_name = request.form.get('employee_name')
    account_name = request.form.get('account_name')
    account_number = request.form.get('account_number')
    bank_name = request.form.get('bank_name')
    salary = request.form.get('salary')
    transaction_date = request.form.get('transaction_date')
    transaction_type = request.form.get('transaction_type')

    # Insert data into database
    with get_db_connection() as conn:
        conn.execute('''
            INSERT INTO bankstatement (employee_id, employee_name, account_name, account_number, bank_name, salary, transaction_date, transaction_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (employee_id, employee_name, account_name, account_number, bank_name, salary, transaction_date, transaction_type))
        conn.commit()

    flash('Bank statement created successfully', 'success')
    return redirect(url_for('get_all_bankstatements'))

# Route to view all bank statements


@app.route('/bankstatements')
def get_all_bankstatements():
    with get_db_connection() as conn:
        bankstatements = conn.execute('SELECT * FROM bankstatement').fetchall()
    return render_template('/bankstatements/view_bankstatements.html', bankstatements=bankstatements)

# Route to view a single bank statement


@app.route('/bankstatement/view/<int:id>')
def view_bankstatement(id):
    with get_db_connection() as conn:
        bankstatement = conn.execute(
            'SELECT * FROM bankstatement WHERE id = ?', (id,)).fetchone()
    return render_template('/bankstatements/view_bankstatement.html', bankstatement=bankstatement)

# Route to update a bank statement


@app.route('/bankstatement/edit/<int:id>', methods=['GET', 'POST'])
def update_bankstatement(id):
    with get_db_connection() as conn:
        bankstatement = conn.execute(
            'SELECT * FROM bankstatement WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        # Get form data
        employee_id = request.form.get('employee_id')
        employee_name = request.form.get('employee_name')
        account_name = request.form.get('account_name')
        account_number = request.form.get('account_number')
        bank_name = request.form.get('bank_name')
        salary = request.form.get('salary')
        transaction_date = request.form.get('transaction_date')
        transaction_type = request.form.get('transaction_type')

        # Update the bank statement in the database
        with get_db_connection() as conn:
            conn.execute('''
                UPDATE bankstatement
                SET employee_id = ?, employee_name = ?, account_name = ?, account_number = ?, bank_name = ?, salary = ?, transaction_date = ?, transaction_type = ?
                WHERE id = ?
            ''', (employee_id, employee_name, account_name, account_number, bank_name, salary, transaction_date, transaction_type, id))
            conn.commit()

        flash('Bank statement updated successfully', 'success')
        return redirect(url_for('get_all_bankstatements'))

    return render_template('/bankstatements/edit_bankstatement.html', bankstatement=bankstatement)

# Route to delete a bank statement


@app.route('/bankstatement/delete/<int:id>', methods=['POST'])
def delete_bankstatement(id):
    with get_db_connection() as conn:
        conn.execute('DELETE FROM bankstatement WHERE id = ?', (id,))
        conn.commit()

    flash('Bank statement deleted successfully', 'success')
    return redirect(url_for('get_all_bankstatements'))


# Create department
@app.route('/departments/add', methods=['GET', 'POST'])
def create_department():
    if request.method != 'POST':
        # For GET requests, render the form
        return render_template('/departments/add_department.html')
    # Use request.form.get() for form data
    name = request.form.get('name')
    description = request.form.get('description')

    # Validate the form data
    if not name:
        flash('Department name is required', 'error')
        return redirect(url_for('create_department'))

    # Insert the data into the database
    with get_db_connection() as conn:
        conn.execute('''
                INSERT INTO departments (Name, Description)
                VALUES (?, ?)
            ''', (name, description))
        conn.commit()

    flash('Department created successfully', 'success')
    return redirect(url_for('get_all_departments'))


@app.route('/departments')
def get_all_departments():
    with get_db_connection() as conn:
        departments = conn.execute('SELECT * FROM departments').fetchall()
    return render_template('/departments/departments.html', departments=departments)


@app.route('/departments/view/<int:id>')
def view_department(id):
    with get_db_connection() as conn:
        department = conn.execute(
            'SELECT * FROM departments WHERE id = ?', (id,)).fetchone()
    return render_template('/departments/view_department.html', department=department)

# Route to update a department


@app.route('/department/edit/<int:id>', methods=['GET', 'POST'])
def update_department(id):
    with get_db_connection() as conn:
        department = conn.execute(
            'SELECT * FROM departments WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')

        if not name:
            flash('Department name is required', 'error')
            return redirect(url_for('edit_department', id=id))

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE departments
                SET Name = ?, Description = ?
                WHERE id = ?
            ''', (name, description, id))
            conn.commit()

        flash('Department updated successfully', 'success')
        return redirect(url_for('get_all_departments'))

    return render_template('/departments/edit_department.html', department=department)

# Route to delete a department


@app.route('/departments/delete/<int:id>', methods=['POST'])
def delete_department(id):
    with get_db_connection() as conn:
        conn.execute('DELETE FROM departments WHERE id = ?', (id,))
        conn.commit()

    flash('Department deleted successfully', 'success')
    return redirect(url_for('get_all_departments'))


# Route to create a new position
@app.route('/positions/add', methods=['GET', 'POST'])
def create_position():
    departments = []
    with get_db_connection() as conn:
        departments = conn.execute('SELECT * FROM departments').fetchall()

    if request.method == 'POST':
        position_name = request.form.get('position_name')
        description = request.form.get('description')
        department_id = request.form.get('department_id')

        # Validate the form data
        if not position_name:
            flash('Position name is required', 'error')
            return redirect(url_for('create_position'))

        # Insert the new position into the database
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO positions (PositionName, Description, department_id)
                VALUES (?, ?, ?)
            ''', (position_name, description, department_id))
            conn.commit()

        flash('Position created successfully', 'success')
        return redirect(url_for('get_all_positions'))

    return render_template('/positions/add_position.html', departments=departments)

# Route to get all positions


@app.route('/positions')
def get_all_positions():
    with get_db_connection() as conn:
        positions = conn.execute('SELECT * FROM positions').fetchall()
    return render_template('/positions/positions.html', positions=positions)

# Route to view a single position


@app.route('/positions/view/<int:id>')
def view_position(id):
    with get_db_connection() as conn:
        position = conn.execute(
            'SELECT * FROM positions WHERE ID = ?', (id,)).fetchone()
        employees = conn.execute('''
            SELECT e.id, e.name, e.branch
            FROM employees e
            JOIN positions p ON p.ID = e.position_id
            WHERE p.ID = ?
        ''', (id,)).fetchall()
    return render_template('/positions/view_position.html', position=position, employees=employees)

# Route to update a position


@app.route('/positions/edit/<int:id>', methods=['GET', 'POST'])
def update_position(id):
    with get_db_connection() as conn:
        position = conn.execute(
            'SELECT * FROM positions WHERE ID = ?', (id,)).fetchone()
        departments = conn.execute('SELECT * FROM departments').fetchall()

    if request.method == 'POST':
        position_name = request.form.get('position_name')
        description = request.form.get('description')
        department_id = request.form.get('department_id')

        if not position_name:
            flash('Position name is required', 'error')
            return redirect(url_for('update_position', id=id))

        # Update the position in the database
        with get_db_connection() as conn:
            conn.execute('''
                UPDATE positions
                SET PositionName = ?, Description = ?, department_id = ?
                WHERE ID = ?
            ''', (position_name, description, department_id, id))
            conn.commit()

        flash('Position updated successfully', 'success')
        return redirect(url_for('get_all_positions'))

    return render_template('/positions/edit_position.html', position=position, departments=departments)

# Route to delete a position


@app.route('/positions/delete/<int:id>', methods=['POST'])
def delete_position(id):
    with get_db_connection() as conn:
        conn.execute('DELETE FROM positions WHERE ID = ?', (id,))
        conn.commit()

    flash('Position deleted successfully', 'success')
    return redirect(url_for('get_all_positions'))


# Get department by ID

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# Route to view all leaves


@app.route('/leaves')
def view_leaves():
    if current_user.is_authenticated and not current_user.is_admin:
        with get_db_connection() as conn:
            leaves = conn.execute(
                'SELECT * FROM leaves WHERE employee_id = ?', (current_user.id,)).fetchall()
    else:
        with get_db_connection() as conn:
            leaves = conn.execute('SELECT * FROM leaves').fetchall()

    return render_template('/leaves/view_leaves.html', leaves=leaves)


@app.route('/leave/add', methods=['GET', 'POST'])
def add_leave():
    employees = []

    # Fetch employee list from the database
    with get_db_connection() as conn:
        employees = conn.execute('SELECT id, name FROM employees').fetchall()

    if request.method == 'POST':
        employee_id = request.form['employee_id']
        leave_type = request.form['leave_type']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']

        # Calculate service count (difference between start_date and end_date)
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        service_count = (end_date_obj - start_date_obj).days + 1

        # Insert the leave record into the database
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO leaves (employee_id, leave_type, start_date, end_date, reason, service_count)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (employee_id, leave_type, start_date, end_date, reason, service_count))

        # Redirect to view leaves page after insertion
        return redirect(url_for('view_leaves'))

    # Render the form page with employees list
    return render_template('/leaves/add_leave.html', employees=employees)


@app.route('/leaves/all', methods=['GET'])
@login_required
def get_all_leave_dates():
    if current_user.is_admin == 0:
        # Redirect non-admin users to their specific check-ins page
        return redirect(url_for('leaves_user_id', user_id=current_user.id))

        # Get the optional date range parameters from the request
    start_date_filter = request.args.get('start_date')
    end_date_filter = request.args.get('end_date')

    # Prepare SQL query based on whether the date filters are provided
    query = '''
        SELECT l.id, e.name AS employee_name, l.leave_type, l.start_date, l.end_date
        FROM leaves l
        LEFT JOIN employees e ON l.employee_id = e.id
    '''

    # Add conditions to the query if date filters are provided
    if start_date_filter and end_date_filter:
        query += ' WHERE l.start_date BETWEEN ? AND ?'
        date_params = (start_date_filter, end_date_filter)
    elif start_date_filter:
        query += ' WHERE l.start_date >= ?'
        date_params = (start_date_filter,)
    elif end_date_filter:
        query += ' WHERE l.start_date <= ?'
        date_params = (end_date_filter,)
    else:
        date_params = ()

    # Fetch the leave records based on the query
    with get_db_connection() as conn:
        leaves = conn.execute(query, date_params).fetchall()

    # Initialize total_leave_days to accumulate total leave days
    total_leave_days = 0
    leave_records = []

    # Create a dictionary to count leave types and accumulate their leave days
    leave_type_count = {}

    for leave in leaves:
        # Ensure employee_name is available and handle missing data
        employee_name = leave['employee_name'] if leave['employee_name'] else "Unknown Employee"

        # Parse the start and end dates (ensure they're in 'YYYY-MM-DD' format)
        try:
            start_date_obj = datetime.strptime(leave['start_date'], "%Y-%m-%d")
            end_date_obj = datetime.strptime(leave['end_date'], "%Y-%m-%d")
        except ValueError:
            # If the date format is incorrect, continue to the next record
            continue

        # Calculate the leave days for each record
        leave_days = (end_date_obj - start_date_obj).days + 1
        total_leave_days += leave_days

        # Generate a list of all the leave days (mapping days between start and end date)
        leave_day_list = []
        current_day = start_date_obj
        while current_day <= end_date_obj:
            leave_day_list.append(current_day.strftime('%Y-%m-%d'))
            current_day += timedelta(days=1)

        # Update leave type count (both count of leaves and total leave duration)
        if leave['leave_type'] not in leave_type_count:
            leave_type_count[leave['leave_type']] = {
                'count': 0, 'total_days': 0}
        leave_type_count[leave['leave_type']]['count'] += 1
        leave_type_count[leave['leave_type']]['total_days'] += leave_days

        # Append the leave record with calculated leave days and the list of all leave days
        leave_records.append({
            'employee_name': employee_name,
            'leave_type': leave['leave_type'],
            'start_date': leave['start_date'],
            'end_date': leave['end_date'],
            'leave_days': leave_days,
            'leave_day_list': leave_day_list
        })

    # Return the leave records, total leave days, and leave type counts to the template
    return render_template('/leaves/all_leaves.html',
                           leaves=leave_records,
                           total_leave_days=total_leave_days,
                           leave_type_count=leave_type_count,
                           start_date=start_date_filter,
                           end_date=end_date_filter)


@app.route('/leaves/user/<int:user_id>', methods=['GET'])
@login_required
def leaves_user_id(user_id):
    if current_user.id != user_id:
        # Make sure that users can only see their own leave records
        # or another page you prefer, e.g., homepage
        return redirect(url_for('index'))

    # Get the optional date range parameters from the request
    start_date_filter = request.args.get('start_date')
    end_date_filter = request.args.get('end_date')

    # Prepare SQL query to get leave records for the specific user
    query = '''
        SELECT l.id, e.name AS employee_name, l.leave_type, l.start_date, l.end_date
        FROM leaves l
        LEFT JOIN employees e ON l.employee_id = e.id
        WHERE l.employee_id = ?
    '''

    # Add conditions to the query if date filters are provided
    if start_date_filter and end_date_filter:
        query += ' AND l.start_date BETWEEN ? AND ?'
        date_params = (user_id, start_date_filter, end_date_filter)
    elif start_date_filter:
        query += ' AND l.start_date >= ?'
        date_params = (user_id, start_date_filter)
    elif end_date_filter:
        query += ' AND l.start_date <= ?'
        date_params = (user_id, end_date_filter)
    else:
        date_params = (user_id,)

    # Fetch the leave records for the specific user
    with get_db_connection() as conn:
        leaves = conn.execute(query, date_params).fetchall()

    # Initialize total_leave_days to accumulate total leave days
    total_leave_days = 0
    leave_records = []

    # Create a dictionary to count leave types and accumulate their leave days
    leave_type_count = {}

    for leave in leaves:
        # Ensure employee_name is available and handle missing data
        employee_name = leave['employee_name'] if leave['employee_name'] else "Unknown Employee"

        # Parse the start and end dates (ensure they're in 'YYYY-MM-DD' format)
        try:
            start_date_obj = datetime.strptime(leave['start_date'], "%Y-%m-%d")
            end_date_obj = datetime.strptime(leave['end_date'], "%Y-%m-%d")
        except ValueError:
            # If the date format is incorrect, continue to the next record
            continue

        # Calculate the leave days for each record
        leave_days = (end_date_obj - start_date_obj).days + 1
        total_leave_days += leave_days

        # Generate a list of all the leave days (mapping days between start and end date)
        leave_day_list = []
        current_day = start_date_obj
        while current_day <= end_date_obj:
            leave_day_list.append(current_day.strftime('%Y-%m-%d'))
            current_day += timedelta(days=1)

        # Update leave type count (both count of leaves and total leave duration)
        if leave['leave_type'] not in leave_type_count:
            leave_type_count[leave['leave_type']] = {
                'count': 0, 'total_days': 0}
        leave_type_count[leave['leave_type']]['count'] += 1
        leave_type_count[leave['leave_type']]['total_days'] += leave_days

        # Append the leave record with calculated leave days and the list of all leave days
        leave_records.append({
            'employee_name': employee_name,
            'leave_type': leave['leave_type'],
            'start_date': leave['start_date'],
            'end_date': leave['end_date'],
            'leave_days': leave_days,
            'leave_day_list': leave_day_list
        })

    # Return the leave records, total leave days, and leave type counts to the template
    return render_template('/leaves/all_leaves.html',  # You can create a custom template for user leaves
                           leaves=leave_records,
                           total_leave_days=total_leave_days,
                           leave_type_count=leave_type_count,
                           start_date=start_date_filter,
                           end_date=end_date_filter)


@app.route('/leave/edit/<int:id>', methods=['GET', 'POST'])
def edit_leave(id):
    with get_db_connection() as conn:
        leave = conn.execute(
            'SELECT * FROM leaves WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        leave_type = request.form['leave_type']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        status = request.form['status']

        # Calculate service count (difference between start_date and end_date)
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        service_count = (end_date_obj - start_date_obj).days + 1

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE leaves
                SET leave_type = ?, start_date = ?, end_date = ?, reason = ?, status = ?, service_count = ?
                WHERE id = ?
            ''', (leave_type, start_date, end_date, reason, status, service_count, id))

        return redirect(url_for('view_leaves'))

    return render_template('/leaves/edit_leave.html', leave=leave)


@app.route('/leave/delete/<int:id>')
def delete_leave(id):
    with get_db_connection() as conn:
        conn.execute('DELETE FROM leaves WHERE id = ?', (id,))

    return redirect(url_for('view_leaves'))


# Route to check-in an employee
@app.route('/checkin/<int:user_id>', methods=['GET', 'POST'])
def checkin(user_id):
    with get_db_connection() as conn:
        user = conn.execute(
            'SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

        # Check if user exists
        if user:
            # Convert sqlite3.Row to dictionary to avoid attribute errors
            user_dict = dict(user)

            # Check if employee exists
            if request.method == 'POST':
                # Process the check-in form submission
                checkin_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                conn.execute('''
                    INSERT INTO Attendance (employee_name, status, checkin_time)
                    VALUES (?, ?, ?)
                ''', (user_dict['UserName'], 'Checked In', checkin_time))
                conn.commit()

                # Redirect back to the user list or another page after check-in
                return redirect(url_for('list_checkin'))

            # Render the check-in form with the user data
            return render_template('/worktime/checkin.html', user=user_dict)

    # Redirect if user doesn't exist
    return redirect(url_for('list_checkin'))


@app.route('/list_checkin', methods=['GET'])
@login_required
def list_checkin():
    # Check if the current user is not an admin (is_admin == 0)
    if current_user.is_admin == 0:
        # Redirect non-admin users to their specific check-ins page
        return redirect(url_for('list_checkin_by_user_id', user_id=current_user.id))

    with get_db_connection() as conn:
        # Fetch all check-in records from the Attendance table
        checkins = conn.execute('SELECT * FROM Attendance').fetchall()

        # Convert the check-ins to a list of dictionaries to make it more readable
        checkins_list = [dict(checkin) for checkin in checkins]

        # Calculate the total hours for each checkin
        for checkin in checkins_list:
            if checkin['checkout_time']:
                checkin_time = datetime.strptime(
                    checkin['checkin_time'], '%Y-%m-%d %H:%M:%S')
                checkout_time = datetime.strptime(
                    checkin['checkout_time'], '%Y-%m-%d %H:%M:%S')
                total_hours = (checkout_time -
                               checkin_time).total_seconds() / 3600
                checkin['total_hours'] = round(total_hours, 2)

    # Render the list_checkin.html template with the check-ins data
    return render_template('/worktime/list_checkin.html', checkins=checkins_list)


@app.route('/list_checkin/<int:user_id>', methods=['GET'])
def list_checkin_by_user_id(user_id):
    try:
        with get_db_connection() as conn:
            # Fetch all check-in records for the specific user from the Attendance table
            checkins = conn.execute(
                '''
                SELECT * FROM Attendance
                WHERE employee_name = (SELECT UserName FROM users WHERE id = ?)
                ''', (user_id,)
            ).fetchall()

            # If no check-ins found, return an empty list
            if not checkins:
                return render_template('/worktime/list_checkin.html', checkins=[])

            # Convert the check-ins to a list of dictionaries to make it more readable
            checkins_list = [dict(checkin) for checkin in checkins]

            # Calculate the total hours for each checkin
            for checkin in checkins_list:
                if checkin.get('checkout_time'):  # Check for None in checkout_time
                    checkin_time = datetime.strptime(
                        checkin['checkin_time'], '%Y-%m-%d %H:%M:%S')
                    checkout_time = datetime.strptime(
                        checkin['checkout_time'], '%Y-%m-%d %H:%M:%S')
                    total_hours = (checkout_time -
                                   checkin_time).total_seconds() / 3600
                    checkin['total_hours'] = round(total_hours, 2)
                else:
                    # Set total_hours to 0 if no checkout_time
                    checkin['total_hours'] = 0

            # Render the list_checkin.html template with the check-ins data
            return render_template('/worktime/list_checkin.html', checkins=checkins_list)

    except Exception as e:
        # Log or handle the exception
        print(f"Error fetching check-ins: {e}")
        return render_template('error.html', message="An error occurred while fetching check-ins.")
# Route to check-out an employee


@app.route('/checkout/<int:user_id>', methods=['GET', 'POST'])
def checkout(user_id):
    with get_db_connection() as conn:
        user = conn.execute(
            'SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

        # Check if user exists
        if user:
            # Convert sqlite3.Row to dictionary to avoid attribute errors
            user_dict = dict(user)

            # Handle the checkout form submission
            if request.method == 'POST':
                # Record the current time as the checkout time
                checkout_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Update the attendance record with the checkout time and status
                conn.execute('''
                    UPDATE Attendance
                    SET status = ?, checkout_time = ?
                    WHERE employee_name = ? AND status = 'Checked In'
                ''', ('Checked Out', checkout_time, user_dict['UserName']))
                conn.commit()

                # Redirect back to the check-in list after checkout
                return redirect(url_for('list_checkin'))

            # Render the checkout form with the user data
            return render_template('/worktime/checkout.html', user=user_dict)

    # Redirect if user doesn't exist
    return redirect(url_for('list_checkin'))


@app.route('/worked_time/<int:user_id>')
def worked_time(user_id):
    with get_db_connection() as conn:
        # Fetch employee details based on user ID
        employee = conn.execute('''
            SELECT u.id, u.UserName, e.name, e.department
            FROM users u
            INNER JOIN employees e ON u.id = e.user_id
            WHERE u.id = ?
        ''', (user_id,)).fetchone()

        if employee:
            # Fetch attendance records for the employee for the current month
            attendance = conn.execute('''
                SELECT * FROM Attendance WHERE employee_name = ?
                AND strftime('%Y-%m-%d', checkin_time) BETWEEN date('now', '-30 days') AND date('now')
                ORDER BY checkin_time DESC
            ''', (employee['UserName'],)).fetchall()

            worked_hours_per_day = {}
            overtime_per_day = {}
            leave_taken_per_day = {}

            for record in attendance:
                checkin_time = datetime.strptime(
                    record['checkin_time'], '%Y-%m-%d %H:%M:%S')
                checkout_time = datetime.strptime(
                    record['checkout_time'], '%Y-%m-%d %H:%M:%S') if record['checkout_time'] else None

                # Skip if there's no checkout time
                if not checkout_time:
                    continue

                # Calculate worked duration in hours for this record
                worked_duration = (
                    checkout_time - checkin_time).total_seconds() / 3600
                workday = checkin_time.date()

                # Track worked hours per day
                if workday not in worked_hours_per_day:
                    worked_hours_per_day[workday] = 0
                worked_hours_per_day[workday] += worked_duration

                # Calculate overtime (if worked more than 8 hours)
                if workday not in overtime_per_day:
                    overtime_per_day[workday] = 0
                if worked_hours_per_day[workday] > 8:
                    overtime_per_day[workday] += worked_hours_per_day[workday] - 8

            # Calculate leave taken for each day
            leave_taken_records = conn.execute('''
                SELECT * FROM leaves WHERE employee_id = ?
                AND strftime('%Y-%m-%d', start_date) BETWEEN date('now', '-30 days') AND date('now')
            ''', (employee['id'],)).fetchall()

            for leave in leave_taken_records:
                leave_start = datetime.strptime(
                    leave['start_date'], "%Y-%m-%d").date()
                leave_end = datetime.strptime(
                    leave['end_date'], "%Y-%m-%d").date()

                # Iterate over the leave days and record leave taken
                current_day = leave_start
                while current_day <= leave_end:
                    if current_day not in leave_taken_per_day:
                        leave_taken_per_day[current_day] = 0
                    leave_taken_per_day[current_day] += 1
                    current_day += timedelta(days=1)

            return render_template('worktime/worked_time.html',
                                   employee=employee,
                                   worked_hours_per_day=worked_hours_per_day,
                                   overtime_per_day=overtime_per_day,
                                   leave_taken_per_day=leave_taken_per_day)
        return "Employee not found."


def create_payroll(employee_id, period_start_date, period_end_date, base_salary, bonus=0, deductions=0, tax=0):
    """Create a new payroll record for an employee."""
    total_salary = float(base_salary) + float(bonus) - \
        float(deductions) - float(tax)
    with get_db_connection() as conn:
        conn.execute('''
            INSERT INTO payroll (employee_id, period_start_date, period_end_date, base_salary, bonus, deductions, tax, total_salary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (employee_id, period_start_date, period_end_date, base_salary, bonus, deductions, tax, total_salary))
        conn.commit()


def get_payroll_by_employee_and_period(employee_id, period_start_date, period_end_date):
    """Retrieve payroll details for a specific employee and period."""
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT * FROM payroll
            WHERE employee_id = ? AND period_start_date = ? AND period_end_date = ?
        ''', (employee_id, period_start_date, period_end_date))
        payroll = cursor.fetchone()
        return payroll


def list_payroll_for_employee(employee_id):
    """Retrieve all payroll records for a specific employee."""
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT * FROM payroll WHERE employee_id = ?
        ''', (employee_id,))
        payroll_records = cursor.fetchall()
        return payroll_records


def list_payroll_for_employee_name(employee_name):
    """Retrieve all payroll records for a specific employee."""
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT p.* FROM payroll p
            INNER JOIN employees e ON p.employee_id = e.id
            WHERE e.name = ?
        ''', (employee_name,))
        payroll_records = cursor.fetchall()
        return payroll_records


def list_all_payroll():
    """Retrieve all payroll records."""
    with get_db_connection() as conn:
        cursor = conn.execute('SELECT * FROM payroll')
        payroll_records = cursor.fetchall()
        return payroll_records


@app.route('/payroll_form', methods=['GET'])
def payroll_form():
    employees = get_all_employees()  # Assuming a function to fetch all employees
    return render_template('/payroll/payroll_form.html', employees=employees)


@app.route('/payroll', methods=['GET'])
def get_payroll():
    employee_id = request.args.get('employee_id', type=int)
    employee_name = request.args.get('employee_name')
    period_start_date = request.args.get('period_start_date')
    period_end_date = request.args.get('period_end_date')

    # Determine which payroll query to execute based on provided parameters
    if employee_id and period_start_date and period_end_date:
        payroll = get_payroll_by_employee_and_period(
            employee_id, period_start_date, period_end_date)
    elif employee_id:
        payroll = list_payroll_for_employee(employee_id)
    elif employee_name:
        payroll = list_payroll_for_employee_name(employee_name)
    else:
        payroll = list_all_payroll()

    # If no payroll records are found, return a 404 response
    if not payroll:
        return "No payroll records found", 404

    # Add employee details (name and branch) to each payroll record
    payroll_with_details = []
    for record in payroll:
        employee = get_employee_by_id(
            record['employee_id'])  # Get employee by ID
        if not employee and employee_name:  # If employee is not found by ID, try by name
            employee = get_employee_by_name(employee_name)

        if employee:
            record = dict(record)  # Make a mutable copy of the record
            record['employee_name'] = employee.get('name', 'Unknown')
            record['branch'] = employee.get('branch', 'Unknown')
        payroll_with_details.append(record)

    return jsonify(payroll_with_details)


def get_employee_by_id(employee_id):
    """Fetch employee by ID."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT id, name, branch FROM employees WHERE id = ?", (employee_id,))
        result = cursor.fetchone()
    if result:
        return {'id': result['id'], 'name': result['name'], 'branch': result['branch']}
        # Example SQLAlchemy query (adjust based on your actual setup)
    return None


def get_employee_by_name(employee_name):
    """Fetch employee by name."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT id, name, branch FROM employees WHERE name = ?", (employee_name,))
        result = cursor.fetchone()
    if result:
        return {'id': result['id'], 'name': result['name'], 'branch': result['branch']}
        # Example SQLAlchemy query (adjust based on your actual setup)
    return None


@app.route('/create_payroll', methods=['POST'])
def create_payroll_endpoint():
    data = request.json
    create_payroll(
        data['employee_id'],
        data['period_start_date'],
        data['period_end_date'],
        data['base_salary'],
        data.get('bonus', 0),
        data.get('deductions', 0),
        data.get('tax', 0)
    )
    return jsonify({"message": "Payroll record created successfully."})


@app.route('/payroll_list', methods=['GET'])
def payroll_list():
    if current_user.is_admin == 0:
        # Redirect non-admin users to their specific check-ins page
        return redirect(url_for('payroll_user_id', user_id=current_user.id))

        # Optional filters for employee ID, employee name, and date range
    employee_id = request.args.get('employee_id', type=int)
    employee_name = request.args.get('employee_name')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    # Convert the date strings to datetime objects if valid
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        else:
            start_date = None

        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            end_date = None
    except ValueError:
        return "Invalid date format. Please use 'YYYY-MM-DD'.", 400

    # Determine which payroll query to execute based on provided parameters
    if employee_id and employee_name and start_date and end_date:
        payroll_records = list_payroll_for_employee_name_and_id_with_date_range(
            employee_id, employee_name, start_date, end_date)
    elif employee_id and start_date and end_date:
        payroll_records = list_payroll_for_employee_with_date_range(
            employee_id, start_date, end_date)
    elif employee_name and start_date and end_date:
        payroll_records = list_payroll_for_employee_name_with_date_range(
            employee_name, start_date, end_date)
    elif employee_id:
        payroll_records = list_payroll_for_employee(employee_id)
    elif employee_name:
        payroll_records = list_payroll_for_employee_name(employee_name)
    elif start_date and end_date:
        payroll_records = list_payroll_for_date_range(start_date, end_date)
    else:
        payroll_records = list_all_payroll()

    # If no records found, return a 404 response
    if not payroll_records:
        return render_template('notfound.html')

    # Ensure all employees are fetched before rendering
    employees = get_all_employees()
    print("Employees:", employees)  # Debugging employees

    if not employees:
        return "Failed to retrieve employee information", 500

    # Render the HTML template with the payroll records and employees
    return render_template('payroll/payroll_list.html', payroll_records=payroll_records, employees=employees)


@app.route('/payroll_user_id/<int:user_id>', methods=['GET'])
def payroll_user_id(user_id):
    # Check if the current user is trying to access their own payroll information
    if current_user.id != user_id and current_user.is_admin == 0:
        return "You are not authorized to view this payroll record.", 403

    # Fetch payroll records for the given user_id
    payroll_records = list_payroll_for_employee(user_id)

    if not payroll_records:
        return render_template('notfound.html')

    employees = get_all_employees()
    # Render the payroll details for the user
    return render_template('payroll/payroll_list.html', payroll_records=payroll_records,  employees=employees)


def list_payroll_for_date_range(start_date, end_date):
    """Retrieve payroll records within a specified date range."""
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT * FROM payroll
            WHERE period_start_date >= ? AND period_end_date <= ?
        ''', (start_date, end_date))
        payroll_records = cursor.fetchall()
        return payroll_records


def get_all_employees():
    with get_db_connection() as connection:
        cursor = connection.cursor()
        query = "SELECT id, name, branch, department FROM employees"
        cursor.execute(query)
        employees = cursor.fetchall()

        # Convert rows to dictionaries with column names
        column_names = [description[0] for description in cursor.description]
        employees_dict = [dict(zip(column_names, employee))
                          for employee in employees]

    return employees_dict


def list_payroll_for_employee_name(employee_name):
    with get_db_connection() as connection:
        cursor = connection.cursor()

        query = """
        SELECT * FROM payroll
        WHERE employee_name LIKE ?
        """
        cursor.execute(query, (f'%{employee_name}%',))
        payroll_records = cursor.fetchall()

        column_names = [description[0] for description in cursor.description]
        payroll_records_dict = [dict(zip(column_names, record))
                                for record in payroll_records]

    return payroll_records_dict


def list_payroll_for_employee_name_and_id(employee_id, employee_name):
    # Use context manager to handle the database connection
    with get_db_connection() as connection:
        cursor = connection.cursor()
        # Query to filter by employee_id and employee_name
        query = """
        SELECT * FROM payroll
        WHERE employee_id = ? AND employee_name LIKE ?
        """
        cursor.execute(query, (employee_id, f'%{employee_name}%'))
        payroll_records = cursor.fetchall()

        # Assuming you return the records as a list of dictionaries
        column_names = [description[0] for description in cursor.description]
        payroll_records_dict = [dict(zip(column_names, record))
                                for record in payroll_records]

    # No need to explicitly close cursor or connection as 'with' handles that
    return payroll_records_dict


def generate_monthly_payroll():
    """Create payroll for all employees on the 25th of every month."""
    today = datetime.today()
    if today.day == 25:  # Check if today is the 25th
        start_date = today.replace(day=1)
        end_date = today.replace(day=1)
        end_date = end_date.replace(
            month=today.month + 1) - timedelta(days=1)  # Last day of the month

        with get_db_connection() as conn:
            cursor = conn.execute('SELECT * FROM employees')
            employees = cursor.fetchall()

            for employee in employees:
                create_payroll(
                    employee['id'],
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d'),
                    employee['salary'],
                    bonus=500,  # Example bonus
                    deductions=50,  # Example deduction
                    tax=100  # Example tax
                )
        print(f"Payroll generated for {len(employees)} employees.")


# Scheduler to run payroll generation every day, but only triggers on the 25th
scheduler = BackgroundScheduler()
scheduler.add_job(generate_monthly_payroll, 'interval',
                  days=1)  # Run daily, check if it's the 25th
scheduler.start()


@app.route('/contact', methods=['GET'])
def contact():
    return render_template('/contact/contact.html')


@app.route('/send_message', methods=['POST'])
def send_message():
    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')

    # Save the contact message to the database
    with get_db_connection() as conn:
        conn.execute(
            'INSERT INTO messages (name, email, message) VALUES (?, ?, ?)', (name, email, message))
        conn.commit()

    # Redirect to a thank-you page or display a success message
    return redirect(url_for('thank_you'))


@app.route('/thank_you', methods=['GET'])
def thank_you():
    return render_template('/contact/thank_you.html')

# 📌 List Attendance Records


@app.route('/roles', methods=['GET'])
def list_roles():
    """Display all roles in the system."""
    with get_db_connection() as conn:
        roles = conn.execute('SELECT * FROM roles').fetchall()
    return render_template('/roles/list_roles.html', roles=roles)


@app.route('/roles/create', methods=['GET', 'POST'])
def create_role():
    """Create a new role."""
    if request.method == 'POST':
        user_id = request.form['user_id']
        status = request.form['status']
        description = request.form.get('description')

        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO roles (UserID, Status, Description)
                VALUES (?, ?, ?)
            ''', (user_id, status, description))
            conn.commit()

        flash('Role created successfully!', 'success')
        # Redirect to the roles list page
        return redirect(url_for('list_roles'))

    # For GET request, render the form with available users
    with get_db_connection() as conn:
        users = conn.execute('SELECT id, UserName FROM users').fetchall()

    return render_template('/roles/create_role.html', users=users)


@app.route('/roles/update/<int:role_id>', methods=['GET', 'POST'])
def update_role(role_id):
    """Update an existing role."""
    with get_db_connection() as conn:
        role = conn.execute(
            'SELECT * FROM roles WHERE ID = ?', (role_id,)).fetchone()

    if request.method == 'POST':
        user_id = request.form['user_id']
        status = request.form['status']
        description = request.form['description']

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE roles
                SET UserID = ?, Status = ?, Description = ?
                WHERE ID = ?
            ''', (user_id, status, description, role_id))
            conn.commit()

        flash('Role updated successfully!', 'success')
        return redirect(url_for('list_roles'))

    return render_template('/roles/update_role.html', role=role)


@app.route('/roles/delete/<int:role_id>', methods=['POST'])
def delete_role(role_id):
    """Delete a role."""
    with get_db_connection() as conn:
        conn.execute('DELETE FROM roles WHERE ID = ?', (role_id,))
        conn.commit()

    flash('Role deleted successfully!', 'danger')
    return redirect(url_for('list_roles'))


@app.route('/attendance')
@login_required
def list_attendance():
    with get_db_connection() as conn:
        records = conn.execute(
            "SELECT * FROM attendance ORDER BY id DESC").fetchall()
        last_record = records[0] if records else None
        notifications_attendance = [
            {"title": "New Attendance Recorded",
             "message": f"{last_record['employee_name']} marked as {last_record['status']}."} if last_record else None
        ]
    return render_template('attendance/attendance.html', records=records, notifications_attendance=notifications_attendance)


@app.route('/attendance/search', methods=['GET'])
@login_required
def search_attendance():
    query = request.args.get('query', '')
    with get_db_connection() as conn:
        records = conn.execute(
            "SELECT * FROM attendance WHERE employee_name LIKE ?", (f'%{query}%',)).fetchall()
    return render_template('attendance/attendance.html', records=records)

# 📌 Add Attendance


@app.route('/attendance/add', methods=['GET', 'POST'])
@login_required
def add_attendance():
    if request.method == 'POST':
        employee_name = request.form['employee_name']
        status = request.form['status']
        with get_db_connection() as conn:
            conn.execute("INSERT INTO attendance (employee_name, status) VALUES (?, ?)",
                         (employee_name, status))
            conn.commit()
        return redirect(url_for('list_attendance'))
    return render_template('attendance/add_attendance.html')


@app.route('/attendance/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_attendance(id):
    with get_db_connection() as conn:
        record = conn.execute(
            "SELECT * FROM attendance WHERE id = ?", (id,)).fetchone()
    if request.method == 'POST':
        employee_name = request.form['employee_name']
        status = request.form['status']
        with get_db_connection() as conn:
            conn.execute("UPDATE attendance SET employee_name = ?, status = ? WHERE id = ?",
                         (employee_name, status, id))
            conn.commit()
        return redirect(url_for('list_attendance'))
    return render_template('attendance/edit_attendance.html', record=record)


@app.route('/attendance/delete/<int:id>', methods=['POST'])
@login_required
def delete_attendance(id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM attendance WHERE id = ?", (id,))
        conn.commit()
    return redirect(url_for('list_attendance'))


@app.route('/attendance/<int:id>')
@login_required
def view_attendance(id):
    with get_db_connection() as conn:
        record = conn.execute(
            "SELECT * FROM attendance WHERE id = ?", (id,)).fetchone()
    if record:
        return render_template('attendance/view_attendance.html', record=record)
    else:
        return "Record not found", 404

# Function to send OTP via Telegram


@app.before_request
def update_last_active_time():
    if current_user.is_authenticated:
        with get_db_connection() as conn:
            conn.execute('''
                UPDATE online_users
                SET last_active_time = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (current_user.id,))
            conn.commit()


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{app.config['TELEGRAM_BOT_TOKEN']}/sendMessage"
    payload = {"chat_id": app.config['TELEGRAM_CHAT_ID'], "text": message}
    response = requests.post(url, data=payload)
    print(response.status_code, response.text)  # Debugging: Check API response
    if response.status_code != 200:
        return False
    print("\007")  # Alert sound
    return True


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        mobile1 = request.form['mobile1']
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        # Check if username or email already exists in the database
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM users WHERE UserName = ? OR Email = ?', (username, email))
            existing_user = cursor.fetchone()

            if existing_user:
                flash('Username or Email already exists. Try again.', 'danger')
                return render_template('register.html')

        # Insert user data into the database
        with get_db_connection() as conn:
            try:
                conn.execute('''
                    INSERT INTO users (UserName, Password, Email, Mobile1)
                    VALUES (?, ?, ?, ?)
                ''', (username, hashed_password, email, mobile1))
                conn.commit()

                # Generate OTP and store it in session
                session["otp"] = pyotp.TOTP(pyotp.random_base32()).now()

                # Send OTP and mobile number to the user's Telegram account
                otp_message = f"Verification Code: {session['otp']}\nYour mobile number: {mobile1}\nYour email: {email}"
                if send_telegram_message(otp_message):
                    flash(
                        "Registration successful! Check your Telegram for OTP.", "info")
                else:
                    flash(
                        "Failed to send OTP via Telegram. Please try again.", "danger")

                # Redirect to OTP verification page
                return redirect(url_for('verify_otp'))

            except sqlite3.IntegrityError:
                flash("Username or Email already exists. Try again.", "danger")
                return render_template('register.html')

    return render_template('register.html')


@app.route("/verify", methods=["GET", "POST"])
def verify_otp():
    if request.method == "POST":
        user_otp = request.form.get("otp")  # OTP entered by the user
        # Check if OTP entered by user matches the one in the session
        if user_otp and session.get("otp") == user_otp:
            flash("Account verified successfully!", "success")
            # Redirect to dashboard or other page
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid OTP! Try again.", "danger")
    return render_template("verify.html")


@app.route("/test_telegram")
def test_telegram():
    test_message = "This is a test message from Flask!"
    try:
        send_telegram_message(test_message)
        return "Test message sent successfully!"
    except Exception as e:
        return f"Failed to send test message: {e}"


@login_manager.user_loader
def load_user(user_id):
    with get_db_connection() as conn:
        user_data = conn.execute(
            'SELECT * FROM users WHERE ID = ?', (user_id,)).fetchone()
        if user_data:
            return User(id=user_data['ID'], username=user_data['UserName'], password=user_data['Password'], email=user_data['Email'], branch=user_data['Branch'], is_admin=user_data['IsAdmin'], role_default=user_data['RoleDefault'])
        return None


@login_manager.unauthorized_handler
def unauthorized():
    return render_template('unauthorized.html'), 401


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# File upload route with Flash messages


@app.route('/file', methods=['GET', 'POST'])
@login_required
def upload_image():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'error')  # Flash error message
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            flash('No selected file', 'error')  # Flash error message
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = f"{current_user.id}_{current_user.username}_{current_user.branch}_{secure_filename(file.filename)}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            # Flash success message
            flash('File uploaded successfully', 'success')
            return redirect(url_for('list_user_files', filename=filename))
        else:
            # Flash error for invalid file type
            flash('Invalid file type. Only jpg, png, and gif are allowed.', 'error')
            return redirect(request.url)

    return render_template('/uploads/uploaded_file.html', current_user=current_user)


# Search File route with Flash messages
@app.route('/search_files', methods=['GET'])
@login_required
def search_files():
    query = request.args.get('query', '').lower()

    files = []
    if query:
        search_pattern = os.path.join(
            app.config['UPLOAD_FOLDER'],
            f"{current_user.id}_{current_user.username}_{current_user.branch}*{query}*"
        )
        files = glob.glob(search_pattern)
        files = [os.path.basename(file) for file in files]

    return render_template('/uploads/list_files.html', files=files, query=query, current_user=current_user)


# Delete file route with Flash messages
@app.route('/delete_file/<filename>', methods=['POST'])
@login_required
def delete_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if os.path.exists(file_path):
        os.remove(file_path)
        flash('File deleted successfully', 'success')  # Flash success message
    else:
        flash('File not found', 'error')  # Flash error message

    return redirect(url_for('list_user_files'))


# List user files route with Flash messages
@app.route('/files', methods=['GET'])
@login_required
def list_user_files():
    upload_folder = app.config['UPLOAD_FOLDER']
    file_prefix = f"{current_user.id}_{current_user.username}_{current_user.branch}"
    files = os.listdir(upload_folder)
    user_files = [file for file in files if file.startswith(file_prefix)]
    return render_template('/uploads/list_files.html', files=user_files, current_user=current_user)


# Multiple file upload route with Flash messages
@app.route('/upload_files', methods=['GET', 'POST'])
@login_required
def upload_files():
    if request.method != 'POST':
        return render_template('/uploads/upload_files.html', current_user=current_user)
    if 'files' not in request.files:
        flash('No file part', 'error')  # Flash error message
        return redirect(request.url)

    files = request.files.getlist('files')
    if not files:
        flash('No selected files', 'error')  # Flash error message
        return redirect(request.url)

    upload_folder = app.config['UPLOAD_FOLDER']
    file_prefix = f"{current_user.id}_{current_user.username}_{current_user.branch}"

    for file in files:
        if file.filename == '':
            continue
        if file and allowed_file(file.filename):
            filename = f"{file_prefix}_{secure_filename(file.filename)}"
            file.save(os.path.join(upload_folder, filename))
        else:
            flash(
                f"Invalid file type: {file.filename}. Only jpg, png, and gif are allowed.", 'error')
            # Flash error message and return on failure
            return redirect(request.url)

    flash('Files uploaded successfully', 'success')  # Flash success message
    return redirect(url_for('list_user_files'))


# Route to view uploaded file
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return f'Image uploaded successfully: <img src="/static/uploads/{filename}" alt="uploaded image">'


@app.route('/')
def index():
    return render_template('login.html')

# Function to get geolocation based on IP address (optional)


def get_geolocation(ip):
    # Replace with your geolocation API (e.g., ipstack, ipinfo.io, etc.)
    api_url = f"http://ipinfo.io/{ip}/json"
    response = requests.get(api_url)
    data = response.json()
    city = data.get('city', 'Unknown')
    region = data.get('region', 'Unknown')
    return city, region, data.get('country', 'Unknown')


@app.route('/online_users', methods=['GET'])
def online_users():
    # Define the timeout threshold (e.g., 15 minutes)
    timeout_threshold = 15  # minutes

    with get_db_connection() as conn:
        online_users = conn.execute('''
            SELECT u.UserName, u.Email, ou.last_active_time
            FROM online_users ou
            JOIN users u ON ou.user_id = u.ID
            WHERE strftime('%s', 'now') - strftime('%s', ou.last_active_time) <= ? * 60
        ''', (timeout_threshold,)).fetchall()

    return render_template('online_users.html', online_users=online_users)


@app.route('/health', methods=['GET'])
def health_check():
    # You can customize this status if needed.
    status = "healthy"
    return render_template('health_check.html', status=status)


@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = hashlib.sha256(request.form['password'].encode()).hexdigest()

    # Get the user's IP address and user agent (browser/device info)
    ip_address = request.remote_addr
    user_agent = request.user_agent.string

    # Optionally get the geolocation (City, Region, Country) based on IP address
    city, region, country = get_geolocation(ip_address)

    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row  # Fetch rows as dictionaries
        user = conn.execute('''
            SELECT ID, UserName, Password, Email, Branch, IsAdmin,
                   COALESCE(RoleDefault, 1) AS RoleDefault
            FROM users
            WHERE UserName = ? AND Password = ?
        ''', (username, password)).fetchone()

    if user:
        user = dict(user)  # Convert row to dictionary for easy access
        print("Fetched User Data:", user)  # Debugging print statement

        # Log the login event (store user location and device info)
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO login_logs (user_id, ip_address, city, region, country, user_agent)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user['ID'], ip_address, city, region, country, user_agent))

            # Add user to online_users table or update if already exists
            conn.execute('''
                INSERT OR REPLACE INTO online_users (user_id, login_time, last_active_time)
                VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (user['ID'],))
            conn.commit()

        # Create the user object and log the user in with Flask-Login
        user_obj = User(
            id=user['ID'],
            username=user['UserName'],
            password=user['Password'],
            email=user['Email'],
            branch=user['Branch'],
            is_admin=user['IsAdmin'],
            role_default=user['RoleDefault']  # Ensure correct retrieval
        )

        print("Logged in user:", user_obj)  # Debugging print
        login_user(user_obj)  # Store the user session with Flask-Login

        flash(
            f"Logged in from {city}, {region}, {country} using {user_agent}", 'success')
        return redirect(url_for('dashboard'))

    else:
        flash("Invalid username or password", 'error')
        return render_template('404.html'), 404


@app.route('/logout', methods=['POST'])
def logout():
    # Remove the user from the online_users table if logged in
    if current_user.is_authenticated:
        with get_db_connection() as conn:
            conn.execute('''
                DELETE FROM online_users WHERE user_id = ?
            ''', (current_user.id,))
            conn.commit()
        # Remove the user from the online_users table

    # Log out the user using Flask-Login
    logout_user()

    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('index'))


@app.route('/change_password', methods=['GET', 'POST'])
@login_required  # Ensure the user is logged in
def change_password():
    if request.method != 'POST':
        return render_template('change_password.html')
    old_password = request.form['old_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    # Validate old password
    old_password_hashed = hashlib.sha256(old_password.encode()).hexdigest()

    with get_db_connection() as conn:
        user = conn.execute('''
                SELECT * FROM users WHERE ID = ?
            ''', (current_user.id,)).fetchone()

        if not user or user['Password'] != old_password_hashed:
            flash("Old password is incorrect.", 'error')
            return render_template('change_password.html', old_password_error="Old password is incorrect")

        # Check if new password and confirm password match
        if new_password != confirm_password:
            flash("New password and confirm password do not match.", 'error')
            return render_template('change_password.html', confirm_password_error="New password and confirmation do not match.")

        # Hash the new password and update in database
        new_password_hashed = hashlib.sha256(
            new_password.encode()).hexdigest()
        conn.execute('''
                UPDATE users
                SET Password = ?
                WHERE ID = ?
            ''', (new_password_hashed, current_user.id))
        conn.commit()

    flash("Your password has been updated successfully", 'success')
    return redirect(url_for('dashboard'))


@app.route('/validate_old_password', methods=['POST'])
@login_required  # Ensure the user is logged in
def validate_old_password():
    old_password = request.form['old_password']
    old_password_hashed = hashlib.sha256(old_password.encode()).hexdigest()

    # Check if the old password matches the stored password in the database
    with get_db_connection() as conn:
        user = conn.execute('''
            SELECT * FROM users WHERE ID = ?
        ''', (current_user.id,)).fetchone()

        if user and user['Password'] == old_password_hashed:
            return jsonify({'valid': True})
        else:
            return jsonify({'valid': False}), 400


@app.route('/users/', methods=['GET'])
@login_required
def users():
    with get_db_connection() as conn:
        users = conn.execute("SELECT * FROM users").fetchall()
    return render_template('/users/users.html', users=users)


@app.route('/users/add', methods=['GET', 'POST'])
def add_user():
    if current_user.is_admin == 0:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        mobile1 = request.form['mobile1']
        first_name_kh = request.form['first_name_kh']
        last_name_kh = request.form['last_name_kh']
        first_name_en = request.form['first_name_en']
        last_name_en = request.form['last_name_en']
        branch = request.form['branch']
        branch_id = request.form['branch']  # Get the branch ID from the form
        # Checkbox will return '1' if checked, else default to 0
        is_admin = request.form.get('is_admin', 0)
        role_default = request.form.get('role_default', 0)
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        # Insert user into 'users' table
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Check if username already exists
            cursor.execute(
                'SELECT * FROM users WHERE UserName = ?', (username,))
            existing_user = cursor.fetchone()

            if existing_user:
                flash('Username already exists. Please choose another one.', 'danger')
                return redirect(url_for('add_user'))

            cursor.execute('''
                INSERT INTO users (UserName, Password, Email, Mobile1, FirstNameKh, LastNameKh, FirstNameEn, LastNameEn, Branch, IsAdmin, RoleDefault)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (username, hashed_password, email, mobile1, first_name_kh, last_name_kh, first_name_en, last_name_en, branch, is_admin, role_default))
            user_id = cursor.lastrowid

            # Insert relationship into 'user_branches' table
            cursor.execute('''
                INSERT INTO user_branches (user_id, branch_id)
                VALUES (?, ?)
            ''', (user_id, branch_id))
            conn.commit()

        return redirect(url_for('list_users'))

    # Fetch all branches for selection
    with get_db_connection() as conn:
        branches = conn.execute('SELECT * FROM branches').fetchall()

    return render_template('/users/add_user.html', branches=branches)


@app.route('/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if current_user.is_admin == 0:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    with get_db_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE ID = ?", (id,)).fetchone()
        branches = conn.execute("SELECT * FROM branches").fetchall()

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        first_name_kh = request.form['first_name_kh']
        last_name_kh = request.form['last_name_kh']
        first_name_en = request.form['first_name_en']
        last_name_en = request.form['last_name_en']
        branch = request.form['branch']
        is_admin = request.form.get('is_admin', 0)
        role_default = request.form.get('role_default', 0)
        mobile1 = request.form['mobile1']

        with get_db_connection() as conn:
            conn.execute("""
                UPDATE users SET UserName = ?, Email = ?, FirstNameKh = ?, LastNameKh = ?, FirstNameEn = ?, LastNameEn = ?, Branch = ?, IsAdmin = ?, RoleDefault = ?, Mobile1 = ?, UpdatedAt = CURRENT_TIMESTAMP
                WHERE ID = ?""",
                         (username, email, first_name_kh, last_name_kh, first_name_en, last_name_en, branch, is_admin, role_default, mobile1, id))
            conn.commit()
        return redirect(url_for('list_users'))

    return render_template('/users/edit_user.html', user=user, branches=branches)


@app.route('/users/delete/<int:id>', methods=['POST'])
@login_required
def delete_user(id):
    if current_user.is_admin == 0:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    with get_db_connection() as conn:
        conn.execute("DELETE FROM users WHERE ID = ?", (id,))
        conn.commit()
    return redirect(url_for('list_users'))


@app.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin:
        with get_db_connection() as conn:
            employee = conn.execute(
                "SELECT e.ID FROM employees e WHERE e.user_id = ?", (current_user.id,)).fetchone()
            if employee:
                return redirect(url_for('render_dashboard_employees', employee_id=employee[0]))
            flash("Employee not found!", "danger")
            return redirect(url_for('render_dashboard_employees', employee_id=current_user.id))
    return render_dashboard(current_user.id)


@app.route('/dashboard/<int:id>')
@login_required
def dashboard_with_id(id):
    if current_user.id != id and not current_user.is_admin:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    return render_dashboard_employees(id)


@app.route('/dashboard/employee/<int:employee_id>')
@login_required
def render_dashboard_employees(employee_id):
    with get_db_connection() as conn:
        # Fetch the specific employee's data
        employee = conn.execute(
            "SELECT e.ID, e.Name, e.Age, e.Salary, e.Branch, p.PositionName AS Position, d.Name AS Department "
            "FROM employees e "
            "LEFT JOIN positions p ON e.position_id = p.ID "
            "LEFT JOIN departments d ON p.department_id = d.ID "
            "WHERE e.ID = ?",
            (employee_id,)
        ).fetchone()

        if not employee:
            flash("Employee not found!", "danger")
            return redirect(url_for('dashboard', id=current_user.id))

        employee_data = {
            'ID': employee['ID'] if employee['ID'] is not None else '',
            'Name': employee['Name'] if employee['Name'] is not None else '',
            'Age': employee['Age'] if employee['Age'] is not None else '',
            'Salary': employee['Salary'] if employee['Salary'] is not None else '',
            'Branch': employee['Branch'] if employee['Branch'] is not None else '',
            'Position': employee['Position'] if employee['Position'] is not None else '',
            'Department': employee['Department'] if employee['Department'] is not None else ''
        }

        # Get Payroll by employee ID
        total_salary = conn.execute(
            "SELECT SUM(p.base_salary + p.bonus - p.deductions - p.tax) AS total_salary "
            "FROM payroll p WHERE p.employee_id = ?",
            (employee['ID'],)
        ).fetchone()[0] or 0

    return render_template(
        'employees/employee_dashboard.html',
        employee=employee_data,
        total_salary=total_salary
    )


def render_dashboard(user_id):
    timeout_threshold = 15  # minutes

    with get_db_connection() as conn:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_employees = conn.execute(
            "SELECT COUNT(*) FROM employees").fetchone()[0]
        average_age = conn.execute(
            "SELECT AVG(Age) FROM employees").fetchone()[0] or 0
        total_salary = conn.execute(
            "SELECT SUM(Salary) FROM employees").fetchone()[0] or 0

        # Employee count and total salary by branch
        branch_data = conn.execute("""
            SELECT Branch, COUNT(*) AS employee_count, SUM(Salary) AS total_salary
            FROM employees
            GROUP BY Branch
        """).fetchall()

        branch_names = [row['Branch'] for row in branch_data]
        branch_counts = [row['employee_count'] for row in branch_data]
        branch_salaries = [row['total_salary'] for row in branch_data]

        total_branches = len(branch_names)
        total_payroll = total_salary

        # Fetch online users
        online_users = conn.execute('''
            SELECT u.ID AS user_id, u.UserName, u.Email, ou.last_active_time
            FROM online_users ou
            JOIN users u ON ou.user_id = u.ID
            WHERE strftime('%s', 'now') - strftime('%s', ou.last_active_time) <= ? * 60
        ''', (timeout_threshold,)).fetchall()

    return render_template(
        'dashboard.html',
        total_users=total_users,
        total_employees=total_employees,
        average_age=average_age,
        total_salary=total_salary,
        total_branches=total_branches,
        total_payroll=total_payroll,
        branch_names=branch_names,
        branch_counts=branch_counts,
        branch_salaries=branch_salaries,
        online_users=online_users
    )


@app.route('/users/roles', methods=['GET'])
def get_roles():

    return render_template('/users/roles.html')


@app.route('/users', methods=['GET'])
@login_required
def list_users():
    if current_user.is_admin == 0:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    with get_db_connection() as conn:
        users = conn.execute("SELECT * FROM users ORDER BY ID DESC").fetchall()
        last_user = users[0] if users else None
        notifications = [
            {"title": "New User Added",
                "message": f"User {last_user['username']} has been added."} if last_user else None
        ]

    return render_template('/users/users.html', users=users, notifications=notifications)


@app.route('/users/<int:id>')
@login_required
def view_user(id):
    if current_user.is_admin == 0:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    with get_db_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE ID = ?", (id,)).fetchone()
    if user:
        return render_template('/users/view_user.html', user=user)
    else:
        return "User not found", 404


@app.route('/users/search', methods=['GET'])
@login_required
def search_users():
    if current_user.is_admin == 0:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))
    query = request.args.get('query', '')
    with get_db_connection() as conn:
        users = conn.execute(
            "SELECT * FROM users WHERE UserName LIKE ?", (f'%{query}%',)
        ).fetchall()
    return render_template('/users/users.html', users=users)


@app.route('/employees')
@login_required
def list_employees():
    with get_db_connection() as conn:
        employees = conn.execute(
            "SELECT * FROM employees ORDER BY id DESC").fetchall()
        positions = conn.execute("SELECT * FROM positions").fetchall()
        departments = conn.execute("SELECT * FROM departments").fetchall()
        last_employee = employees[0] if employees else None
        notifications_employees = [
            {"title": "New Employee Added",
             "message": f"Employee {last_employee['name']} has been added."} if last_employee else None
        ]

    return render_template('/employees/employees.html', employees=employees, notifications_employees=notifications_employees,
                           positions=positions, departments=departments)


@app.route('/employees/<string:username>')
@login_required
def view_employee_details(username):
    # Check if the current user has the correct role (admin)
    if current_user.is_admin == 0 or current_user.role_default != 20:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    with get_db_connection() as conn:
        # Fetch the employee by username
        employee = conn.execute(
            "SELECT * FROM employees WHERE username = ?", (username,)).fetchone()

        if employee is None:
            # If no employee is found, return a 404 error
            abort(404, description="Employee not found")

        # Fetch related data (position, department)
        position = conn.execute(
            "SELECT * FROM positions WHERE id = ?", (employee['position_id'],)).fetchone()
        department = conn.execute(
            "SELECT * FROM departments WHERE id = ?", (employee['department_id'],)).fetchone()

    # Render employee details dashboard page
    return render_template('/employees/employees.html',
                           employee=employee,
                           position=position,
                           department=department)


@app.route('/employees/search', methods=['GET'])
@login_required
def search_employees():

    query = request.args.get('query', '')

    with get_db_connection() as conn:
        employees = conn.execute(
            "SELECT * FROM employees WHERE name LIKE ?", (f'%{query}%',)
        ).fetchall()

    return render_template('/employees/employees.html', employees=employees)


@app.route('/employees/add', methods=['GET', 'POST'])
@login_required
def add_employee():
    branches = []
    users = []
    positions = []

    with get_db_connection() as conn:
        branches = conn.execute("SELECT * FROM branches").fetchall()
        users = conn.execute(
            "SELECT id, UserName FROM users").fetchall()  # Fetch users
        positions = conn.execute("SELECT * FROM positions").fetchall()

    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        department = request.form['department']
        salary = request.form['salary']
        position_id = request.form['position_id']
        joining_date = request.form['joining_date']
        status = request.form['status']
        branch = request.form['branch']
        user_id = request.form['user_id']
        phone_number = request.form['phone_number']
        email = request.form['email']
        address = request.form['address']
        emergency_contact_name = request.form['emergency_contact_name']
        emergency_contact_phone = request.form['emergency_contact_phone']

        with get_db_connection() as conn:
            conn.execute(
                """INSERT INTO employees (name, age, department, salary, position_id, joining_date, status,
                                           branch, user_id, phone_number, email, address, emergency_contact_name, emergency_contact_phone)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, age, department, salary, position_id, joining_date, status, branch, user_id,
                 phone_number, email, address, emergency_contact_name, emergency_contact_phone)
            )
            conn.commit()
        return redirect(url_for('list_employees'))

    # Pass users and branches to template
    return render_template('/employees/add_employee.html', branches=branches, users=users, positions=positions)


@app.route('/employees/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_employee(id):
    with get_db_connection() as conn:
        employee = conn.execute(
            "SELECT * FROM employees WHERE id = ?", (id,)).fetchone()
        branches = conn.execute("SELECT * FROM branches").fetchall()
        positions = conn.execute("SELECT * FROM positions").fetchall()

    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        department = request.form['department']
        salary = request.form['salary']
        position_id = request.form['position_id']
        joining_date = request.form['joining_date']
        status = request.form['status']
        branch = request.form['branch']
        phone_number = request.form['phone_number']
        email = request.form['email']
        address = request.form['address']
        emergency_contact_name = request.form['emergency_contact_name']
        emergency_contact_phone = request.form['emergency_contact_phone']

        with get_db_connection() as conn:
            conn.execute(
                """UPDATE employees SET name = ?, age = ?, department = ?, salary = ?, position_id = ?, joining_date = ?,
                   status = ?, branch = ?, phone_number = ?, email = ?, address = ?, emergency_contact_name = ?, emergency_contact_phone = ?
                   WHERE id = ?""",
                (name, age, department, salary, position_id, joining_date, status, branch,
                 phone_number, email, address, emergency_contact_name, emergency_contact_phone, id)
            )
            conn.commit()
        return redirect(url_for('list_employees'))

    return render_template('/employees/edit_employee.html', employee=employee, branches=branches, positions=positions)


@app.route('/employees/delete/<int:id>', methods=['POST'])
@login_required
def delete_employee(id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM employees WHERE id = ?", (id,))
        conn.commit()
    return redirect(url_for('list_employees'))


@app.route('/employees/<int:id>')
@login_required
def view_employee(id):
    with get_db_connection() as conn:
        employee = conn.execute(
            "SELECT * FROM employees WHERE id = ?", (id,)).fetchone()
    if employee:
        return render_template('/employees/view_employee.html', employee=employee)
    else:
        return "Employee not found", 404


@app.route('/branches')
@login_required
def list_branches():
    conn = get_db_connection()
    branches = conn.execute('SELECT * FROM branches').fetchall()
    conn.close()
    return render_template('/branches/branches.html', branches=branches)


@app.route('/branches/add', methods=['GET', 'POST'])
@login_required
def add_branch():
    if request.method == 'POST':
        description = request.form['description']
        branch = request.form['branch']
        branch_manager = request.form['branch_manager']
        contact_number = request.form['contact_number']
        address = request.form['address']
        register_date = request.form['register_date']
        local_description = request.form['local_description']
        local_address = request.form['local_address']
        local_branch_manager = request.form['local_branch_manager']
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO branches (Description, Branch, BranchManagerName, ContactNumber, Address,
                                      RegisterDate, LocalDescription, LocalAddress, LocalBranchManagerName)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                         (description, branch, branch_manager, contact_number, address,
                          register_date, local_description, local_address, local_branch_manager,
                          ))
            conn.commit()
        return redirect(url_for('list_branches'))
    return render_template('/branches/add_branch.html')

# Route to update a branch


@app.route('/branches/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_branch(id):
    conn = get_db_connection()
    branch = conn.execute(
        'SELECT * FROM branches WHERE ID = ?', (id,)).fetchone()
    if request.method == 'POST':
        status = request.form['status']
        branch_manager = request.form['branch_manager']
        address = request.form['address']
        description = request.form['description']
        branch_name = request.form['branch']
        contact_number = request.form['contact_number']
        conn.execute('''
            UPDATE branches
            SET Status = ?, BranchManagerName = ?, Address = ?, Description = ?, Branch = ?, ContactNumber = ?, UpdatedAt = CURRENT_TIMESTAMP
            WHERE ID = ?''',
                     (status, branch_manager, address, description, branch_name, contact_number, id))
        conn.commit()
        conn.close()
        return redirect(url_for('list_branches'))

    conn.close()
    return render_template('/branches/edit_branch.html', branch=branch)

# Route to delete a branch


@app.route('/branches/delete/<int:id>', methods=['POST'])
@login_required
def delete_branch(id):
    with get_db_connection() as conn:
        conn.execute('DELETE FROM branches WHERE ID = ?', (id,))
        conn.commit()
    return redirect(url_for('list_branches'))


@app.route('/branches/<int:id>')
@login_required
def view_branch(id):
    with get_db_connection() as conn:
        branch = conn.execute(
            "SELECT * FROM branches WHERE ID = ?", (id,)).fetchone()
    if branch:
        return render_template('/branches/view_branch.html', branch=branch)
    else:
        return "Branch not found", 404


@app.route('/branches/search', methods=['GET'])
@login_required
def search_branches():
    query = request.args.get('query', '')
    with get_db_connection() as conn:
        branches = conn.execute(
            "SELECT * FROM branches WHERE Branch LIKE ?", (f'%{query}%',)
        ).fetchall()
    return render_template('/branches/branches.html', branches=branches)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
