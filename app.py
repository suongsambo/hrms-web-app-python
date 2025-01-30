# from flask import Flask, render_template, request, redirect, url_for, jsonify, session
# import sqlite3
# import hashlib

# app = Flask(__name__)
# app.secret_key = "your_secret_key"

# def get_db_connection():
#     conn = sqlite3.connect("database/hr_management.db")
#     conn.row_factory = sqlite3.Row
#     return conn

# @app.route('/')
# def index():
#     return render_template('login.html')

# @app.route('/login', methods=['POST'])
# def login():
#     username = request.form['username']
#     password = hashlib.sha256(request.form['password'].encode()).hexdigest()

#     conn = get_db_connection()
#     user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
#     conn.close()

#     if user:
#         session['user'] = username
#         return redirect(url_for('dashboard'))
#     else:
#         return "Invalid credentials. Try again."

# @app.route('/dashboard')
# def dashboard():
#     if 'user' not in session:
#         return redirect(url_for('index'))
#     return render_template('dashboard.html')

# @app.route('/employees', methods=['GET', 'POST'])
# def employees():
#     conn = get_db_connection()
#     if request.method == 'POST':
#         name = request.json['name']
#         age = request.json['age']
#         department = request.json['department']
#         salary = request.json['salary']
#         conn.execute("INSERT INTO employees (name, age, department, salary) VALUES (?, ?, ?, ?)", (name, age, department, salary))
#         conn.commit()
#         return jsonify({'message': 'Employee added successfully'}), 201
#     else:
#         employees = conn.execute("SELECT * FROM employees").fetchall()
#         conn.close()
#         return jsonify([dict(emp) for emp in employees])

# if __name__ == '__main__':
#     app.run(debug=True)










# from flask import Flask, render_template, request, redirect, url_for, session
# import sqlite3
# import hashlib

# app = Flask(__name__)
# app.secret_key = "your_secret_key"

# def get_db_connection():
#     conn = sqlite3.connect("database/hr_management.db")
#     conn.row_factory = sqlite3.Row
#     return conn

# @app.route('/')
# def index():
#     return render_template('login.html')

# @app.route('/register', methods=['GET', 'POST'])
# def register():
#     if request.method == 'POST':
#         username = request.form['username']
#         password = request.form['password']
#         hashed_password = hashlib.sha256(password.encode()).hexdigest()

#         conn = get_db_connection()
#         try:
#             conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
#             conn.commit()
#             conn.close()
#             return redirect(url_for('index'))
#         except sqlite3.IntegrityError:
#             conn.close()
#             return "Username already exists. Please choose a different username."
#     return render_template('register.html')

# @app.route('/login', methods=['POST'])
# def login():
#     username = request.form['username']
#     password = hashlib.sha256(request.form['password'].encode()).hexdigest()

#     conn = get_db_connection()
#     user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
#     conn.close()

#     if user:
#         session['user'] = username
#         return redirect(url_for('dashboard'))
#     else:
#         return "Invalid credentials. Try again."

# @app.route('/dashboard')
# def dashboard():
#     if 'user' not in session:
#         return redirect(url_for('index'))
#     return render_template('dashboard.html')

# @app.route('/employees', methods=['GET', 'POST'])
# def employees():
#     conn = get_db_connection()
#     if request.method == 'POST':
#         name = request.json['name']
#         age = request.json['age']
#         department = request.json['department']
#         salary = request.json['salary']
#         conn.execute("INSERT INTO employees (name, age, department, salary) VALUES (?, ?, ?, ?)", (name, age, department, salary))
#         conn.commit()
#         return jsonify({'message': 'Employee added successfully'}), 201
#     else:
#         employees = conn.execute("SELECT * FROM employees").fetchall()
#         conn.close()
#         return jsonify([dict(emp) for emp in employees])

# if __name__ == '__main__':
#     app.run(debug=True)




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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
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
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        with get_db_connection() as conn:
            try:
                conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
                conn.commit()
                return redirect(url_for('index'))
            except sqlite3.IntegrityError:
                return "Username already exists. Try again."

    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = hashlib.sha256(request.form['password'].encode()).hexdigest()

    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()

    if user:
        session['user'] = username
        return redirect(url_for('dashboard'))
    else:
        return render_template('404.html'), 404

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

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

    return render_template('employees.html', employees=employees)

@app.route('/employees/search', methods=['GET'])
def search_employees():
    if 'user' not in session:
        return redirect(url_for('index'))

    query = request.args.get('query', '')

    with get_db_connection() as conn:
        employees = conn.execute("SELECT * FROM employees WHERE name LIKE ?", ('%' + query + '%',)).fetchall()

    return render_template('employees.html', employees=employees)


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

    return render_template('add_employee.html')

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

    return render_template('edit_employee.html', employee=employee)

@app.route('/employees/delete/<int:id>', methods=['POST'])
def delete_employee(id):
    if 'user' not in session:
        return redirect(url_for('index'))

    with get_db_connection() as conn:
        conn.execute("DELETE FROM employees WHERE id = ?", (id,))
        conn.commit()

    return redirect(url_for('list_employees'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)