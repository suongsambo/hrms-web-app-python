

# from flask import Flask, request, render_template, redirect, url_for
import base64
from flask import Flask, Response, render_template, flash, redirect, url_for, request, session, send_from_directory, jsonify, send_file
import sqlite3
import hashlib
import os
import math
import json
import pyotp
import requests
import shutil
import glob
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from config import Config
from flask_socketio import SocketIO, emit, join_room, leave_room, send
import time  # Make sure this is the standard time module
from datetime import datetime, timedelta
from typing import Optional
import eventlet
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from typing import Union
from flask_caching import Cache
from db import init_db

app = Flask(__name__)

app.config.from_object(Config)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")
cache = Cache(config={'CACHE_TYPE': 'simple'})
eventlet.monkey_patch()
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# def allowed_file(filename):
#     return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


class User(UserMixin):
    def __init__(self, id: int, username: str, password: str, email: str,
                 branch: Optional[str] = None, employee_id: Optional[int] = None, is_admin: bool = False,
                 role_default: Optional[int] = 0, image_data: Optional[bytes] = None,
                 zone_id: Optional[int] = None):
        self.id = id
        self.username = username
        self.password = password
        self.email = email
        self.branch = branch
        self.employee_id = employee_id
        self.is_admin = is_admin
        self.role_default = role_default
        self.image_data = image_data
        self.zone_id = zone_id

    def get_id(self):
        """Override get_id method to work with Flask-Login."""
        return str(self.id)

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@app.route('/clear_session')
def clear_session():
    session.clear()  # Clears the session data
    return "Session cleared!"


@app.route('/clear_cache')
def clear_cache():
    cache.clear()  # Clears the cache
    return "Cache cleared!"


@login_manager.user_loader
def load_user(user_id):
    with get_db_connection() as conn:
        user_data = conn.execute(
            'SELECT * FROM users WHERE ID = ?', (user_id,)).fetchone()
        if user_data:
            # Fetch the employee ID associated with the user
            employee = conn.execute(
                'SELECT id FROM employees WHERE user_id = ?', (user_id,)).fetchone()
            employee_id = employee['id'] if employee else None

            return User(
                id=user_data['ID'],
                username=user_data['UserName'],
                password=user_data['Password'],
                email=user_data['Email'],
                branch=user_data['Branch'],
                is_admin=user_data['IsAdmin'],
                role_default=user_data['RoleDefault'],
                image_data=user_data['Image'],
                employee_id=employee_id,
                zone_id=user_data['ZoneID']
            )
        return None


@socketio.on("message")
def handle_message(msg):
    print(f"Message: {msg}")
    send(msg, broadcast=True)  # Broadcast message to all clients


def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn


# Remove temp file
def clear_pycache(directory='.'):
    for root, dirs, files in os.walk(directory):
        for dir_name in dirs:
            if dir_name == '__pycache__':
                dir_path = os.path.join(root, dir_name)
                print(f"Removing {dir_path}")
                shutil.rmtree(dir_path)


clear_pycache()


def get_holidays(year: int):
    holidays = [
        {"label": datetime(year, 1, 1).strftime('%Y-%m-%d'),
         "value": "ទិវាចូលឆ្នាំសាកល"},
        {"label": datetime(year, 2, 7).strftime('%Y-%m-%d'),
         "value": "ទិវាជ័យជម្នះលើរបបប្រល័យពូជសាសន៍"},
        {"label": datetime(year, 3, 8).strftime('%Y-%m-%d'),
         "value": "ទិវាអន្តរជាតិនារី"},
        {"label": datetime(year, 5, 1).strftime('%Y-%m-%d'),
         "value": "ទិវាពលកម្មអន្តរជាតិ"},
        {"label": datetime(year, 4, 14).strftime('%Y-%m-%d'),
         "value": "ពិធីបុណ្យចូលឆ្នាំថ្មីប្រពៃណីជាតិ"},
        {"label": datetime(year, 4, 15).strftime('%Y-%m-%d'),
         "value": "ពិធីបុណ្យចូលឆ្នាំថ្មីប្រពៃណីជាតិ"},
        {"label": datetime(year, 4, 16).strftime('%Y-%m-%d'),
         "value": "ពិធីបុណ្យចូលឆ្នាំថ្មីប្រពៃណីជាតិ"},
        {"label": datetime(year, 5, 1).strftime('%Y-%m-%d'),
         "value": "ទិវាពលកម្មអន្តរជាតិ"},
        {"label": datetime(year, 5, 14).strftime(
            '%Y-%m-%d'), "value": "ព្រះរាជពិធីបុណ្យចម្រើនព្រះជន្ម ព្រះករុណា ព្រះបាទសម្តេចព្រះបរមនាថ នរោត្តម សីហមុនី"},
        {"label": datetime(year, 5, 15).strftime(
            '%Y-%m-%d'), "value": "ព្រះរាជពិធីច្រត់ព្រះនង្គ័ល"},
        {"label": datetime(year, 6, 18).strftime(
            '%Y-%m-%d'), "value": "ព្រះរាជពិធីបុណ្យចម្រើនព្រះជន្ម សម្តេចព្រះមហាក្សត្រី ព្រះវររាជមាតា នរោត្តម មុនិនាថ​ សីហនុ"},
        {"label": datetime(year, 9, 24).strftime('%Y-%m-%d'),
         "value": "ទិវាប្រកាសរដ្ឋធម្មនុញ្ញ"},
        {"label": datetime(year, 9, 21).strftime('%Y-%m-%d'),
         "value": "ពិធីបុណ្យភ្ផុំបិណ្ឌ"},
        {"label": datetime(year, 9, 22).strftime('%Y-%m-%d'),
         "value": "ពិធីបុណ្យភ្ផុំបិណ្ឌ"},
        {"label": datetime(year, 9, 23).strftime('%Y-%m-%d'),
         "value": "ពិធីបុណ្យភ្ផុំបិណ្ឌ"},
        {"label": datetime(year, 10, 15).strftime(
            '%Y-%m-%d'), "value": "ទិវាប្រារព្ឋពិធីគោរពព្រះវិញ្ញាណក្ខន្ឋ ព្រះករុណា ព្រះបាទសម្តេចព្រះ នរោត្តម សីហនុ ព្រះមហាវីរក្សត្រ ព្រះវររាជបិតាឯករាជ្យ បូរណភាពទឹកដី និងឯកភាពជាតិខ្មែរ  'ព្រះបរមរតនកោដ្ឋ'"},
        {"label": datetime(year, 10, 29).strftime(
            '%Y-%m-%d'), "value": "ព្រះរាជពិធីគ្រងព្រះបរមរាជសម្បត្តិ របស់ ព្រះករុណា ព្រះបាទសម្តេចព្រះបរមនាថ នរោត្តម សីហមុនី ព្រះមហាក្សត្រនៃព្រះរាជាណាចក្រកម្ពុជា"},
        {"label": datetime(year, 11, 9).strftime('%Y-%m-%d'),
         "value": "ពិធីបុណ្យឯករាជ្យជាតិ"},
        {"label": datetime(year, 11, 4).strftime(
            '%Y-%m-%d'), "value": "ព្រះរាជពិធីបុណ្យអុំទូក បណ្តែតប្រទីប និងសំពះព្រះខែអកអំបុក"},
        {"label": datetime(year, 11, 5).strftime(
            '%Y-%m-%d'), "value": "ព្រះរាជពិធីបុណ្យអុំទូក បណ្តែតប្រទីប និងសំពះព្រះខែអកអំបុក"},
        {"label": datetime(year, 11, 6).strftime(
            '%Y-%m-%d'), "value": "ព្រះរាជពិធីបុណ្យអុំទូក បណ្តែតប្រទីប និងសំពះព្រះខែអកអំបុក"},
        {"label": datetime(year, 12, 29).strftime(
            '%Y-%m-%d'), "value": "ទិវាសន្តិភាពនៅកម្ពុជា"},

    ]
    return holidays


def get_holiday_labels(year: int):
    holidays = get_holidays(year)
    return [holiday['label'] for holiday in holidays]


holidays = []


def load_holidays():
    try:
        with open('holidays.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save_holidays():
    with open('holidays.json', 'w') as f:
        json.dump(holidays, f)


@app.route('/add_holiday', methods=['GET', 'POST'])
def add_holiday():
    if request.method == 'POST':
        holiday_date = request.form['holiday_date']
        holiday_name = request.form['holiday_name']

        # Add new holiday
        holidays.append({
            "label": holiday_date,
            "value": holiday_name
        })
        # Save the updated holidays list to a file
        save_holidays()
        # Redirect to the page showing all holidays
        return redirect(url_for('show_holidays'))
    else:
        return render_template('holidays/add_holiday.html')


@app.route('/holidays')
def show_holidays():
    # Load holidays from the file
    holidays = load_holidays()
    # Get holidays for the current year
    holidays = get_holidays(datetime.now().year)
    holiday_labels = get_holiday_labels(datetime.now().year)
    return render_template('holidays/holidays.html', holidays=holidays, holiday_labels=holiday_labels)


# TODO: Backup database to a file Automatically


def backup_database_auto():
    backup_folder = os.path.dirname(app.config['BACKUP_FILE'])

    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)

    if os.path.exists(app.config['DATABASE']):
        current_datetime = datetime.now().strftime("%m-%d-%Y_%I-%M-%S")
        backup_file_with_date = f"backup_hr_management_{current_datetime}.db"
        backup_file_path = os.path.join(backup_folder, backup_file_with_date)

        try:
            shutil.copy2(app.config['DATABASE'], backup_file_path)
            print(f"✅ Database backup created: {backup_file_with_date}")
        except Exception as e:
            print(f"❌ Backup failed: {e}")
    else:
        print("❌ Database file not found!")


def start_scheduler():
    scheduler = BackgroundScheduler()

    scheduler.add_job(backup_database_auto, 'cron', day=1, hour=0, minute=0)

    def job_listener(event):
        if event.exception:
            print(f'❌ Job failed: {event.job_id}')
        else:
            print(f'✅ Job {event.job_id} executed successfully')

    scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    scheduler.start()

    print("📅 Scheduler started. Waiting for scheduled jobs...")

    try:
        while True:
            time.sleep(1)  # Ensure this is from the standard time module
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Stopping scheduler...")
        scheduler.shutdown()
        print("Scheduler shut down gracefully.")

    print("✅ Scheduler stopped.")


@app.route('/backup', methods=['GET', 'POST'])
@login_required
def backup_database_manual():
    # Ensure backup folder exists
    backup_folder = os.path.dirname(app.config['BACKUP_FILE'])

    if os.path.exists(app.config['DATABASE']):
        # Generate backup file name with current date and time
        current_datetime = datetime.now().strftime("%m-%d-%Y_%I-%M-%S")
        backup_file_with_date = f"backup_hr_management_{current_datetime}.db"
        backup_file_path = os.path.join(backup_folder, backup_file_with_date)

        shutil.copy2(app.config['DATABASE'], backup_file_path)

        # Flash a success message
        flash(
            f"Database backup created successfully! Your database has been backed up to {backup_file_with_date}.", "success")

        # Redirect to the backups management page
        return redirect(url_for('manage_backups'))
    else:
        # Flash an error message if the database is not found
        flash("Database file not found!", "error")
        return redirect(url_for('manage_backups'))


@app.route('/delete', methods=['POST'])
@login_required
def delete_backup():
    # Get the backup file name from the form submission
    backup_filename = request.form.get('backup')

    if backup_filename == 'hr_management.db':
        # Flash an error message if the file is the database itself
        flash("You cannot delete the database itself!", "error")
        # Ensure the backup file exists
    else:
        backup_folder = os.path.dirname(app.config['BACKUP_FILE'])
        backup_file_path = os.path.join(backup_folder, backup_filename)

        # Ensure the backup file exists
        if os.path.exists(backup_file_path):
            # Delete the backup file
            os.remove(backup_file_path)

            # Flash a success message
            flash(
                f"Backup file {backup_filename} deleted successfully!", "success")
        else:
            # Flash an error message if the file doesn't exist
            flash("Selected backup file not found!", "error")

            # Redirect to the backups management page
    return redirect(url_for('manage_backups'))


@app.route('/backup', methods=['GET', 'POST'])
@login_required
def backup_database():
    # Ensure backup folder exists
    backup_folder = os.path.dirname(app.config['BACKUP_FILE'])

    if os.path.exists(app.config['DATABASE']):
        # Generate backup file name with current date and time
        current_datetime = datetime.now().strftime("%m-%d-%Y_%I-%M-%S")
        backup_file_with_date = f"backup_hr_management_{current_datetime}.db"
        backup_file_path = os.path.join(backup_folder, backup_file_with_date)

        # Create backup by copying the database
        shutil.copy2(app.config['DATABASE'], backup_file_path)

        # Flash a success message
        flash(
            f"Database backup created successfully! Your database has been backed up to {backup_file_with_date}.", "success")

        # Redirect to the backups management page
        return redirect(url_for('manage_backups'))
    else:
        # Flash an error message if the database is not found
        flash("Database file not found!", "error")
        return redirect(url_for('manage_backups'))


@app.route('/restore', methods=['POST'])
@login_required
def restore_database():
    # Get the backup file name from the form submission
    backup_filename = request.form.get('backup')

    # Make sure the backup_filename is provided and valid
    if not backup_filename:
        flash("No backup file selected!", "error")
        # Redirect to the backups management page
        return redirect(url_for('manage_backups'))

    # Define the backup folder and the path to the backup file
    backup_folder = os.path.dirname(app.config['BACKUP_FILE'])
    backup_file_path = os.path.join(backup_folder, backup_filename)

    # Ensure the selected backup file exists
    if os.path.exists(backup_file_path):
        try:
            # Restore the selected backup to the original database location
            shutil.copy2(backup_file_path, app.config['DATABASE'])

            # Pass a success message to the template
            flash(
                f"Database restored successfully from {backup_filename}!", "success")
            # Redirect to the backups management page
            return redirect(url_for('manage_backups'))
        except Exception as e:
            flash(f"Error restoring database: {str(e)}", "error")
            # Redirect to the backups management page
            return redirect(url_for('manage_backups'))
    else:
        flash("Selected backup file not found!", "error")
        # Redirect to the backups management page
        return redirect(url_for('manage_backups'))


@app.route('/backups')
@login_required
def manage_backups():
    # Ensure backup folder exists
    backup_folder = os.path.dirname(app.config['BACKUP_FILE'])
    # List all backup files in the backup folder
    backup_files = [f for f in os.listdir(backup_folder) if f.endswith('.db')]
    return render_template('backups/manage_backups.html', backup_files=backup_files)


# Route to download the database file
@app.route('/download')
@login_required
def download_db():
    return send_file(app.config['DATABASE'], as_attachment=True)


@app.route('/filter-leaves')
def filter_leaves_by_ids():
    ids = request.args.get('ids')
    id_list = [int(i) for i in ids.split(',')] if ids else []
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('''
            SELECT *
            FROM leaves
            WHERE id IN ({seq})
            ORDER BY start_date DESC
        '''.format(seq=','.join(['?']*len(id_list))), id_list)
        leaves = cur.fetchall()
    return render_template('leaves.html', leaves=leaves)


@app.route('/zones/add', methods=['GET', 'POST'])
def add_zone():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']

        # Insert zone into the zones table
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO zones (Name, Description)
                VALUES (?, ?)
            ''', (name, description))
            conn.commit()

        flash('Zone added successfully!', 'success')
        return redirect(url_for('list_zones'))

    return render_template('/zones/add_zone.html')


@app.route('/zone/create', methods=['GET', 'POST'])
def create_zone():
    with get_db_connection() as conn:
        branches = conn.execute('SELECT * FROM branches').fetchall()

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        selected_branches = request.form.getlist(
            'branches')  # Get multiple branch IDs

        if not name:
            flash('Zone name is required.', 'danger')
            return render_template('zones/create_zone.html', branches=branches)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO zones (Name, Description) VALUES (?, ?)',
                (name, description)
            )
            zone_id = cursor.lastrowid  # Get the last inserted zone ID

            # Assign selected branches to the zone
            for branch_id in selected_branches:
                cursor.execute(
                    'INSERT INTO zone_branch (zone_id, branch_id) VALUES (?, ?)',
                    (zone_id, branch_id)
                )

            conn.commit()

        flash('Zone created and branches assigned successfully!', 'success')
        # Redirect to the zones list page
        return redirect(url_for('list_zones'))

    return render_template('zones/create_zone.html', branches=branches)


@app.route('/zones')
def list_zones():
    with get_db_connection() as conn:
        zones = conn.execute('SELECT * FROM zones').fetchall()

    return render_template('/zones/list_zones.html', zones=zones)


@app.route('/zones/edit/<int:zone_id>', methods=['GET', 'POST'])
def edit_zone(zone_id):
    with get_db_connection() as conn:
        zone = conn.execute(
            'SELECT * FROM zones WHERE ID = ?', (zone_id,)).fetchone()

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']

        # Update zone in the zones table
        with get_db_connection() as conn:
            conn.execute('''
                UPDATE zones
                SET Name = ?, Description = ?
                WHERE ID = ?
            ''', (name, description, zone_id))
            conn.commit()

        flash('Zone updated successfully!', 'success')
        return redirect(url_for('list_zones'))

    return render_template('/zones/edit_zone.html', zone=zone)


@app.route('/zones/delete/<int:zone_id>', methods=['POST'])
def delete_zone(zone_id):
    with get_db_connection() as conn:
        conn.execute('DELETE FROM zones WHERE ID = ?', (zone_id,))
        conn.commit()

    flash('Zone deleted successfully!', 'success')
    return redirect(url_for('list_zones'))


@app.route('/zone/<int:zone_id>/assign_branch', methods=['GET', 'POST'])
def assign_branch_to_zone(zone_id):
    with get_db_connection() as conn:
        zone = conn.execute(
            'SELECT * FROM zones WHERE ID = ?', (zone_id,)).fetchone()
        branches = conn.execute('SELECT * FROM branches').fetchall()

    if request.method == 'POST':
        branch_id = request.form['branch_id']

        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO zone_branch (zone_id, branch_id)
                VALUES (?, ?)
            ''', (zone_id, branch_id))
            conn.commit()

        flash('Branch assigned to zone successfully!', 'success')
        return redirect(url_for('list_zones'))

    return render_template('/zones/assign_branch_to_zone.html', zone=zone, branches=branches)


@app.route('/locations/add', methods=['GET', 'POST'])
@login_required
def add_location():
    if current_user.is_admin == 0:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        street = request.form['street']
        city = request.form['city']
        province = request.form['province']
        country = request.form['country']
        postal_code = request.form['postal_code']

        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO location(street, city, province, country, postal_code)
                VALUES(?, ?, ?, ?, ?)
            ''', (street, city, province, country, postal_code))
            conn.commit()

        return redirect(url_for('list_locations'))

    return render_template('/locations/add_location.html')


@app.route('/locations', methods=['GET'])
@login_required
def list_locations():
    with get_db_connection() as conn:
        locations = conn.execute("SELECT * FROM location").fetchall()
    return render_template('/locations/list_locations.html', locations=locations)


@app.route('/locations/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_location(id):
    if current_user.is_admin == 0:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    with get_db_connection() as conn:
        location = conn.execute(
            "SELECT * FROM location WHERE id = ?", (id,)).fetchone()

    if request.method == 'POST':
        street = request.form['street']
        city = request.form['city']
        province = request.form['province']
        country = request.form['country']
        postal_code = request.form['postal_code']

        with get_db_connection() as conn:
            conn.execute("""
                UPDATE location
                SET street = ?, city = ?, province = ?, country = ?, postal_code = ?
                WHERE id = ?
            """, (street, city, province, country, postal_code, id))
            conn.commit()

        return redirect(url_for('list_locations'))

    return render_template('/locations/edit_location.html', location=location)


@app.route('/locations/delete/<int:id>', methods=['POST'])
@login_required
def delete_location(id):
    if current_user.is_admin == 0:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    with get_db_connection() as conn:
        conn.execute("DELETE FROM location WHERE id = ?", (id,))
        conn.commit()

    return redirect(url_for('list_locations'))


@app.route('/locations/<int:id>', methods=['GET'])
@login_required
def view_location(id):
    with get_db_connection() as conn:
        location = conn.execute(
            "SELECT * FROM location WHERE id = ?", (id,)).fetchone()

    if location:
        return render_template('/locations/view_location.html', location=location)
    else:
        return "Location not found", 404


@app.route("/chat", methods=["GET", "POST"])
def chat():
    # Assuming the user is already logged in
    return render_template("chat.html", username=session.get("username", "Guest"))


# Route to fetch chat history
@app.route("/chat/history")
def chat_history():
    """Fetch last 50 messages from the chat room"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT username, timestamp FROM Message WHERE message IS NOT NULL ORDER BY timestamp DESC LIMIT 50'
        )
        messages = cursor.fetchall()

    # Send the messages to the frontend as JSON
    return jsonify([{
        "message": None,  # Indicate message is null
        "username": row[0],
        "timestamp": row[1].isoformat()  # Use ISO format
    } for row in messages[::-1]])  # Reverse to get chronological order


@socketio.on("connect")
def connect():
    print("Client connected")


@socketio.on("private_message")
def handle_private_message(data):
    sender = session.get("username", "Unknown")
    recipient = data.get("recipient")
    message = data.get("message")

    if recipient and message:
        # Emit private message to recipient
        emit("private_message", {
            "sender": sender,
            "message": message,
            "timestamp": datetime.utcnow().strftime("%H:%M:%S")
        }, room=recipient)
    else:
        print("Error: Recipient or message is missing.")
        # Emit private message to recipient

# Handle chat room join


@socketio.on("join_room")
def handle_join_room(data):
    room = data["room"]
    username = current_user.username
    join_room(room)
    emit("room_message", {
        "message": f"{username} has joined the room {room}"
    }, room=room)

    # Connect to the database and log the join event
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO Message (username, message) VALUES (?, ?)',
            (username, f"joined the room {room}")
        )
        conn.commit()

# Handle chat room leave


@socketio.on("leave_room")
def handle_leave_room(data):
    room = data["room"]
    username = session.get("username", "Guest")
    leave_room(room)
    emit("room_message", {
        "message": f"{username} has left the room {room}"
    }, room=room)

# Handle chat message


@socketio.on("chat_message")
def handle_chat_message(data):
    room = data["room"]
    username = current_user.username
    message = data["message"]
    emit("chat_message", {
        "username": username,
        "message": message,
        "timestamp": data["timestamp"]
    }, room=room)


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
            INSERT INTO bankstatement(employee_id, employee_name, account_name, account_number, bank_name, salary, transaction_date, transaction_type)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
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
                SET employee_id= ?, employee_name= ?, account_name= ?, account_number= ?, bank_name= ?, salary= ?, transaction_date= ?, transaction_type= ?
                WHERE id= ?
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
                INSERT INTO departments(Name, Description)
                VALUES(?, ?)
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
                SET Name= ?, Description= ?
                WHERE id= ?
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
                INSERT INTO positions(PositionName, Description, department_id)
                VALUES(?, ?, ?)
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
            JOIN positions p ON p.ID=e.position_id
            WHERE p.ID= ?
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
                SET PositionName= ?, Description= ?, department_id= ?
                WHERE ID= ?
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


@app.route('/leaves')
def view_leaves():
    if current_user.is_authenticated:
        if current_user.is_admin == 1:
            with get_db_connection() as conn:
                leaves = conn.execute('''
                    SELECT l.*, e.name AS employee_name, e.age, e.department
                    FROM leaves l
                    LEFT JOIN employees e ON l.employee_id = e.id
                ''').fetchall()

            return render_template('/leaves/view_leaves.html', leaves=leaves)

        if current_user.role_default == 140:
            # Fixed the syntax error here
            return redirect(url_for('filter_leaves_by_branch_name', branch_name=current_user.branch))

        if current_user.role_default == 145:
            return redirect(url_for('leaves_by_branch_and_spm'))

        if current_user.role_default == 35:
            return redirect(url_for('leaves_by_branch_and_ccc_category', branch_name=current_user.branch))

        if current_user.role_default == 180:
            return redirect(url_for('leaves_by_gm'))

        if current_user.role_default == 20:
            with get_db_connection() as conn:
                employee = conn.execute(
                    "SELECT id FROM employees WHERE user_id = ?", (current_user.id,)).fetchone()
                if employee:
                    return redirect(url_for('filter_leaves_by_employee_id', employee_id=employee[0]))

        # This block will run if none of the role conditions match
        with get_db_connection() as conn:
            leaves = conn.execute(
                'SELECT * FROM leaves WHERE employee_id = ?', (current_user.id,)).fetchall()
        return render_template('/leaves/view_leaves.html', leaves=leaves)

    else:
        # If the user is not authenticated, fetch all leaves (public access)
        with get_db_connection() as conn:
            leaves = conn.execute('SELECT * FROM leaves').fetchall()

        return render_template('/leaves/view_leaves.html', leaves=leaves)


@app.route('/leave/<int:leave_id>/users')
def users_for_leave(leave_id):
    # Combined query to get both leave details and users associated with the leave
    leave_query = '''
        SELECT l.id, e.name AS employee_name, e.branch AS branch_name,
               l.leave_type, l.start_date, l.end_date, l.reason, l.status,
               l.service_count, l.verified_by, l.approved_by, l.employee_id,
              l.requested_by,
               u.ID AS user_id, u.UserName, u.Email, u.Signature
        FROM leaves l
        INNER JOIN employees e ON l.employee_id = e.id
        LEFT JOIN user_leave ul ON l.id = ul.leave_id
        LEFT JOIN users u ON ul.user_id = u.ID
        WHERE l.id = ?
    '''

    with get_db_connection() as conn:
        result = conn.execute(leave_query, (leave_id,)).fetchall()

    # Process the Signature BLOBs and format the response
    leave_info = None
    users_list = []

    for row in result:
        leave_info = {
            'id': row['id'],
            'employee_name': row['employee_name'],
            'branch_name': row['branch_name'],
            'leave_type': row['leave_type'],
            'start_date': row['start_date'],
            'end_date': row['end_date'],
            'reason': row['reason'],
            'status': row['status'],
            'service_count': row['service_count'],
            'verified_by': row['verified_by'],
            'approved_by': row['approved_by'],
            'employee_id': row['employee_id'],
            'requested_by': row['requested_by'],
        }

        if row['user_id']:  # Only add user details if they exist
            user_dict = {
                'user_id': row['user_id'],
                'UserName': row['UserName'],
                'Email': row['Email'],
                'Signature': base64.b64encode(row['Signature']).decode('utf-8') if row['Signature'] else None
            }
            users_list.append(user_dict)

    return render_template('leaves/users_for_leave.html', leave=leave_info, users=users_list)


@app.route('/leave/users')
def users_for_all_leaves():
    # Query to get all leave details along with the associated employee data
    leave_query = '''
        SELECT l.id, e.name AS employee_name, e.branch AS branch_name,
               l.leave_type, l.start_date, l.end_date, l.reason, l.status,
               l.service_count, l.verified_by, l.approved_by, l.employee_id,
               l.spm_status, l.dd_status, l.manager_status, l.requested_by
        FROM leaves l
        INNER JOIN employees e ON l.employee_id = e.id
    '''

    # Query for users associated with the leave
    user_query = '''
        SELECT u.ID, u.UserName, u.Email, u.Signature
        FROM users u
        INNER JOIN user_leave ul ON u.ID = ul.user_id
        WHERE ul.leave_id = ?
    '''

    with get_db_connection() as conn:
        # Fetch all leave details
        leave_details_list = conn.execute(leave_query).fetchall()

        # Dictionary to hold leave details with associated users
        all_leaves_data = []

        # Iterate over each leave record
        for leave_details in leave_details_list:
            # Convert leave record to a dictionary
            leave_data = dict(leave_details)

            # Fetch the users associated with this leave
            users = conn.execute(user_query, (leave_data['id'],)).fetchall()

            # Process the Signature BLOBs for users
            users_list = []
            for user in users:
                user_dict = dict(user)
                if user_dict.get('Signature'):
                    user_dict['Signature'] = base64.b64encode(
                        user_dict['Signature']).decode('utf-8')
                users_list.append(user_dict)

            # Combine leave details and users data into a single object
            leave_data['users'] = users_list
            all_leaves_data.append(leave_data)

    # If no leaves found, return an error
    if not all_leaves_data:
        return "No leaves found", 404

    # Render template with all leaves and their associated users
    return render_template('leaves/all_users_for_leaves.html', leaves=all_leaves_data)


@app.route('/leave/<int:leave_id>/user/<int:user_id>')
def user_signature_for_leave(leave_id, user_id):
    query = '''
        SELECT u.ID, u.UserName, u.Email, u.Signature
        FROM users u
        INNER JOIN user_leave ul ON u.ID = ul.user_id
        WHERE ul.leave_id = ? AND u.ID = ?
    '''
    with get_db_connection() as conn:
        user = conn.execute(query, (leave_id, user_id)).fetchone()

    if user:
        # Convert the user row to a dictionary
        user_dict = dict(user)
        # Process the Signature BLOB
        if user_dict.get('Signature'):
            user_dict['Signature'] = base64.b64encode(
                user_dict['Signature']).decode('utf-8')
        return render_template('leaves/user_signature.html', user=user_dict)
    else:
        return "User not found for this leave."


@app.route('/leaves/employee/<int:employee_id>', methods=['GET'])
def filter_leaves_by_employee_id(employee_id):
    if not current_user.is_authenticated or current_user.role_default != 20:
        return redirect(url_for('access_denied'))

    leave_id = request.args.get('leave_id', type=int)

    try:
        with get_db_connection() as conn:
            # Fetch current user's signature from the database
            user_query = '''
                SELECT Signature
                FROM users
                WHERE ID = ?
            '''
            result = conn.execute(user_query, (current_user.id,)).fetchone()
            # If Signature is in binary, encode it to base64
            user_signature = base64.b64encode(result['Signature']).decode(
                'utf-8') if result and result['Signature'] else None

            # Now add the current user's info to the users_list
            current_user_info = {
                'user_id': current_user.id,
                'UserName': current_user.username,
                'Signature': user_signature  # The signature fetched from DB or None
            }

            # Add current user to the users list
            users_list = [current_user_info]

            if leave_id:  # If we are looking for specific leave info
                leave_query = '''
                    SELECT l.id, e.name AS employee_name, e.branch AS branch_name,
                           l.leave_type, l.start_date, l.end_date, l.reason, l.status,
                           l.service_count, l.verified_by, l.approved_by, l.employee_id,
                           l.requested_by,l.leave_hours, l.type_of_leave,
                           u.ID AS user_id, u.UserName, u.Email, u.Signature
                    FROM leaves l
                    INNER JOIN employees e ON l.employee_id = e.id
                    LEFT JOIN user_leave ul ON l.id = ul.leave_id
                    LEFT JOIN users u ON ul.user_id = u.ID
                    WHERE l.id = ?
                '''
                result = conn.execute(leave_query, (leave_id,)).fetchall()
                leave_info = None

                for row in result:
                    if not leave_info:
                        leave_info = {
                            'id': row['id'],
                            'employee_name': row['employee_name'],
                            'branch_name': row['branch_name'],
                            'leave_type': row['leave_type'],
                            'start_date': row['start_date'],
                            'end_date': row['end_date'],
                            'reason': row['reason'],
                            'status': row['status'],
                            'service_count': row['service_count'],
                            'verified_by': row['verified_by'],
                            'approved_by': row['approved_by'],
                            'employee_id': row['employee_id'],
                            'requested_by': row['requested_by'],
                            # <-- added this line
                            'leave_hours': row['leave_hours'],
                            'type_of_leave': row['type_of_leave']

                        }

                    if row['user_id']:
                        # If the user has a Signature, encode it
                        user_signature = base64.b64encode(row['Signature']).decode(
                            'utf-8') if row['Signature'] else None
                        user_info = {
                            'user_id': row['user_id'],
                            'UserName': row['UserName'],
                            'Email': row['Email'],
                            'Signature': user_signature
                        }
                        users_list.append(user_info)

                return render_template('leaves/users_for_leave.html', leave=leave_info, users=users_list)

            else:  # Show all leaves for employee
                leaves_query = '''
                    SELECT l.id, e.name AS employee_name, e.branch AS branch_name,
                           l.leave_type, l.start_date, l.end_date, l.reason, l.status,
                           l.service_count, l.verified_by, l.approved_by, l.employee_id,
                           l.spm_status, l.dd_status, l.manager_status, l.requested_by
                    FROM leaves l
                    INNER JOIN employees e ON l.employee_id = e.id
                    WHERE l.employee_id = ?
                '''
                leaves = conn.execute(leaves_query, (employee_id,)).fetchall()

                users = conn.execute("SELECT * FROM users").fetchall()

                return render_template('leaves/filter_leaves_by_employee.html', leaves=leaves, employee_id=employee_id, users=users)

    except sqlite3.DatabaseError as e:
        print(f"Database error occurred: {e}")
        return f"Database error: {e}", 500


@app.route('/leaves/ccc/<string:branch_name>', methods=['GET'])
def leaves_by_branch_and_ccc_category(branch_name):
    if not current_user.is_authenticated or current_user.role_default != 35:
        return redirect(url_for('access_denied'))

    if branch_name:
        query = '''
            SELECT
                l.id,
                e.name AS employee_name,
                e.branch AS branch_name,
                l.leave_type,
                l.start_date,
                l.end_date,
                l.reason,
                l.status,
                l.type_of_leave,
                l.verified_by,
                l.approved_by,
                l.leave_hours,
                l.service_count,
                l.requested_by
            FROM leaves l
            LEFT JOIN employees e ON l.employee_id = e.id
            WHERE e.branch = ? AND (l.category = 'S' OR l.type_of_leave = 'T')
        '''
        params = (branch_name,)
    else:
        query = '''
            SELECT
                l.id,
                e.name AS employee_name,
                e.branch AS branch_name,
                l.leave_type,
                l.start_date,
                l.end_date,
                l.reason,
                l.status,
                l.type_of_leave,
                l.verified_by,
                l.approved_by,
                l.leave_hours,
                l.service_count,
                l.requested_by
            FROM leaves l
            LEFT JOIN employees e ON l.employee_id = e.id
            WHERE l.category = 'S' OR l.type_of_leave = 'T'
        '''
        params = ()

    try:
        with get_db_connection() as conn:
            leaves = conn.execute(query, params).fetchall()
    except sqlite3.DatabaseError as e:
        return f"Database error: {e}", 500

    return render_template('leaves/leaves_ccc_verify.html', leaves=leaves, branch_name=branch_name)


@app.route('/leaves/spm', methods=['GET'])
def leaves_by_branch_and_spm():
    # Ensure user is authenticated and has the correct role
    if not current_user.is_authenticated or current_user.role_default != 145:
        return redirect(url_for('access_denied'))

    # Get the branch name from the query string
    branch_name = request.args.get('branch_name')
    zone_id = current_user.zone_id  # Get the user's zone ID

    if zone_id is None:
        flash("Zone ID not found for the current user!", "danger")
        return redirect(url_for('dashboard'))

    try:
        with get_db_connection() as conn:
            # Get the user's zone
            zone = conn.execute(
                "SELECT * FROM zones WHERE ID = ?", (zone_id,)).fetchone()
            if zone is None:
                flash("Zone not found!", "danger")
                return redirect(url_for('dashboard'))

            # Find branches in the current zone
            branches_in_zone = conn.execute(
                "SELECT b.ID, b.Branch FROM branches b "
                "JOIN zone_branch zb ON b.ID = zb.branch_id WHERE zb.zone_id = ?", (
                    zone_id,)
            ).fetchall()

            # If no branch_name is provided, use the first branch in the list
            if not branch_name:
                if branches_in_zone:  # If there are any branches in the zone
                    # Set to the first branch
                    branch_name = branches_in_zone[0]["Branch"]
                else:
                    branch_name = "All branches"  # Fallback if no branches exist

            # Get the branch IDs in the zone
            branch_ids = [branch["ID"] for branch in branches_in_zone]

            # Prepare the leave query
            if branch_name != "All branches":  # If branch_name is provided
                query = '''
                    SELECT
                        l.id,
                        e.name AS employee_name,
                        e.branch AS branch_name,
                        l.leave_type,
                        l.start_date,
                        l.end_date,
                        l.reason,
                        l.status,
                        l.type_of_leave,
                        l.verified_by,
                        l.approved_by,
                        l.leave_hours,
                        l.service_count,
                        l.requested_by
                    FROM leaves l
                    LEFT JOIN employees e ON l.employee_id = e.id
                    WHERE (e.branch = ? AND (l.category = 'M' OR l.category = 'L')) OR l.type_of_leave = 'T'
                '''
                params = (branch_name,)
            else:  # If no branch_name is provided, use all branches in the zone
                query = '''
                    SELECT
                        l.id,
                        e.name AS employee_name,
                        e.branch AS branch_name,
                        l.leave_type,
                        l.start_date,
                        l.end_date,
                        l.reason,
                        l.status,
                        l.type_of_leave,
                        l.verified_by,
                        l.approved_by,
                        l.leave_hours,
                        l.service_count,
                        l.requested_by
                    FROM leaves l
                    LEFT JOIN employees e ON l.employee_id = e.id
                    WHERE (e.branch = ? AND (l.category = 'M' OR l.category = 'L')) OR l.type_of_leave = 'T'
                '''.format(', '.join('?' for _ in branch_ids))  # Dynamically create placeholders
                params = tuple(branch_ids)

            # Execute the query
            leaves = conn.execute(query, params).fetchall()

    except sqlite3.DatabaseError as e:
        return f"Database error: {e}", 500

    return render_template(
        'leaves/leaves_spm_approve.html',
        leaves=leaves,
        branch_name=branch_name,
        branches_in_zone=branches_in_zone,
        zone=zone
    )


@app.route('/leaves/gm', methods=['GET'])
def leaves_by_gm():
    if current_user.role_default in [180]:
        pass
    elif not current_user.is_authenticated or current_user.role_default != 180:
        return redirect(url_for('access_denied'))

    # Simplified query without branch_name
    query = '''
        SELECT
            l.id,
            e.name AS employee_name,
            e.branch AS branch_name,
            l.leave_type,
            l.start_date,
            l.end_date,
            l.reason,
            l.status,
            l.type_of_leave,
            l.verified_by,
            l.approved_by,
            l.leave_hours,
            l.service_count,
            l.requested_by
        FROM leaves l
        LEFT JOIN employees e ON l.employee_id = e.id
        WHERE l.category = 'L'
        AND l.verified_by IS NOT NULL
    '''
    params = ()  # No branch_name parameter needed

    try:
        with get_db_connection() as conn:
            leaves = conn.execute(query, params).fetchall()
    except sqlite3.DatabaseError as e:
        return f"Database error: {e}", 500

    return render_template('leaves/leaves_gm_approve.html', leaves=leaves)


@app.route('/leaves/branch/<string:branch_name>', methods=['GET'])
@login_required
def filter_leaves_by_branch_name(branch_name):
    # Check if user is role 140 and has a branch assigned
    if current_user.role_default == 140 and current_user.branch and current_user.branch != branch_name:
        return redirect(url_for('filter_leaves_by_branch_name', branch_name=current_user.branch))

    elif current_user.role_default != 140:
        return redirect(url_for('access_denied'))

    app.logger.debug(f"Filtering by branch: {branch_name}")

    query = '''
        SELECT
            l.id,
            e.name AS employee_name,
            e.branch AS branch_name,
            l.leave_type,
            l.start_date,
            l.end_date,
            l.reason,
            l.status,
            l.type_of_leave,
            l.verified_by,
            l.approved_by,
            l.leave_hours,
            l.service_count,
            l.requested_by
        FROM leaves l
        LEFT JOIN employees e ON l.employee_id = e.id
        WHERE e.branch = ?
        AND (
            (l.category = 'S' AND l.verified_by IS NOT NULL)
            OR (l.category = 'M' AND l.verified_by IS NULL)
        )
    '''
    params = (branch_name,)

    try:
        with get_db_connection() as conn:
            leaves = conn.execute(query, params).fetchall()
    except sqlite3.DatabaseError as e:
        app.logger.error(f"Database error: {e}")
        return "An error occurred while retrieving data. Please try again later.", 500

    return render_template('leaves/leaves_branch.html', leaves=leaves, branch_name=branch_name)


@app.route('/leave_hours/add/<string:branch>', methods=['GET', 'POST'])
@login_required
def add_leave_hours(branch):
    employees = []
    users = []
    user_branch = branch if not current_user.is_authenticated else current_user.branch

    with get_db_connection() as conn:
        employees = conn.execute('SELECT id, name FROM employees').fetchall()
        users = conn.execute(
            'SELECT id, username FROM users WHERE RoleDefault IN (35,140) AND branch = ?',
            (user_branch,)
        ).fetchall()

    if request.method == 'POST':
        employee_id = request.form['employee_id']
        leave_type = request.form['leave_type']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        requested_by = request.form['requested_by']
        user_ids = request.form.getlist('user_ids')

        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d %H:%M")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d %H:%M")

        # Validations...
        if end_date_obj <= start_date_obj:
            flash("កាលបរិច្ឆេទ/ពេលវេលាបញ្ចប់ត្រូវតែបន្ទាប់...", "error")
            return redirect(url_for('add_leave_hours', branch=branch))

            # Disallow leave hours on Saturday and Sunday
        if start_date_obj.weekday() >= 5 or end_date_obj.weekday() >= 5:
            flash("មិនអាចដាក់ម៉ោងឈប់សម្រាកនៅថ្ងៃសៅរ៍ ឬ អាទិត្យបានទេ។", "error")
            return redirect(url_for('add_leave_hours', branch=branch))

        if start_date_obj.hour < 7:
            flash("ម៉ោងឈប់សម្រាកត្រូវតែចាប់ពីម៉ោង 7:00 ព្រឹក...", "error")
            return redirect(url_for('add_leave_hours', branch=branch))

        if start_date_obj.hour > 17 or (start_date_obj.hour == 17 and start_date_obj.minute > 0) or \
           end_date_obj.hour > 17 or (end_date_obj.hour == 17 and end_date_obj.minute > 0):
            flash("ម៉ោងឈប់សម្រាកត្រូវតែចប់មុនម៉ោង 5:00 ល្ងាច...", "error")
            return redirect(url_for('add_leave_hours', branch=branch))

        # Calculate total hours
        total_seconds = (end_date_obj - start_date_obj).total_seconds()
        total_hours = total_seconds / 3600

        # Define lunch time range
        lunch_start = start_date_obj.replace(hour=12, minute=0)
        lunch_end = start_date_obj.replace(hour=13, minute=30)

        # Subtract lunch only if overlapping
        if start_date_obj < lunch_end and end_date_obj > lunch_start:
            lunch_overlap_start = max(start_date_obj, lunch_start)
            lunch_overlap_end = min(end_date_obj, lunch_end)
            if lunch_overlap_end > lunch_overlap_start:
                lunch_overlap = (lunch_overlap_end -
                                 lunch_overlap_start).total_seconds() / 3600
                total_hours -= lunch_overlap

        total_hours = max(total_hours, 0)
        leave_hours = round(total_hours, 2)  # Show decimals like 4.5

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO leaves(employee_id, leave_type, start_date, end_date, reason, leave_hours, requested_by, type_of_leave)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (employee_id, leave_type, start_date, end_date, reason, leave_hours, requested_by, 'H'))

            leave_id = cursor.lastrowid

            for user_id in user_ids:
                cursor.execute('''
                    INSERT INTO user_leave (user_id, leave_id)
                    VALUES (?, ?)
                ''', (user_id, leave_id))

            conn.commit()

        return redirect(url_for('view_leaves'))

    return render_template('/leaves/add_leave_hours.html', employees=employees, users=users, branch=branch)


def calculate_service_count_1(start_date_obj, end_date_obj, holiday_labels=None):
    # Initialize service count
    service_count = 0
    current_date = start_date_obj

    # Ensure holiday_labels is an empty list if None is provided
    if holiday_labels is None:
        holiday_labels = [
            holiday["label"] for holiday in get_holidays(current_date.year)
        ]

    # Loop through each date and count weekdays only (excluding Saturday, Sunday, and holidays)
    while current_date <= end_date_obj:
        # Exclude Saturday (5), Sunday (6), and holidays
        if current_date.weekday() not in [5, 6] and current_date.strftime('%Y-%m-%d') not in holiday_labels:
            service_count += 1
        current_date += timedelta(days=1)
    return service_count


def calculate_add_day_and_final_end_date(start_date_str, end_date_str, public_holidays_str):
    # Convert string inputs to datetime.date objects
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    public_holidays = [datetime.strptime(date.strip(), "%Y-%m-%d").date()
                       for date in public_holidays_str.split(",") if date.strip()]

    # Calculate excluded days (weekends and public holidays)
    current_date = start_date
    excluded_days = 0
    while current_date <= end_date:
        if current_date.weekday() >= 5 or current_date in public_holidays:
            excluded_days += 1
        current_date += timedelta(days=1)

    # Add excluded days as working days after end date
    final_end_date = end_date
    days_added = 0
    while days_added < excluded_days:
        final_end_date += timedelta(days=1)
        if final_end_date.weekday() < 5 and final_end_date not in public_holidays:
            days_added += 1

    return {
        "StartDate": start_date,
        "EndDate": end_date,
        "PublicHolidays": public_holidays,
        "ExcludedDays": excluded_days,
        "FinalEndDate": final_end_date
    }


def remove_sun_sat_and_holiday(start_date_str, end_date_str, public_holidays_str):
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    public_holidays = [datetime.strptime(date.strip(), "%Y-%m-%d").date()
                       for date in public_holidays_str.split(",") if date.strip()]

    # Initialize
    current_date = start_date
    valid_dates = []
    excluded_days = 0

    while current_date <= end_date:
        if current_date.weekday() < 5 and current_date not in public_holidays:
            valid_dates.append(current_date)
        else:
            excluded_days += 1
        current_date += timedelta(days=1)

    return {
        "StartDate": start_date,
        "EndDate": end_date,
        "PublicHolidays": public_holidays,
        "ExcludedDays": excluded_days,
        "ValidWorkingDays": valid_dates,
        "TotalWorkingDays": len(valid_dates)
    }


def calculate_service_count(start_date, end_date):
    # Count working days between start_date and end_date (excluding weekends)
    count = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # Mon-Fri are 0-4
            count += 1
        current += timedelta(days=1)
    return count


@app.route('/leave_many/add/<string:branch>', methods=['GET', 'POST'])
@login_required
def add_many_leave(branch):
    user_branch = branch if not current_user.is_authenticated else current_user.branch

    with get_db_connection() as conn:
        users3 = []
        branch_row = conn.execute(
            "SELECT id FROM branches WHERE Branch = ?", (user_branch,)
        ).fetchone()

        if branch_row:
            branch_id = branch_row[0]
            print("Branch ID:", branch_id)

            # Check if the branch_id exists in zone_branch table
            cursor = conn.execute(
                "SELECT zone_id FROM zone_branch WHERE branch_id = ?", (branch_id,))

            zone_row = cursor.fetchone()
            zone_id = zone_row[0] if zone_row else None

            if zone_row:
                print(
                    f"Branch ID {branch_id} is linked to Zone ID {zone_row[0]}")
            else:
                print(f"Branch ID {branch_id} is not linked to any zone.")

            # Now find users that belong to this zone
            if zone_id:
                cursor.execute(
                    "SELECT * FROM users WHERE ZoneID = ?", (zone_id,))
                users_in_zone = cursor.fetchall()

                if users_in_zone:
                    for user in users_in_zone:
                        user_info = {
                            "id": user[0],
                            "Username": user[1],
                            "Branch": user[2],
                            "ZoneID": user[3]
                        }
                        users3.append(user_info)
                        print(f"User added: {user_info}")
                else:
                    print(f"No users found in zone ID {zone_id}")
            else:
                print("Zone ID not found for the given branch.")

            # Check if branch_id exists in zone_branch
            zone_check = conn.execute(
                "SELECT 1 FROM zone_branch WHERE branch_id = ? LIMIT 1", (
                    branch_id,)
            ).fetchone()

            if zone_check:
                print("Branch is in zone_branch ✅")
                users3 = conn.execute('''
                    SELECT DISTINCT
                        u.id,
                        u.username,
                        u.branch,
                        u.ZoneID
                    FROM
                        users AS u
                    WHERE
                        u.RoleDefault = 145
                        AND u.ZoneID IS NOT NULL
                        AND u.branch IS NOT NULL
                        AND u.ZoneID = ?
                ''', (zone_id,)).fetchall()

            else:
                print("Branch is NOT in zone_branch ❌")
        else:
            print("Branch not found.")

        employees = conn.execute(
            'SELECT id, name, branch FROM employees').fetchall()

        users = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault IN (35,140) AND branch = ?', (
                user_branch,)
        ).fetchall()

        users2 = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault IN (140) AND branch = ?', (
                user_branch,)
        ).fetchall()
        users4 = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault = 180'
        ).fetchall()

    if request.method == 'POST':
        employee_id = request.form['employee_id']
        leave_type = request.form['leave_type']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        requested_by = request.form['requested_by']
        type_of_leave = request.form.get('type_of_leave', 'D')
        user_ids = request.form.getlist('user_ids')

        branch = user_branch

        current_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        holiday_labels = None
        if holiday_labels is None:
            holiday_labels = [holiday["label"]
                              for holiday in get_holidays(current_date.year)]
        public_holidays_str = ",".join(holiday_labels)

       # Calculate the adjusted leave details
        result = calculate_add_day_and_final_end_date(
            start_date, end_date, public_holidays_str)
        excluded_days = result['ExcludedDays']
        final_end_date = result['FinalEndDate']
        final_end_date_obj = datetime.strptime(str(final_end_date), "%Y-%m-%d")
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")

        # Now calculate working days between actual start and adjusted final end
        service_count = calculate_service_count_1(
            start_date_obj, final_end_date_obj)
        # leave_hours = service_count * 8

        # Determine category
        if service_count <= 2:
            category = "S"
        elif 3 <= service_count <= 5:
            category = "M"
        else:
            category = "L"

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO leaves (employee_id, leave_type, start_date, end_date, reason, service_count, type_of_leave, requested_by, category, branch,  excluded_days, final_end_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                employee_id, leave_type, start_date_obj.date(), final_end_date_obj.date(),
                reason, service_count, type_of_leave, requested_by, category, branch,  excluded_days, final_end_date
            ))

            leave_id = cursor.lastrowid

            for user_id in user_ids:
                cursor.execute('''
                    INSERT INTO user_leave (user_id, leave_id)
                    VALUES (?, ?)
                ''', (user_id, leave_id))

            conn.commit()

        return redirect(url_for('view_leaves'))

    return render_template(
        'leaves/leave_many.html',
        employees=employees,
        users=users,
        users2=users2,
        users3=users3,
        users4=users4,
        branch=user_branch
    )


@app.route('/leave/add', methods=['GET', 'POST'])
def add_leave():
    employees = []

    # Fetch employee list from the database
    with get_db_connection() as conn:
        employees = conn.execute('SELECT id, name FROM employees').fetchall()
        users = conn.execute('SELECT id, username FROM users').fetchall()

    if request.method == 'POST':
        employee_id = request.form['employee_id']
        leave_type = request.form['leave_type']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        requested_by = request.form['requested_by']
        type_of_leave = request.form.get(
            'type_of_leave', 'D')  # Set default value to 'D'

        # Calculate service count (difference between start_date and end_date)
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        service_count = (end_date_obj - start_date_obj).days + 1

        # Insert the leave record into the database
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO leaves(employee_id, leave_type, start_date, end_date, reason, service_count, type_of_leave, requested_by)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            ''', (employee_id, leave_type, start_date, end_date, reason, service_count, type_of_leave, requested_by))

        # Redirect to view leaves page after insertion
        return redirect(url_for('view_leaves'))

    # Render the form page with employees list
    return render_template('/leaves/add_leave.html', employees=employees, users=users)


@app.route('/leaves/all', methods=['GET'])
@login_required
def get_all_leave_dates():
    if current_user.is_admin == 0:
        return redirect(url_for('leaves_user_id', user_id=current_user.id))

    start_date_filter = request.args.get('start_date')
    end_date_filter = request.args.get('end_date')
    employee_name_filter = request.args.get('employee_name')

    query = '''
        SELECT l.id, e.name AS employee_name, e.branch, l.leave_type, l.start_date, l.end_date
        FROM leaves l
        LEFT JOIN employees e ON l.employee_id = e.id
    '''

    conditions = []
    params = []

    if start_date_filter:
        conditions.append('l.start_date >= ?')
        params.append(start_date_filter)
    if end_date_filter:
        conditions.append('l.start_date <= ?')
        params.append(end_date_filter)
    if employee_name_filter:
        conditions.append('e.name LIKE ?')
        params.append(f"%{employee_name_filter}%")

    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)

    with get_db_connection() as conn:
        leaves = conn.execute(query, params).fetchall()

    total_leave_days = 0
    leave_records = []
    leave_type_count = {}
    branch_leave_count = {}

    for leave in leaves:
        employee_name = leave['employee_name'] or "Unknown Employee"
        branch = leave['branch'] or "Unknown Branch"

        try:
            start_date_obj = datetime.strptime(leave['start_date'], "%Y-%m-%d")
            end_date_obj = datetime.strptime(leave['end_date'], "%Y-%m-%d")
        except ValueError:
            continue

        # Get holidays for the year of the start date
        holidays = get_holidays(start_date_obj.year)
        public_holidays_str = ",".join(
            [holiday["label"] for holiday in holidays])

        # Remove weekends and holidays
        result = remove_sun_sat_and_holiday(
            start_date_obj.strftime("%Y-%m-%d"),
            end_date_obj.strftime("%Y-%m-%d"),
            public_holidays_str
        )

        valid_leave_days = result.get(
            "ValidWorkingDays", [])  # The correct key
        leave_day_list = [day.strftime('%Y-%m-%d') for day in valid_leave_days]
        leave_days = len(valid_leave_days)
        total_leave_days += leave_days

        # Count by leave type
        if leave['leave_type'] not in leave_type_count:
            leave_type_count[leave['leave_type']] = {
                'count': 0, 'total_days': 0}
        leave_type_count[leave['leave_type']]['count'] += 1
        leave_type_count[leave['leave_type']]['total_days'] += leave_days

        # Count by branch
        if branch not in branch_leave_count:
            branch_leave_count[branch] = {'leave_count': 0, 'total_days': 0}
        branch_leave_count[branch]['leave_count'] += 1
        branch_leave_count[branch]['total_days'] += leave_days

        leave_records.append({
            'branch': branch,
            'employee_name': employee_name,
            'leave_type': leave['leave_type'],
            'start_date': leave['start_date'],
            'end_date': leave['end_date'],
            'leave_days': leave_days,
            'leave_day_list': leave_day_list
        })

    return render_template('/leaves/all_leaves.html',
                           leaves=leave_records,
                           total_leave_days=total_leave_days,
                           leave_type_count=leave_type_count,
                           branch_leave_count=branch_leave_count,
                           start_date=start_date_filter,
                           end_date=end_date_filter,
                           employee_name=employee_name_filter)


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
        LEFT JOIN employees e ON l.employee_id=e.id
        WHERE l.employee_id= ?
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


@app.route('/leave/edit_ccc_verify/<int:id>', methods=['GET', 'POST'])
def edit_leave_ccc_verify(id):
    with get_db_connection() as conn:
        leave = conn.execute(
            'SELECT * FROM leaves WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        leave_type = request.form['leave_type']
        reason = request.form['reason']
        status = request.form['status']
        verified_by = request.form['verified_by']

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE leaves
                SET leave_type = ?, reason = ?, status = ?, verified_by = ?
                WHERE id = ?
            ''', (leave_type, reason, status, verified_by, id))

        return redirect(url_for('view_leaves'))

    return render_template('/leaves/edit_ccc_leave.html', leave=leave)


@app.route('/leave/edit_spm_approve/<int:id>', methods=['GET', 'POST'])
def edit_leave_spm_approve(id):
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
        start_date_obj = datetime.strptime(start_date[:10], "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date[:10], "%Y-%m-%d")
        service_count = (end_date_obj - start_date_obj).days + 1
        # Determine leave category, status, and set the appropriate fields
        if 3 <= service_count <= 5:
            category = "M"
            status = "Approved"
            approved_by = current_user.username  # Automatically set current user
            # Automatically set current user as verified_by
            verified_by = request.form.get('verified_by', None)
        elif service_count >= 6:
            category = "L"
            status = request.form['status']
            approved_by = request.form.get('approved_by', None)
            # Automatically set current user as verified_by if service_count >= 6
            verified_by = current_user.username

        # Update the leave in the database
        with get_db_connection() as conn:
            conn.execute('''
                UPDATE leaves
                SET leave_type= ?,  reason= ?, status= ?, category= ?, approved_by= ?, verified_by= ?
                WHERE id= ?
            ''', (leave_type, reason, status,  category,
                  approved_by, verified_by, id))

        return redirect(url_for('view_leaves'))

    return render_template('/leaves/edit_spm_leave.html', leave=leave)


@app.route('/leave/edit_gm_approve/<int:id>', methods=['GET', 'POST'])
def edit_leave_gm_approve(id):
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
        start_date_obj = datetime.strptime(start_date[:10], "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date[:10], "%Y-%m-%d")
        service_count = (end_date_obj - start_date_obj).days + 1
        # Set category and approved_by
        if service_count <= 5:
            category = "M"
            status = "Approved"
            approved_by = current_user.username
        else:
            category = "L"
            status = request.form['status']
            approved_by = request.form.get(
                'approved_by', current_user.username)

        # Update the leave in the database
        with get_db_connection() as conn:
            conn.execute('''
                UPDATE leaves
                SET leave_type= ?,  reason= ?, status= ?, category= ?, approved_by= ?
                WHERE id= ?
            ''', (leave_type,  reason, status, category, approved_by, id))

        return redirect(url_for('view_leaves'))

    return render_template('/leaves/edit_gm_leave.html', leave=leave)


@app.route('/leave_pm/edit/<int:id>', methods=['GET', 'POST'])
def edit_leave_pm(id):
    with get_db_connection() as conn:
        leave = conn.execute(
            'SELECT * FROM leaves WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        leave_type = request.form['leave_type']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']

        # Calculate service count (difference between start_date and end_date)
        start_date_obj = datetime.strptime(start_date[:10], "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date[:10], "%Y-%m-%d")
        service_count = (end_date_obj - start_date_obj).days + 1

        # Determine leave category and set the appropriate fields
        if service_count <= 2:
            category = "S"
            status = "Approved"
            approved_by = current_user.username  # Automatically set current user
            verified_by = request.form['verified_by']
        elif 3 <= service_count <= 5:
            category = "M"
            status = "Verified"
            approved_by = request.form['approved_by']
            verified_by = current_user.username  # Automatically set current user
        else:
            category = "L"
            status = request.form['status']
            approved_by = request.form.get('approved_by', None)
            verified_by = request.form.get('verified_by', None)

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE leaves
                SET leave_type= ?,  reason= ?, status= ?, category= ?, approved_by= ?, verified_by= ?
                WHERE id= ?
            ''', (leave_type, reason, status,  category, approved_by, verified_by, id))

        return redirect(url_for('view_leaves'))

    return render_template('/leaves/edit_leave_pm.html', leave=leave)


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

        # Get values for approved_by and verified_by if they exist
        approved_by = request.form.get('approved_by', None)
        verified_by = request.form.get('verified_by', None)

        # Calculate service count (difference between start_date and end_date)
        start_date_obj = datetime.strptime(start_date[:10], "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date[:10], "%Y-%m-%d")
        service_count = (end_date_obj - start_date_obj).days + 1

        # Determine leave category and set the appropriate fields
        if service_count <= 2:
            category = "S"
            status = "Approved"
            # Require verified_by for small leaves
            verified_by = request.form['verified_by']
            approved_by = None  # Clear approved_by for category "S"
        elif 3 <= service_count <= 5:
            category = "M"
            status = "Verified"
            # Require approved_by for medium leaves
            approved_by = request.form['approved_by']
            verified_by = None  # Clear verified_by for category "M"
        else:
            category = "L"
            status = request.form['status']  # User-defined status
            # Keep approved_by and verified_by unchanged

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE leaves
                SET leave_type= ?, start_date= ?, end_date= ?, reason= ?, status= ?, 
                    service_count= ?, category= ?, approved_by= ?, verified_by= ?
                WHERE id= ?
            ''', (leave_type, start_date, end_date, reason, status, service_count, category,
                  approved_by, verified_by, id))

        return redirect(url_for('view_leaves'))

    return render_template('/leaves/edit_leave.html', leave=leave)


@app.route('/leave/edit/<int:id>', methods=['GET', 'POST'])
def edit_leave_spm(id):
    with get_db_connection() as conn:
        leave = conn.execute(
            'SELECT * FROM leaves WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        leave_type = request.form['leave_type']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        status = request.form['status']
        approved_by = request.form['approved_by']
        # Calculate service count (difference between start_date and end_date)
        start_date_obj = datetime.strptime(start_date[:10], "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date[:10], "%Y-%m-%d")
        service_count = (end_date_obj - start_date_obj).days + 1

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE leaves
                SET leave_type= ?, start_date= ?, end_date= ?, reason= ?, status= ?, service_count= ?, verified_by= ?, approved_by= ?
                WHERE id= ?
            ''', (leave_type, start_date, end_date, reason, status, service_count, verified_by, approved_by, id))

        return redirect(url_for('view_leaves'))

    return render_template('/leaves/edit_leave_spm.html', leave=leave)


@app.route('/leave_days/edit/<int:id>', methods=['GET', 'POST'])
def edit_leave_days(id):
    with get_db_connection() as conn:
        leave = conn.execute(
            'SELECT * FROM leaves WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        leave_type = request.form['leave_type']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        status = request.form['status']
        approved_by = request.form['approved_by']

        # Calculate service count (difference between start_date and end_date)
        start_date_obj = datetime.strptime(start_date[:10], "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date[:10], "%Y-%m-%d")
        service_count = (end_date_obj - start_date_obj).days + 1

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE leaves
                SET leave_type= ?, start_date= ?, end_date= ?, reason= ?, status= ?, service_count= ?, approved_by= ?
                WHERE id= ?
            ''', (leave_type, start_date, end_date, reason, status, service_count, approved_by, id))

        return redirect(url_for('view_leaves'))

    return render_template('/leaves/edit_leave_days.html', leave=leave)


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
                    INSERT INTO Attendance(employee_name, status, checkin_time)
                    VALUES(?, ?, ?)
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
                WHERE employee_name=(SELECT UserName FROM users WHERE id= ?)
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
                    SET status= ?, checkout_time= ?
                    WHERE employee_name= ? AND status='Checked In'
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
            INNER JOIN employees e ON u.id=e.user_id
            WHERE u.id= ?
        ''', (user_id,)).fetchone()

        if employee:
            # Fetch attendance records for the employee for the current month
            attendance = conn.execute('''
                SELECT * FROM Attendance WHERE employee_name= ?
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
                SELECT * FROM leaves WHERE employee_id= ?
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
            INSERT INTO payroll(employee_id, period_start_date, period_end_date, base_salary, bonus, deductions, tax, total_salary)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        ''', (employee_id, period_start_date, period_end_date, base_salary, bonus, deductions, tax, total_salary))
        conn.commit()


def get_payroll_by_employee_and_period(employee_id, period_start_date, period_end_date):
    """Retrieve payroll details for a specific employee and period."""
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT * FROM payroll
            WHERE employee_id= ? AND period_start_date= ? AND period_end_date= ?
        ''', (employee_id, period_start_date, period_end_date))
        payroll = cursor.fetchone()
        return payroll


def list_payroll_for_employee(employee_id):
    """Retrieve all payroll records for a specific employee."""
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT * FROM payroll WHERE employee_id= ?
        ''', (employee_id,))
        payroll_records = cursor.fetchall()
        return payroll_records


def list_payroll_for_employee_name(employee_name):
    """Retrieve all payroll records for a specific employee."""
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT p.* FROM payroll p
            INNER JOIN employees e ON p.employee_id=e.id
            WHERE e.name= ?
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
                INSERT INTO roles(UserID, Status, Description)
                VALUES(?, ?, ?)
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
                SET UserID= ?, Status= ?, Description= ?
                WHERE ID= ?
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
                SET last_active_time=CURRENT_TIMESTAMP
                WHERE user_id= ?
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
                    INSERT INTO users(UserName, Password, Email, Mobile1)
                    VALUES(?, ?, ?, ?)
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


@login_manager.unauthorized_handler
def unauthorized():
    return render_template('unauthorized.html'), 401


# def allowed_file(filename):
#     return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

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
            JOIN users u ON ou.user_id=u.ID
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
                   COALESCE(RoleDefault, 1) AS RoleDefault, ZoneID
            FROM users
            WHERE UserName= ? AND Password= ?
        ''', (username, password)).fetchone()

    if user:
        user = dict(user)  # Convert row to dictionary for easy access
        print("Fetched User Data:", user)  # Debugging print statement

        # Find employee ID associated with the user
        with get_db_connection() as conn:
            employee = conn.execute('''
                SELECT id FROM employees
                WHERE user_id= ?
            ''', (user['ID'],)).fetchone()
            employee_id = employee['id'] if employee else None

        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO login_logs(user_id, ip_address, city, region, country, user_agent)
                VALUES(?, ?, ?, ?, ?, ?)
            ''', (user['ID'], ip_address, city, region, country, user_agent))

            # Add user to online_users table or update if already exists
            conn.execute('''
                INSERT OR REPLACE INTO online_users(user_id, login_time, last_active_time)
                VALUES(?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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
            role_default=user['RoleDefault'],
            image_data=user.get('Image', None),
            employee_id=employee_id,
            zone_id=user['ZoneID']
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
                DELETE FROM online_users WHERE user_id= ?
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
                SELECT * FROM users WHERE ID= ?
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
                SET Password= ?
                WHERE ID= ?
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
            SELECT * FROM users WHERE ID= ?
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
def add_user() -> Union[str, 'Response']:
    if current_user.is_admin == 0:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username: str = request.form['username']
        password: str = request.form['password']
        email: str = request.form['email']
        mobile1: str = request.form['mobile1']
        first_name_kh: str = request.form['first_name_kh']
        last_name_kh: str = request.form['last_name_kh']
        first_name_en: str = request.form['first_name_en']
        last_name_en: str = request.form['last_name_en']
        branch: str = request.form['branch']
        branch_id: str = request.form['branch']
        zone_id: str = request.form['zone_id']
        is_admin: int = int(request.form.get('is_admin', 0))
        role_default: int = int(request.form.get('role_default', 0))
        hashed_password: str = hashlib.sha256(password.encode()).hexdigest()

        # Handle image upload
        image_data: Union[bytes, None] = None
        if 'image' in request.files:
            image: FileStorage = request.files['image']
            if image and allowed_file(image.filename):
                image_data = image.stream.read()

        # Handle signature upload
        signature_data: Union[bytes, None] = None
        if 'signature' in request.files:
            signature: FileStorage = request.files['signature']
            if signature and allowed_file(signature.filename):
                signature_data = signature.stream.read()

        # Insert user into 'users' table
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM users WHERE UserName = ?', (username,))
            existing_user = cursor.fetchone()

            if existing_user:
                flash('Username already exists. Please choose another one.', 'danger')
                return redirect(url_for('add_user'))

            # Insert user data including signature into 'users' table
            cursor.execute('''
                INSERT INTO users(UserName, Password, Email, Mobile1, FirstNameKh, LastNameKh, FirstNameEn, LastNameEn, Branch, IsAdmin, RoleDefault, Image, ZoneID, Signature)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (username, hashed_password, email, mobile1, first_name_kh, last_name_kh, first_name_en, last_name_en, branch, is_admin, role_default, image_data, zone_id, signature_data))

            user_id = cursor.lastrowid

            # Insert relationship into 'user_branches' table
            cursor.execute('''
                INSERT INTO user_branches(user_id, branch_id)
                VALUES(?, ?)
            ''', (user_id, branch_id))
            conn.commit()

        return redirect(url_for('list_users'))

    # Fetch all branches for selection
    with get_db_connection() as conn:
        branches = conn.execute('SELECT * FROM branches').fetchall()
        zones = conn.execute('SELECT * FROM zones').fetchall()

    return render_template('/users/add_user.html', branches=branches, zones=zones)

# Route to serve the user's signature


@app.route('/user/<int:user_id>/signature')
def get_user_signature(user_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT Signature FROM users WHERE id = ?', (user_id,))
        signature_data = cursor.fetchone()

        if signature_data and signature_data[0]:

            return Response(signature_data[0], mimetype='image/png')
        else:
            return "Signature not found", 404


# Route to upload a new signature
@app.route('/users/<int:user_id>/signature/upload', methods=['GET', 'POST'])
@login_required
def upload_user_signature(user_id):
    if request.method == 'GET':
        # If GET request, render the upload form
        return render_template('users/upload_signature.html', user_id=user_id)

    # Handle the POST request for signature upload
    signature_file = request.files.get('signature')

    if not signature_file:
        flash('No signature uploaded', 'danger')
        return redirect(request.url)

    # Read the signature file as binary data
    signature_data = signature_file.read()

    # Update the signature data in the database
    with get_db_connection() as conn:
        conn.execute(
            'UPDATE users SET Signature = ? WHERE id = ?',
            (signature_data, user_id)
        )
        conn.commit()

    flash('Signature uploaded successfully!', 'success')
    return redirect(url_for('profile', user_id=user_id))


@app.route('/user/<int:user_id>/image')
def get_user_image(user_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT Image FROM users WHERE id = ?', (user_id,))
        image_data = cursor.fetchone()[0]

    if image_data:
        # or another appropriate MIME type
        return Response(image_data, mimetype='image/jpeg')
    else:
        return "Image not found", 404


@app.route('/users/<int:user_id>/image/upload', methods=['GET', 'POST'])
@login_required
def upload_user_image(user_id):
    if request.method != 'POST':
        # If GET request, show the upload form
        return render_template('/users/upload_image.html', user_id=user_id)
    # Get the uploaded file
    image_file = request.files.get('image')

    if not image_file:
        return "No image uploaded", 400

    # Read the image file as binary data
    image_data = image_file.read()

    # Update the image data in the database
    with get_db_connection() as conn:
        conn.execute(
            'UPDATE users SET Image = ? WHERE id = ?',
            (image_data, user_id)
        )
        conn.commit()

    # Redirect to profile page after upload
    return redirect(url_for('profile', user_id=user_id))


@app.route('/users/profile/<int:user_id>')
@login_required
def profile(user_id):
    with get_db_connection() as conn:
        user_data = conn.execute(
            "SELECT * FROM users WHERE ID = ?", (user_id,)).fetchone()
        branches = conn.execute("SELECT * FROM branches").fetchall()

    if user_data:
        return render_template('/users/profile.html', user=user_data, branches=branches)
    else:
        return "User not found", 404


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


@app.route('/access_denied')
def access_denied():
    flash("Access denied!", "danger")
    return render_template('access_denied.html')


@app.route('/dashboard')
@login_required
def dashboard():
    # Admin users are directed to the admin dashboard
    if current_user.is_admin:
        return render_dashboard(current_user.id)

    # Employees (role_default == 20) are directed to the employee dashboard
    if current_user.role_default == 20:
        with get_db_connection() as conn:
            employee = conn.execute(
                "SELECT e.ID FROM employees e WHERE e.user_id = ?", (
                    current_user.id,)
            ).fetchone()

        if employee:
            return redirect(url_for('render_dashboard_employees', employee_id=employee[0]))
        else:
            flash("Employee not found!", "danger")
            return redirect(url_for('render_dashboard_employees', employee_id=current_user.id))

    # Users with role_default == 145 are directed to the SPM dashboard
    if current_user.role_default == 145:
        return redirect(url_for('spm_dashboard'))

    # Users with roles 40, 45, 60, or 65 are directed to the branch manager dashboard
    if current_user.role_default in [140, 35, 180]:
        if current_user.branch:
            return redirect(url_for('render_dashboard_branch_manager', branch_name=current_user.branch))
        elif not current_user.branch:
            flash("Branch information is missing.", "danger")
            return render_template('access_denied.html')

    # If no conditions are met, deny access
    flash("Access denied: You do not have permission to view this page.", "danger")
    return redirect(url_for('dashboard'))


@app.route('/spm_dashboard')
@login_required
def spm_dashboard():
    # Ensure that only users with role_default == 145 can access this page
    if current_user.role_default != 145:
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    # Get the current user's zone_id
    zone_id = current_user.zone_id

    if zone_id is None:
        flash("Zone ID not found for the current user!", "danger")
        return redirect(url_for('dashboard'))

    # Query the Zone and Branch based on the user's zone_id
    with get_db_connection() as conn:
        # Get the zone based on the user's zone_id
        zone = conn.execute(
            "SELECT * FROM zones WHERE ID = ?", (zone_id,)).fetchone()
        if zone is None:
            flash("Zone not found!", "danger")
            return redirect(url_for('dashboard'))

        # Find branches in the current zone
        branches_in_zone = conn.execute(
            "SELECT b.ID, b.Branch, b.ContactNumber FROM branches b JOIN zone_branch zb ON b.ID = zb.branch_id WHERE zb.zone_id = ?", (zone_id,)).fetchall()

    # If no branches are found, we can handle that too
    if not branches_in_zone:
        flash("No branches found in this zone.", "warning")

    # Prepare the data to send to the template
    data = {
        'message': "Welcome",
        'zone': zone,  # Zone information for the current user
        'branches': branches_in_zone  # Branches in the user's zone
    }

    # Render the spm_dashboard template with data
    return render_template('/dashboard/spm_dashboard.html', data=data)


@app.route('/dashboard/branch_manager/<string:branch_name>')
@login_required
def render_dashboard_branch_manager(branch_name):

    with get_db_connection() as conn:
        # Fetch all employees data based on branch_name
        employees = conn.execute(
            "SELECT e.ID, e.Name, e.Age, e.Salary, e.Branch, p.PositionName AS Position, d.Name AS Department "
            "FROM employees e "
            "LEFT JOIN positions p ON e.position_id = p.ID "
            "LEFT JOIN departments d ON p.department_id = d.ID "
            "WHERE e.Branch = ?",  # Fetch all employees in the given branch
            (branch_name,)
        ).fetchall()  # Fetch all employees in the branch

        if not employees:
            flash("No employees found in this branch!", "danger")
            # Redirect to the main dashboard if no employees are found
            return redirect(url_for('dashboard'))

        # Prepare employee data for rendering in the template
        employee_data = [
            {
                'ID': employee['ID'] if employee['ID'] is not None else '',
                'Name': employee['Name'] if employee['Name'] is not None else '',
                'Age': employee['Age'] if employee['Age'] is not None else '',
                'Salary': employee['Salary'] if employee['Salary'] is not None else '',
                'Branch': employee['Branch'] if employee['Branch'] is not None else '',
                'Position': employee['Position'] if employee['Position'] is not None else '',
                'Department': employee['Department'] if employee['Department'] is not None else ''
            }
            for employee in employees
        ]

        return render_template(
            'employees/bm_dashboard.html',
            employees=employee_data
        )


@app.route('/dashboard/employee/<int:employee_id>')
@login_required
def render_dashboard_employees(employee_id):
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    with get_db_connection() as conn:
        # Fetch the specific employee's data
        employee = conn.execute(
            """
            SELECT e.ID, e.Name, e.Age, e.Salary, e.Branch, 
                   p.PositionName AS Position, d.Name AS Department 
            FROM employees e 
            LEFT JOIN positions p ON e.position_id = p.ID 
            LEFT JOIN departments d ON p.department_id = d.ID 
            WHERE e.ID = ?
            """,
            (employee_id,)
        ).fetchone()

        if not employee:
            flash("Employee not found!", "danger")
            return redirect(url_for('dashboard', id=current_user.id))

        employee_data = {
            'ID': employee['ID'] or '',
            'Name': employee['Name'] or '',
            'Age': employee['Age'] or '',
            'Salary': employee['Salary'] or '',
            'Branch': employee['Branch'] or '',
            'Position': employee['Position'] or '',
            'Department': employee['Department'] or ''
        }

        # Get Payroll by employee ID and optional date range
        payroll_query = """
            SELECT COALESCE(SUM(p.base_salary + p.bonus - p.deductions - p.tax), 0) AS total_salary 
            FROM payroll p 
            WHERE p.employee_id = ?
        """
        payroll_params = [employee['ID']]
        if start_date and end_date:
            payroll_query += " AND p.period_start_date >= ? AND p.period_end_date <= ?"
            payroll_params.extend([start_date, end_date])

        total_salary = conn.execute(payroll_query, payroll_params).fetchone()
        total_salary = total_salary["total_salary"] if total_salary else 0

        # Get Leaves by employee ID and optional date range
        leaves_query = """
            SELECT 
                COALESCE(SUM(l.service_count), 0) AS total_leaves_days,
                COALESCE(
                    SUM(l.leave_hours), 
                    0
                ) AS total_leaves_hours
            FROM leaves l 
            WHERE l.employee_id = ?
        """
        leaves_params = [employee['ID']]
        if start_date and end_date:
            leaves_query += " AND l.start_date >= ? AND l.end_date <= ?"
            leaves_params.extend([start_date, end_date])

        leaves = conn.execute(leaves_query, leaves_params).fetchone()

        # Ensure we handle cases where the query returns None
        total_leaves_days = leaves["total_leaves_days"] if leaves else 0
        total_leaves_hours = "{:.0f} hours".format(
            leaves["total_leaves_hours"]) if leaves else "0 hours"

        return render_template(
            'employees/employee_dashboard.html',
            employee=employee_data,
            total_salary=total_salary,
            total_leaves_days=total_leaves_days,
            total_leaves_hours=total_leaves_hours
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
            JOIN users u ON ou.user_id=u.ID
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

    # Get branches, users, and positions from the database
    with get_db_connection() as conn:
        branches = conn.execute("SELECT * FROM branches").fetchall()
        users = conn.execute(
            "SELECT id, UserName FROM users").fetchall()  # Fetch users
        positions = conn.execute("SELECT * FROM positions").fetchall()

    if request.method == 'POST':
        # Collect all form data
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
        employees_height = request.form.get('employees_height')
        ethnicity = request.form.get('ethnicity')
        nationality = request.form.get('nationality')
        religion = request.form.get('religion')
        family_status = request.form.get('family_status')
        place_of_birth = request.form.get('place_of_birth')
        permanent_address = request.form.get('permanent_address')
        village = request.form.get('village')
        commune = request.form.get('commune')
        district = request.form.get('district')
        province = request.form.get('province')
        home_number = request.form.get('home_number')
        street_number = request.form.get('street_number')
        group_name = request.form.get('group_name')

        # New fields to be added
        personal_phone_number = request.form.get('personal_phone_number')
        level_of_culture = request.form.get('level_of_culture')
        skill = request.form.get('skill')
        name_of_educational_institution = request.form.get(
            'name_of_educational_institution')
        knowledge_of_foreign_languages = request.form.get(
            'knowledge_of_foreign_languages')
        current_function = request.form.get('current_function')
        id_card_number = request.form.get('id_card_number')
        work_at = request.form.get('work_at')
        employment_id = request.form.get('employment_id')
        employment_date = request.form.get('employment_date')
        khmer_nationality_identity_card = request.form.get(
            'khmer_nationality_identity_card')

        # Handle photo, fingerprints, and signature upload
        photo = request.files.get('photo')
        fingerprints = request.files.get('fingerprints')
        signature = request.files.get('signature')

        # Function to check if file is allowed
        def allowed_file(filename):
            ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'bmp'}
            return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

        # Convert files to binary data if valid
        photo_data = None
        if photo and allowed_file(photo.filename):
            photo_data = photo.read()

        fingerprints_data = None
        if fingerprints and allowed_file(fingerprints.filename):
            fingerprints_data = fingerprints.read()

        signature_data = None
        if signature and allowed_file(signature.filename):
            signature_data = signature.read()

        # Ensure that mandatory fields are provided (simple validation)
        if not name or not age or not department:
            flash('Name, Age, and Department are required fields!', 'error')
            return redirect(url_for('add_employee'))

        # Insert the new employee into the database
        with get_db_connection() as conn:
            conn.execute(
                """INSERT INTO employees (
                    name, age, department, salary, position_id, joining_date, status,
                    branch, user_id, phone_number, email, address, emergency_contact_name, emergency_contact_phone,
                    employees_height, ethnicity, nationality, religion, family_status, place_of_birth, permanent_address, village,
                    commune, district, province, home_number, street_number, group_name,
                    personal_phone_number, level_of_culture, skill, name_of_educational_institution,
                    knowledge_of_foreign_languages, current_function, id_card_number, work_at, employment_id, employment_date,
                    khmer_nationality_identity_card, photo, fingerprints, signature)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? , ?, ?)""",
                (name, age, department, salary, position_id, joining_date, status, branch, user_id,
                 phone_number, email, address, emergency_contact_name, emergency_contact_phone,
                 employees_height, ethnicity, nationality, religion, family_status, place_of_birth, permanent_address, village,
                 commune, district, province, home_number, street_number, group_name,
                 personal_phone_number, level_of_culture, skill, name_of_educational_institution,
                 knowledge_of_foreign_languages, current_function, id_card_number, work_at, employment_id, employment_date,
                 khmer_nationality_identity_card, photo_data, fingerprints_data, signature_data)
            )
            conn.commit()

        # Redirect to employee list after successful insertion
        return redirect(url_for('list_employees'))

    # Render the form to add a new employee with necessary context
    return render_template('employees/add_employee.html', branches=branches, users=users, positions=positions)


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
                INSERT INTO branches(Description, Branch, BranchManagerName, ContactNumber, Address,
                                      RegisterDate, LocalDescription, LocalAddress, LocalBranchManagerName)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)''',
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
            SET Status= ?, BranchManagerName= ?, Address= ?, Description= ?, Branch= ?, ContactNumber= ?, UpdatedAt=CURRENT_TIMESTAMP
            WHERE ID= ?''',
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


if __name__ == "__main__":
    init_db()
    socketio.run(app, debug=True)
    start_scheduler()
