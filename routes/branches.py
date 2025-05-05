# views/branches.py or routes/branches.p
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


branches_bp = Blueprint('branches', __name__, url_prefix='/branches')


@branches_bp.route('/')
@login_required
def list_branches():
    conn = get_db_connection()
    branches = conn.execute('SELECT * FROM branches').fetchall()
    conn.close()
    return render_template('/branches/branches.html', branches=branches)


@branches_bp.route('/add', methods=['GET', 'POST'])
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
                INSERT INTO branches(Description, Branch, BranchManagerName, ContactNumber, Address,
                                      RegisterDate, LocalDescription, LocalAddress, LocalBranchManagerName)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                         (description, branch, branch_manager, contact_number, address,
                          register_date, local_description, local_address, local_branch_manager))
            conn.commit()
        return redirect(url_for('branches.list_branches'))
    return render_template('/branches/add_branch.html')


@branches_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
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
            SET Status= ?, BranchManagerName= ?, Address= ?, Description= ?, Branch= ?, ContactNumber= ?, UpdatedAt=CURRENT_TIMESTAMP
            WHERE ID= ?''',
                     (status, branch_manager, address, description, branch_name, contact_number, id))
        conn.commit()
        conn.close()
        return redirect(url_for('branches.list_branches'))
    conn.close()
    return render_template('/branches/edit_branch.html', branch=branch)


@branches_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_branch(id):
    with get_db_connection() as conn:
        conn.execute('DELETE FROM branches WHERE ID = ?', (id,))
        conn.commit()
    return redirect(url_for('branches.list_branches'))


@branches_bp.route('/<int:id>')
@login_required
def view_branch(id):
    with get_db_connection() as conn:
        branch = conn.execute(
            'SELECT * FROM branches WHERE ID = ?', (id,)).fetchone()
    if branch:
        return render_template('/branches/view_branch.html', branch=branch)
    else:
        return "Branch not found", 404


@branches_bp.route('/search')
@login_required
def search_branches():

    query = request.args.get('query', '')
    with get_db_connection() as conn:
        branches = conn.execute(
            "SELECT * FROM branches WHERE Branch LIKE ?", (f'%{query}%',)
        ).fetchall()
    return render_template('/branches/branches.html', branches=branches)
