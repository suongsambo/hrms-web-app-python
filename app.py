from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import hashlib
import os

app = Flask(__name__)
app.secret_key = "your_secret_key"

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database/hr_management.db')

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database and create tables if they don't exist."""
    with get_db_connection() as conn:
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
                RoleDefault TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                department TEXT NOT NULL,
                salary REAL NOT NULL
            )
        ''')
        conn.commit()

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        with get_db_connection() as conn:
            try:
                conn.execute('''
                    INSERT INTO users (UserName, Password, Email)
                    VALUES (?, ?, ?)
                ''', (username, hashed_password, email))
                conn.commit()
                return redirect(url_for('index'))
            except sqlite3.IntegrityError:
                return render_template('username_or_email_exists.html')
                #  "Username or Email already exists. Try again."

    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = hashlib.sha256(request.form['password'].encode()).hexdigest()

    with get_db_connection() as conn:
        user = conn.execute('''
            SELECT * FROM users WHERE UserName = ? AND Password = ?
        ''', (username, password)).fetchone()

    if user:
        session['user'] = username
        return redirect(url_for('dashboard'))
    else:
        return render_template('404.html'), 404

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/users')
def users():
    with get_db_connection() as conn:
        users = conn.execute("SELECT * FROM users").fetchall()
    return render_template('/users/users.html', users=users)


@app.route('/users/add', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        email = request.form['email']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        branch = request.form['branch']
        is_admin = request.form.get('is_admin', 0)
        
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO users (UserName, Password, Email, FirstNameEn, LastNameEn, Branch, IsAdmin)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (username, password, email, first_name, last_name, branch, is_admin))
            conn.commit()
        return redirect(url_for('list_users'))
    return render_template('/users/add_user.html')

@app.route('/users/edit/<int:id>', methods=['GET', 'POST'])
def edit_user(id):
    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE ID = ?", (id,)).fetchone()
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        branch = request.form['branch']
        is_admin = request.form.get('is_admin', 0)
        
        with get_db_connection() as conn:
            conn.execute("""
                UPDATE users SET UserName = ?, Email = ?, FirstNameEn = ?, LastNameEn = ?, Branch = ?, IsAdmin = ?, UpdatedAt = CURRENT_TIMESTAMP
                WHERE ID = ?""",
                (username, email, first_name, last_name, branch, is_admin, id))
            conn.commit()
        return redirect(url_for('list_users'))
    
    return render_template('/users/edit_user.html', user=user)

@app.route('/users/delete/<int:id>', methods=['POST'])
def delete_user(id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM users WHERE ID = ?", (id,))
        conn.commit()
    return redirect(url_for('/users/list_users'))


@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html')


@app.route('/employees')
def list_employees():
    if 'user' not in session:
        return redirect(url_for('index'))

    with get_db_connection() as conn:
        employees = conn.execute("SELECT * FROM employees").fetchall()

    return render_template('/employees/employees.html', employees=employees)

@app.route('/employees/search', methods=['GET'])
def search_employees():
    if 'user' not in session:
        return redirect(url_for('index'))

    query = request.args.get('query', '')

    with get_db_connection() as conn:
        employees = conn.execute("SELECT * FROM employees WHERE name LIKE ?", ('%' + query + '%',)).fetchall()

    return render_template('/employees/employees.html', employees=employees)


@app.route('/employees/add', methods=['GET', 'POST'])
def add_employee():
    if 'user' not in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        department = request.form['department']
        salary = request.form['salary']

        with get_db_connection() as conn:
            conn.execute("INSERT INTO employees (name, age, department, salary) VALUES (?, ?, ?, ?)",
                         (name, age, department, salary))
            conn.commit()

        return redirect(url_for('list_employees'))

    return render_template('/employees/add_employee.html')

@app.route('/employees/edit/<int:id>', methods=['GET', 'POST'])
def edit_employee(id):
    if 'user' not in session:
        return redirect(url_for('index'))

    with get_db_connection() as conn:
        employee = conn.execute("SELECT * FROM employees WHERE id = ?", (id,)).fetchone()

    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        department = request.form['department']
        salary = request.form['salary']

        with get_db_connection() as conn:
            conn.execute("UPDATE employees SET name = ?, age = ?, department = ?, salary = ? WHERE id = ?",
                         (name, age, department, salary, id))
            conn.commit()

        return redirect(url_for('list_employees'))

    return render_template('/employees/edit_employee.html', employee=employee)

@app.route('/employees/delete/<int:id>', methods=['POST'])
def delete_employee(id):
    if 'user' not in session:
        return redirect(url_for('index'))

    with get_db_connection() as conn:
        conn.execute("DELETE FROM employees WHERE id = ?", (id,))
        conn.commit()

    return redirect(url_for('list_employees'))


@app.route('/employee/<int:id>')
def view_employee(id):
    with get_db_connection() as conn:
        employee = conn.execute("SELECT * FROM employees WHERE id = ?", (id,)).fetchone()

    if employee:
        return render_template('/employees/view_employee.html', employee=employee)
    else:
        return "Employee not found", 404


if __name__ == '__main__':
    init_db()
    app.run(debug=True)