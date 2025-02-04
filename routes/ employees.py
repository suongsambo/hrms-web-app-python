from flask import Blueprint, render_template, redirect, url_for, request
from models import Employee
from database import db

employees_bp = Blueprint('employees', __name__)


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


@app.route('/employees/<int:id>')
def view_employee(id):
    with get_db_connection() as conn:
        employee = conn.execute("SELECT * FROM employees WHERE id = ?", (id,)).fetchone()

    if employee:
        return render_template('/employees/view_employee.html', employee=employee)
    else:
        return "Employee not found", 404

