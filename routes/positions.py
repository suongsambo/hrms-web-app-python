import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required

positions_bp = Blueprint('positions', __name__, url_prefix='/positions')


def get_db_connection():
    # Use current_app here!
    conn = sqlite3.connect(current_app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn


@positions_bp.route('/add', methods=['GET', 'POST'])
def create_position():
    with get_db_connection() as conn:
        departments = conn.execute('SELECT * FROM departments').fetchall()

    if request.method == 'POST':
        position_name = request.form.get('position_name')
        description = request.form.get('description')
        department_id = request.form.get('department_id')

        if not position_name:
            flash('Position name is required', 'error')
            return redirect(url_for('positions.create_position'))

        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO positions(PositionName, Description, department_id)
                VALUES(?, ?, ?)
            ''', (position_name, description, department_id))
            conn.commit()

        flash('Position created successfully', 'success')
        return redirect(url_for('positions.get_all_positions'))

    return render_template('positions/add_position.html', departments=departments)


@positions_bp.route('/')
@login_required
def get_all_positions():
    with get_db_connection() as conn:
        positions = conn.execute('SELECT * FROM positions').fetchall()
    return render_template('positions/positions.html', positions=positions)


@positions_bp.route('/view/<int:id>')
@login_required
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
    return render_template('positions/view_position.html', position=position, employees=employees)


@positions_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
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
            return redirect(url_for('positions.update_position', id=id))

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE positions
                SET PositionName = ?, Description = ?, department_id = ?
                WHERE ID = ?
            ''', (position_name, description, department_id, id))
            conn.commit()

        flash('Position updated successfully', 'success')
        return redirect(url_for('positions.get_all_positions'))

    return render_template('positions/edit_position.html', position=position, departments=departments)


@positions_bp.route('/delete/<int:id>', methods=['POST'])
def delete_position(id):
    with get_db_connection() as conn:
        conn.execute('DELETE FROM positions WHERE ID = ?', (id,))
        conn.commit()

    flash('Position deleted successfully', 'success')
    return redirect(url_for('positions.get_all_positions'))
