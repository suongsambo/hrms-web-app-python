# views/branches.py or routes/branches.p
import sqlite3
from flask import Flask, flash
from config import Config
from flask import Blueprint, render_template, request, redirect, url_for
app = Flask(__name__)
app.config.from_object(Config)


def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn


zones_bp = Blueprint('zones', __name__, url_prefix='/zones')


@zones_bp.route('/')
def list_zones():
    with get_db_connection() as conn:
        zones = conn.execute('SELECT * FROM zones').fetchall()
    return render_template('/zones/list_zones.html', zones=zones)


@zones_bp.route('/add', methods=['GET', 'POST'])
def add_zone():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        with get_db_connection() as conn:
            conn.execute(
                'INSERT INTO zones (Name, Description) VALUES (?, ?)',
                (name, description)
            )
            conn.commit()
        flash('Zone added successfully!', 'success')
        return redirect(url_for('zones.list_zones'))
    return render_template('/zones/add_zone.html')


@zones_bp.route('/create', methods=['GET', 'POST'])
def create_zone():
    with get_db_connection() as conn:
        branches = conn.execute('SELECT * FROM branches').fetchall()

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        selected_branches = request.form.getlist('branches')
        if not name:
            flash('Zone name is required.', 'danger')
            return render_template('zones/create_zone.html', branches=branches)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO zones (Name, Description) VALUES (?, ?)',
                (name, description)
            )
            zone_id = cursor.lastrowid
            for branch_id in selected_branches:
                cursor.execute(
                    'INSERT INTO zone_branch (zone_id, branch_id) VALUES (?, ?)',
                    (zone_id, branch_id)
                )
            conn.commit()
        flash('Zone created and branches assigned successfully!', 'success')
        return redirect(url_for('zones.list_zones'))

    return render_template('zones/create_zone.html', branches=branches)


@zones_bp.route('/edit/<int:zone_id>', methods=['GET', 'POST'])
def edit_zone(zone_id):
    with get_db_connection() as conn:
        zone = conn.execute(
            'SELECT * FROM zones WHERE ID = ?', (zone_id,)).fetchone()
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        with get_db_connection() as conn:
            conn.execute(
                'UPDATE zones SET Name = ?, Description = ? WHERE ID = ?',
                (name, description, zone_id)
            )
            conn.commit()
        flash('Zone updated successfully!', 'success')
        return redirect(url_for('zones.list_zones'))
    return render_template('/zones/edit_zone.html', zone=zone)


@zones_bp.route('/delete/<int:zone_id>', methods=['POST'])
def delete_zone(zone_id):
    with get_db_connection() as conn:
        conn.execute('DELETE FROM zones WHERE ID = ?', (zone_id,))
        conn.commit()
    flash('Zone deleted successfully!', 'success')
    return redirect(url_for('zones.list_zones'))


@zones_bp.route('/<int:zone_id>/assign_branch', methods=['GET', 'POST'])
def assign_branch_to_zone(zone_id):
    with get_db_connection() as conn:
        zone = conn.execute(
            'SELECT * FROM zones WHERE ID = ?', (zone_id,)).fetchone()
        branches = conn.execute('SELECT * FROM branches').fetchall()
    if request.method == 'POST':
        branch_id = request.form['branch_id']
        with get_db_connection() as conn:
            conn.execute(
                'INSERT INTO zone_branch (zone_id, branch_id) VALUES (?, ?)',
                (zone_id, branch_id)
            )
            conn.commit()
        flash('Branch assigned to zone successfully!', 'success')
        return redirect(url_for('zones.list_zones'))
    return render_template('/zones/assign_branch_to_zone.html', zone=zone, branches=branches)
