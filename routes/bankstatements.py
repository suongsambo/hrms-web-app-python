
from flask import Blueprint, render_template, request, redirect, url_for, flash
from typing import Union
import sqlite3
from flask import Flask
from config import Config
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required
app = Flask(__name__)
app.config.from_object(Config)


def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn


bankstatements_bp = Blueprint(
    'bankstatements', __name__, url_prefix='/bankstatements')


@bankstatements_bp.route('/')
@login_required
def get_all_bankstatements():

    with get_db_connection() as conn:
        bankstatements = conn.execute('SELECT * FROM bankstatement').fetchall()
    return render_template('/bankstatements/view_bankstatements.html', bankstatements=bankstatements)


@bankstatements_bp.route('/add', methods=['GET', 'POST'])
@login_required
def create_bankstatement():
    if request.method == 'GET':
        with get_db_connection() as conn:
            employees = conn.execute(
                'SELECT id, name FROM employees').fetchall()
        return render_template('/bankstatements/add_bankstatement.html', employees=employees)

    employee_id = request.form.get('employee_id')
    employee_name = request.form.get('employee_name')
    account_name = request.form.get('account_name')
    account_number = request.form.get('account_number')
    bank_name = request.form.get('bank_name')
    salary = request.form.get('salary')
    transaction_date = request.form.get('transaction_date')
    transaction_type = request.form.get('transaction_type')

    with get_db_connection() as conn:
        conn.execute('''
            INSERT INTO bankstatement(employee_id, employee_name, account_name, account_number, bank_name, salary, transaction_date, transaction_type)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        ''', (employee_id, employee_name, account_name, account_number, bank_name, salary, transaction_date, transaction_type))
        conn.commit()

    flash('Bank statement created successfully', 'success')
    return redirect(url_for('bankstatements.get_all_bankstatements'))


@bankstatements_bp.route('/view/<int:id>')
@login_required
def view_bankstatement(id):

    with get_db_connection() as conn:
        bankstatement = conn.execute(
            'SELECT * FROM bankstatement WHERE id = ?', (id,)).fetchone()
    return render_template('/bankstatements/view_bankstatement.html', bankstatement=bankstatement)


@bankstatements_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def update_bankstatement(id):
    with get_db_connection() as conn:
        bankstatement = conn.execute(
            'SELECT * FROM bankstatement WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        employee_id = request.form.get('employee_id')
        employee_name = request.form.get('employee_name')
        account_name = request.form.get('account_name')
        account_number = request.form.get('account_number')
        bank_name = request.form.get('bank_name')
        salary = request.form.get('salary')
        transaction_date = request.form.get('transaction_date')
        transaction_type = request.form.get('transaction_type')

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE bankstatement
                SET employee_id= ?, employee_name= ?, account_name= ?, account_number= ?, bank_name= ?, salary= ?, transaction_date= ?, transaction_type= ?
                WHERE id= ?
            ''', (employee_id, employee_name, account_name, account_number, bank_name, salary, transaction_date, transaction_type, id))
            conn.commit()

        flash('Bank statement updated successfully', 'success')
        return redirect(url_for('bankstatements.get_all_bankstatements'))

    return render_template('/bankstatements/edit_bankstatement.html', bankstatement=bankstatement)


@bankstatements_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_bankstatement(id):
    with get_db_connection() as conn:
        conn.execute('DELETE FROM bankstatement WHERE id = ?', (id,))
        conn.commit()

    flash('Bank statement deleted successfully', 'success')
    return redirect(url_for('bankstatements.get_all_bankstatements'))
