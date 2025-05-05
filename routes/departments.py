import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app

departments_bp = Blueprint('departments', __name__, url_prefix='/departments')


def get_db_connection():
    conn = sqlite3.connect(current_app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn


@departments_bp.route('/add', methods=['GET', 'POST'])
def create_department():
    if request.method != 'POST':
        return render_template('departments/add_department.html')

    name = request.form.get('name')
    description = request.form.get('description')

    if not name:
        flash('Department name is required', 'error')
        return redirect(url_for('departments.create_department'))

    with get_db_connection() as conn:
        conn.execute('''
            INSERT INTO departments(Name, Description)
            VALUES(?, ?)
        ''', (name, description))
        conn.commit()

    flash('Department created successfully', 'success')
    return redirect(url_for('departments.get_all_departments'))


@departments_bp.route('/')
def get_all_departments():
    with get_db_connection() as conn:
        departments = conn.execute('SELECT * FROM departments').fetchall()
    return render_template('departments/departments.html', departments=departments)


@departments_bp.route('/view/<int:id>')
def view_department(id):
    with get_db_connection() as conn:
        department = conn.execute(
            'SELECT * FROM departments WHERE id = ?', (id,)).fetchone()
    return render_template('departments/view_department.html', department=department)


@departments_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def update_department(id):
    with get_db_connection() as conn:
        department = conn.execute(
            'SELECT * FROM departments WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')

        if not name:
            flash('Department name is required', 'error')
            return redirect(url_for('departments.update_department', id=id))

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE departments
                SET Name= ?, Description= ?
                WHERE id= ?
            ''', (name, description, id))
            conn.commit()

        flash('Department updated successfully', 'success')
        return redirect(url_for('departments.get_all_departments'))

    return render_template('departments/edit_department.html', department=department)


@departments_bp.route('/delete/<int:id>', methods=['POST'])
def delete_department(id):
    with get_db_connection() as conn:
        conn.execute('DELETE FROM departments WHERE id = ?', (id,))
        conn.commit()

    flash('Department deleted successfully', 'success')
    return redirect(url_for('departments.get_all_departments'))
