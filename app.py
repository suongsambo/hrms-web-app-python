from datetime import date
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    Response, session, send_from_directory, jsonify, send_file
)

from flask_login import (
    login_required, LoginManager, login_user,
    logout_user, current_user
)
import base64
import sqlite3
import hashlib
import os
import io
import pandas as pd
from io import BytesIO, TextIOWrapper
import csv
import json
import requests
import shutil
import math
import glob
from werkzeug.utils import secure_filename
from config import Config
from flask_socketio import SocketIO, emit, join_room, leave_room, send
import time
from datetime import datetime, timedelta, date
import eventlet
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from typing import Union
from flask_caching import Cache
from db import init_db
from flask_cors import CORS
from limiter_config import limiter
from flask_limiter.errors import RateLimitExceeded
# from flask_babel import Babel, _
from flask_babel import Babel
# Blueprints
from routes.branches import branches_bp
from routes.zones import zones_bp
from routes.users import users_bp
from routes.bankstatements import bankstatements_bp
from routes.positions import positions_bp
from routes.departments import departments_bp
# utils
from utils.holidays import get_holidays

# models
from models.user import User
from models.users.user_loader import load_user
import qrcode

app = Flask(__name__)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
app.register_blueprint(branches_bp)
app.register_blueprint(zones_bp)
app.register_blueprint(users_bp)
app.register_blueprint(bankstatements_bp)
app.register_blueprint(positions_bp)
app.register_blueprint(departments_bp)
app.config.from_object(Config)
CORS(app)
# Update session cookie settings for security
# app.secret_key = 'kpca_2023_admin_app'  # Use a strong, random secret!
# app.config.update(
#     SESSION_COOKIE_HTTPONLY=True,
#     SESSION_COOKIE_SECURE=True,
#     SESSION_COOKIE_SAMESITE='Lax',
#     PERMANENT_SESSION_LIFETIME=timedelta(minutes=30)
# )
CORS(app, resources={
     r"/*": {"origins": ["http://127.0.0.1:5000",  "http://172.104.60.81"]}})
app.config['BABEL_DEFAULT_LOCALE'] = 'en'
app.config['LANGUAGES'] = ['en', 'km']
app.config['BABEL_TRANSLATION_DIRECTORIES'] = 'translations'
babel = Babel(app)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")
cache = Cache(config={'CACHE_TYPE': 'simple'})
eventlet.monkey_patch()
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
LANGUAGES = ['en', 'km']
ALLOWED_EXCEL = {'xlsx', 'xls'}
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_FOLDER = 'signatures'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_excel(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXCEL


# @app.before_request
# def make_session_permanent():
#     session.permanent = True


@app.route('/signature')
def signature():
    return render_template('/signature/signature.html')


@app.route('/save-signature', methods=['POST'])
def save_signature():
    data_url = request.form['signature_data']
    # Strip metadata and decode
    header, encoded = data_url.split(",", 1)
    binary_data = base64.b64decode(encoded)

    # Save to file
    filepath = os.path.join(UPLOAD_FOLDER, 'signature.png')
    with open(filepath, 'wb') as f:
        f.write(binary_data)

    return redirect(url_for('signature'))


@app.route('/download-signature', methods=['POST'])
def download_signature():
    return send_from_directory(UPLOAD_FOLDER, 'signature.png', as_attachment=True)


@app.route('/leave-guide')
def leave_guide():
    return render_template('/guideline/leave_guide.html')


@app.route('/data-management')
def data_management():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Get all non-system tables
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return render_template('/backups/data_management.html', tables=tables)


# Should be POST for destructive action
@app.route('/clear_by_table_name', methods=['POST'])
def clear_data_by_table_name():
    conn = get_db_connection()
    cursor = conn.cursor()

    # List only the tables you want to clear
    tables_to_clear = ['leaves', 'user_leave']

    for table in tables_to_clear:
        # Deletes all rows in the table
        cursor.execute(f"DELETE FROM {table};")

    conn.commit()
    conn.close()

    # Optional: flash a success message
    flash('Leaves and user leave data cleared successfully.', 'success')

    return redirect('/data-management')  # or any page you want to redirect to


@app.route('/clear_table_employees', methods=['POST'])
def clear_table_employees():
    conn = get_db_connection()
    cursor = conn.cursor()

    # List only the tables you want to clear
    tables_to_clear = ['employees']

    for table in tables_to_clear:
        # Deletes all rows in the table
        cursor.execute(f"DELETE FROM {table};")

    conn.commit()
    conn.close()

    # Optional: flash a success message
    flash('Leaves and user leave data cleared successfully.', 'success')

    return redirect('/data-management')  # or any page you want to redirect to


@app.route('/clear_data')
def clear_data():
    conn = get_db_connection()  # raw SQLite connection
    cursor = conn.cursor()
    # Get all table names from sqlite_master
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    for table_name_tuple in tables:
        table_name = table_name_tuple[0]
        # Skip SQLite internal tables if needed (e.g., sqlite_sequence)
        if table_name.startswith('sqlite_'):
            continue
        cursor.execute(f"DELETE FROM {table_name};")

    conn.commit()
    conn.close()

    return render_template('/backups/clear_data.html')


@app.route('/routes', methods=['GET'])
def show_routes():
    routes = []
    with app.app_context():
        for rule in app.url_map.iter_rules():
            routes.append({
                'endpoint': rule.endpoint,
                'rule': rule.rule,
                # Optional: Include allowed HTTP methods
                'methods': list(rule.methods)
            })
    return jsonify(routes)


@app.route('/routes/current', methods=['GET'])
def show_current_routes():
    current_endpoint = request.endpoint          # Function name: 'show_routes'
    current_path = request.path                  # Actual path: '/routes'
    current_method = request.method              # HTTP method: 'GET'

    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'rule': rule.rule,
            'methods': list(rule.methods)
        })

    # Include current route info in response (optional)
    return jsonify({
        'current': {
            'endpoint': current_endpoint,
            'path': current_path,
            'method': current_method
        },
        'all_routes': routes
    })


@app.route('/qr/<int:leave_id>')
def generate_qr_for_leave(leave_id):
    # Data encoded in the QR (e.g., a verification URL or just the leave ID)
    # You can use a URL or more detail here
    data = f"http://172.104.60.81/print-leaves?ids={leave_id}"
    img = qrcode.make(data)
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')


@app.route('/print-leaves')
def print_leaves():
    ids = request.args.getlist('ids')

    if not ids:
        return "No leave IDs provided.", 400

    try:
        ids = list(map(int, ids))
    except ValueError:
        return "Invalid leave ID provided.", 400

    placeholders = ','.join(['?'] * len(ids))

    with get_db_connection() as conn:
        # Fetch leave data
        # leaves = conn.execute(
        #     f'''
        #     SELECT
        #         id,
        #         employee_id,
        #         leave_type,
        #         start_date,
        #         end_date,
        #         reason,
        #         start_date_obj,
        #         end_date_obj,
        #         excluded_days,
        #         final_end_date,
        #         service_count,
        #         leave_hours,
        #         requested_by,
        #         requested_by_roles,
        #         verified_by,
        #         approved_by,
        #         type_of_leave,
        #         status,
        #         spm_status,
        #         dd_status,
        #         manager_status,
        #         branch,
        #         category
        #     FROM leaves
        #     WHERE id IN ({placeholders})
        #     ''',
        #     ids
        # ).fetchall()

        leaves = conn.execute(
            f'''
            SELECT
                l.id,
                l.employee_id,
                e.age AS employee_age,
                e.department AS employee_department,
                e.name AS employee_name,
                l.leave_type,
                l.start_date,
                l.end_date,
                l.reason,
                l.start_date_obj,
                l.end_date_obj,
                l.excluded_days,
                l.final_end_date,
                l.service_count,
                l.leave_hours,
                l.requested_by,
                l.requested_by_roles,
                l.verified_by,
                l.approved_by,
                l.type_of_leave,
                l.status,
                l.spm_status,
                l.dd_status,
                l.manager_status,
                l.branch,
                l.category
            FROM leaves l
            JOIN employees e ON l.employee_id = e.id  -- Join to get employee name
            WHERE l.id IN ({placeholders})
            ''',
            ids
        ).fetchall()

        if not leaves:
            return "No leaves found for the provided IDs.", 404

        usernames = set()

        for leave in leaves:
            for field in ['requested_by', 'verified_by', 'approved_by']:
                val = leave[field]
                if val:  # non-empty string
                    usernames.add(val)

        # Fetch user records by username
        users = {}
        if usernames:
            placeholders = ','.join(['?'] * len(usernames))
            users_raw = conn.execute(
                f'''
                SELECT ID, UserName, Email, Signature
                FROM users
                WHERE UserName IN ({placeholders})
                ''',
                list(usernames)
            ).fetchall()

            for user in users_raw:
                user_dict = dict(user)
                sig = user_dict.get('Signature')
                if sig:
                    user_dict['Signature'] = base64.b64encode(
                        sig).decode('utf-8')
                else:
                    user_dict['Signature'] = None
                # Key by username so it’s easy to lookup in template
                users[user_dict['UserName']] = user_dict

    return render_template(
        'leave_print_template.html',
        leaves=leaves,
        users=users
    )


# get holidays
year = datetime.now().year
holidays = get_holidays(year)


def get_locale():
    lang = request.args.get('lang')
    if lang in LANGUAGES:
        return lang
    return request.accept_languages.best_match(LANGUAGES)


babel.init_app(app, locale_selector=get_locale)


@app.context_processor
def inject_locale():
    return dict(get_locale=get_locale)


def allowed_file(filename: str) -> bool:
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

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
def load_user_loader(user_id):
    return load_user(user_id)


@socketio.on("message")
def handle_message(msg):
    print(f"Message: {msg}")
    send(msg, broadcast=True)


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


@app.route('/download')
@login_required
def download_db():
    # Format current datetime as MM-DD-YYYY_HH-MM-SS
    timestamp = datetime.now().strftime("%m-%d-%Y_%H-%M-%S")
    filename = f"backup_{timestamp}.db"

    return send_file(
        app.config['DATABASE'],
        as_attachment=True,
        download_name=filename
    )


@app.route('/restore_local', methods=['GET', 'POST'])
@login_required
def restore_db():
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename.endswith('.db'):
            filepath = app.config['DATABASE']
            file.save(filepath)  # Overwrite the existing DB
            flash('Database restored successfully.', 'success')
            return redirect(url_for('manage_backups'))
        else:
            flash('Please upload a valid .db file.', 'error')
            return redirect(request.url)

    # Render upload form on GET
    return render_template('/backups/restore_db.html')


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


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# FIXME: leaves import


# @app.route('/leaves/import', methods=['GET', 'POST'])
# @login_required
# def import_leaves():
#     leave_columns = [
#         'employee_id', 'leave_type', 'start_date', 'end_date', 'reason',
#         'type_of_leave', 'requested_by', 'requested_by_roles',
#         'verified_by', 'approved_by', 'branch', 'category'
#     ]

#     if request.method == 'POST':
#         f = request.files.get('excel_file')
#         if not f or f.filename == '':
#             flash('Please choose an Excel file.', 'error')
#             return redirect(request.url)

#         if not allowed_excel(f.filename):
#             flash('Supported formats: .xlsx or .xls', 'error')
#             return redirect(request.url)

#         try:
#             df = pd.read_excel(f)
#         except Exception as e:
#             flash(f'Could not read file: {e}', 'error')
#             return redirect(request.url)

#         missing = [c for c in leave_columns if c not in df.columns]
#         if missing:
#             flash(f'Missing columns: {", ".join(missing)}', 'error')
#             return redirect(request.url)

#         inserted, skipped = 0, 0
#         employees = []
#         with get_db_connection() as conn:
#             cursor = conn.cursor()
#             employees = conn.execute(
#                 'SELECT id, name FROM employees').fetchall()
#             for _, row in df.iterrows():
#                 if pd.isna(row['employee_id']) or pd.isna(row['leave_type']) or pd.isna(row['start_date']) or pd.isna(row['end_date']):
#                     skipped += 1
#                     continue

#                 start_date = pd.to_datetime(row['start_date'])
#                 end_date = pd.to_datetime(row['end_date'])

#                 # Default fallback values
#                 leave_hours = row.get('leave_hours', None)
#                 if pd.isna(leave_hours):
#                     service_count = (end_date - start_date).days + 1
#                     leave_hours = service_count * 8
#                 else:
#                     leave_hours = float(leave_hours)
#                     service_count = int(leave_hours / 8)

#                 cursor.execute("""
#                     INSERT INTO leaves (
#                         employee_id, leave_type, start_date, end_date, reason,
#                         type_of_leave, requested_by, requested_by_roles,
#                         verified_by, approved_by, branch, category,
#                         final_end_date, service_count, leave_hours
#                     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
#                 """, (
#                     row['employee_id'], row['leave_type'], row['start_date'],
#                     row['end_date'], row['reason'], row['type_of_leave'],
#                     row['requested_by'], row['requested_by_roles'],
#                     row['verified_by'], row['approved_by'], row['branch'],
#                     row['category'], row['end_date'], service_count, leave_hours
#                 ))
#                 # Get the inserted leave_id
#                 leave_id = cursor.lastrowid

#                 # Insert into user_leave (assuming one user_id per row)
#                 user_id = row['employee_id']
#                 cursor.execute('''
#                     INSERT INTO user_leave (user_id, leave_id)
#                     VALUES (?, ?)
#                 ''', (user_id, leave_id))
#                 inserted += 1

#             conn.commit()

#         flash(
#             f'Imported {inserted} leave entries ({skipped} skipped).', 'success')
#         return redirect(url_for('import_leaves'))

#     return render_template('leaves/import_leaves.html', employees=employees)

@app.route('/leaves/import', methods=['GET', 'POST'])
@login_required
def import_leaves():
    leave_columns = [
        'employee_id', 'leave_type', 'start_date', 'end_date', 'reason',
        'type_of_leave', 'requested_by', 'requested_by_roles',
        'verified_by', 'approved_by', 'branch', 'category'
    ]

    employees = []  # Define upfront to avoid UnboundLocalError

    if request.method == 'POST':
        f = request.files.get('excel_file')
        if not f or f.filename == '':
            flash('Please choose an Excel file.', 'error')
            return redirect(request.url)

        if not allowed_excel(f.filename):
            flash('Supported formats: .xlsx or .xls', 'error')
            return redirect(request.url)

        try:
            df = pd.read_excel(f)
        except Exception as e:
            flash(f'Could not read file: {e}', 'error')
            return redirect(request.url)

        missing = [c for c in leave_columns if c not in df.columns]
        if missing:
            flash(f'Missing columns: {", ".join(missing)}', 'error')
            return redirect(request.url)

        inserted, skipped = 0, 0
        with get_db_connection() as conn:
            cursor = conn.cursor()
            employees = conn.execute(
                'SELECT id, name FROM employees').fetchall()

            for _, row in df.iterrows():
                if pd.isna(row['employee_id']) or pd.isna(row['leave_type']) or pd.isna(row['start_date']) or pd.isna(row['end_date']):
                    skipped += 1
                    continue

                start_date = pd.to_datetime(row['start_date'])
                end_date = pd.to_datetime(row['end_date'])

                # Default fallback values
                leave_hours = row.get('leave_hours', None)
                if pd.isna(leave_hours):
                    service_count = (end_date - start_date).days + 1
                    leave_hours = service_count * 8
                else:
                    leave_hours = float(leave_hours)
                    service_count = int(leave_hours / 8)

                cursor.execute("""
                    INSERT INTO leaves (
                        employee_id, leave_type, start_date, end_date, reason,
                        type_of_leave, requested_by, requested_by_roles,
                        verified_by, approved_by, branch, category,
                        final_end_date, service_count, leave_hours
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['employee_id'], row['leave_type'], row['start_date'],
                    row['end_date'], row['reason'], row['type_of_leave'],
                    row['requested_by'], row['requested_by_roles'],
                    row['verified_by'], row['approved_by'], row['branch'],
                    row['category'], row['end_date'], service_count, leave_hours
                ))

                leave_id = cursor.lastrowid
                user_id = row['employee_id']
                cursor.execute('''
                    INSERT INTO user_leave (user_id, leave_id)
                    VALUES (?, ?)
                ''', (user_id, leave_id))

                inserted += 1

            conn.commit()

        flash(
            f'Imported {inserted} leave entries ({skipped} skipped).', 'success')
        return redirect(url_for('import_leaves'))

    # For GET request, fetch employees to pass to the template
    with get_db_connection() as conn:
        employees = conn.execute('SELECT id, name FROM employees').fetchall()

    return render_template('leaves/import_leaves.html', employees=employees)


@app.route('/leaves/import/template')
@login_required
def download_leave_import_template():
    # Define the columns required for the leave import
    columns = [
        'employee_id', 'leave_type', 'start_date', 'end_date', 'reason',
        'type_of_leave', 'requested_by', 'requested_by_roles',
        'verified_by', 'approved_by', 'branch', 'category',
        'final_end_date', 'service_count', 'leave_hours'
    ]

    # Optionally include a sample row
    sample_data = [{
        'employee_id': 1,
        'leave_type': 'annualLeave',
        'start_date': '2025-06-01',
        'end_date': '2025-06-05',
        'reason': 'Sick Leave',
        'type_of_leave': 'D',
        'requested_by': 'John Doe',
        'requested_by_roles': 20,
        'verified_by': '',
        'approved_by': '',
        'branch': 'KPT',
        'category': 'S',
        'final_end_date': '2025-06-05',
        'service_count': 5,
        'leave_hours': 40.0
    }]

    df = pd.DataFrame(sample_data)
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="leave_import_template.xlsx",
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@app.route('/leaves/<int:leave_id>', methods=['GET'])
@login_required
def view_leave_by_id(leave_id):
    with get_db_connection() as conn:
        leave = conn.execute("""
            SELECT
                l.id,
                l.employee_id,
                e.name AS employee_name,
                e.department,
                l.leave_type,
                l.type_of_leave,
                l.start_date,
                l.end_date,
                l.reason,
                l.service_count,
                l.leave_hours,
                l.requested_by,
                l.verified_by,
                l.approved_by,
                l.status,
                l.spm_status,
                l.dd_status,
                l.manager_status,
                l.branch,
                l.category
            FROM leaves l
            JOIN employees e ON l.employee_id = e.id
            WHERE l.id = ?
        """, (leave_id,)).fetchone()

    if leave is None:
        flash('Leave not found.', 'danger')
        return redirect(url_for('view_leaves'))

    return render_template('leaves/view_leave_by_id.html', leave=leave)


@app.route('/leaves/<int:leave_id>/edit', methods=['GET', 'POST'])
def edit_leave_admin(leave_id):
    conn = get_db_connection()
    leave = conn.execute(
        'SELECT * FROM leaves WHERE id = ?', (leave_id,)).fetchone()

    if not leave:
        flash('Leave record not found.', 'danger')
        return redirect(url_for('view_leaves'))

    if request.method == 'POST':
        leave_type = request.form['leave_type']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        status = request.form['status']

        conn.execute('''
            UPDATE leaves SET
                leave_type = ?, start_date = ?, end_date = ?, reason = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (leave_type, start_date, end_date, reason, status, leave_id))
        conn.commit()
        conn.close()

        flash('Leave updated successfully!', 'success')
        return redirect(url_for('view_leaves'))

    conn.close()
    return render_template('leaves/edit_leave_admin.html', leave=leave)


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


@app.route('/leaves/ccc/dashboard/<string:branch_name>', methods=['GET'])
def leaves_by_branch_and_ccc_dashboard(branch_name):
    if not current_user.is_authenticated or current_user.role_default != 35:
        return redirect(url_for('access_denied'))

    base_query = '''
        SELECT
            l.id,
            e.name AS employee_name,
            l.branch AS branch_name,
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
        WHERE ({conditions})
    '''

    if branch_name:
        conditions = '(l.branch = ? AND (l.type_of_leave = "H" OR l.requested_by_roles = 35)) AND l.requested_by_roles = 35'
        params = (branch_name,)
    else:
        conditions = '(l.type_of_leave = "H" OR l.requested_by_roles = 35) AND l.requested_by_roles = 35'
        params = ()

    query = base_query.format(conditions=conditions)

    try:
        with get_db_connection() as conn:
            leaves = conn.execute(query, params).fetchall()
            users = conn.execute("SELECT * FROM users").fetchall()
    except sqlite3.DatabaseError as e:
        return f"Database error: {e}", 500

    return render_template(
        'leaves/leaves_ccc_dashboard.html',
        leaves=leaves or [],
        branch_name=branch_name or '',
        users=users or []
    )


# TODO: PM Report
@app.route('/leaves/pm/report/<string:branch_name>', methods=['GET'])
def leaves_by_branch_and_pm_report(branch_name):
    if not current_user.is_authenticated or current_user.role_default != 140:
        return redirect(url_for('access_denied'))

    base_query = '''
        SELECT
            l.id,
            e.name AS employee_name,
            l.branch AS branch_name,
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
        WHERE ({conditions})
    '''

    if branch_name:
        # Enforce role 140 even when OR is used
        conditions = '(l.branch = ? AND (l.type_of_leave = "H" OR l.requested_by_roles = 140)) AND l.requested_by_roles = 140'
        params = (branch_name,)
    else:
        conditions = '(l.type_of_leave = "H" OR l.requested_by_roles = 140) AND l.requested_by_roles = 140'
        params = ()

    query = base_query.format(conditions=conditions)

    try:
        with get_db_connection() as conn:
            leaves = conn.execute(query, params).fetchall()
            users = conn.execute("SELECT * FROM users").fetchall()
    except sqlite3.DatabaseError as e:
        return f"Database error: {e}", 500

    return render_template(
        'leaves/leaves_pm_dashboard.html',
        leaves=leaves or [],
        branch_name=branch_name or '',
        users=users or []
    )


@app.route('/leaves/spm/report/<string:branch_name>', methods=['GET'])
def leaves_by_branch_and_spm_report(branch_name):
    if not current_user.is_authenticated or current_user.role_default != 145:
        return redirect(url_for('access_denied'))

    base_query = '''
        SELECT
            l.id,
            e.name AS employee_name,
            l.branch AS branch_name,
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
        WHERE ({conditions})
    '''

    if branch_name:
        # Enforce role 140 even when OR is used
        conditions = '(l.branch = ? AND (l.type_of_leave = "H" OR l.requested_by_roles = 145)) AND l.requested_by_roles = 145'
        params = (branch_name,)
    else:
        conditions = '(l.type_of_leave = "H" OR l.requested_by_roles = 145) AND l.requested_by_roles = 145'
        params = ()

    query = base_query.format(conditions=conditions)

    try:
        with get_db_connection() as conn:
            leaves = conn.execute(query, params).fetchall()
            users = conn.execute("SELECT * FROM users").fetchall()
    except sqlite3.DatabaseError as e:
        return f"Database error: {e}", 500

    return render_template(
        'leaves/leaves_pm_dashboard.html',
        leaves=leaves or [],
        branch_name=branch_name or '',
        users=users or []
    )


# @app.route('/leaves/ccc/verify/<string:branch_name>', methods=['GET'])
# def leaves_by_branch_and_ccc_category(branch_name):
#     if not current_user.is_authenticated or current_user.role_default != 35:
#         return redirect(url_for('access_denied'))

#     if branch_name:
#         query = '''
#          SELECT
#             l.id,
#             e.name AS employee_name,
#             e.branch AS branch_name,
#             l.leave_type,
#             l.start_date,
#             l.end_date,
#             l.reason,
#             l.status,
#             l.type_of_leave,
#             l.verified_by,
#             l.approved_by,
#             l.leave_hours,
#             l.service_count,
#             l.requested_by
#         FROM leaves l
#         LEFT JOIN employees e ON l.employee_id = e.id
#         WHERE e.branch = ?
#         AND (
#             l.category IS NULL
#             OR l.category = 'S'
#             OR (l.type_of_leave = 'H' AND l.requested_by_roles = 20)
#         )
#         AND (l.requested_by_roles IS NULL OR l.requested_by_roles != 35)

#         '''
#         params = (branch_name,)
#     else:
#         query = '''
#         SELECT
#             l.id,
#             e.name AS employee_name,
#             e.branch AS branch_name,
#             l.leave_type,
#             l.start_date,
#             l.end_date,
#             l.reason,
#             l.status,
#             l.type_of_leave,
#             l.verified_by,
#             l.approved_by,
#             l.leave_hours,
#             l.service_count,
#             l.requested_by
#         FROM leaves l
#         LEFT JOIN employees e ON l.employee_id = e.id
#         WHERE e.branch = ?
#         AND (
#             l.category IS NULL
#             OR l.category = 'S'
#             OR l.type_of_leave = 'H'
#             OR l.requested_by_roles = 20
#         )
#         AND (l.type_of_leave = 'H' AND l.requested_by_roles = 20)
#         '''
#         params = ()

#     try:
#         with get_db_connection() as conn:
#             leaves = conn.execute(query, params).fetchall()
#     except sqlite3.DatabaseError as e:
#         return f"Database error: {e}", 500

#     return render_template('leaves/leaves_ccc_verify.html', leaves=leaves, branch_name=branch_name)

@app.route('/leaves/ccc/verify/<string:branch_name>', methods=['GET'])
def leaves_by_branch_and_ccc_category(branch_name):
    if not current_user.is_authenticated or current_user.role_default != 35:
        return redirect(url_for('access_denied'))

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
            l.requested_by,
            l.requested_by_roles
        FROM leaves l
        LEFT JOIN employees e ON l.employee_id = e.id
        WHERE e.branch = ?
        AND l.requested_by_roles != 140
        AND l.requested_by_roles != 145
        AND l.requested_by_roles != 35
        AND (
            l.category IS NULL
            OR l.category = 'S'
            OR (
                l.type_of_leave = 'H' AND l.requested_by_roles = 20
            )
        )
        AND (
            l.category IS NULL OR l.category NOT IN ('M', 'L')
        )
    '''
    params = (branch_name,)

    try:
        with get_db_connection() as conn:
            leaves = conn.execute(query, params).fetchall()
    except sqlite3.DatabaseError as e:
        return f"Database error: {e}", 500

    return render_template('leaves/leaves_ccc_verify.html', leaves=leaves, branch_name=branch_name)


@app.route('/leaves/spm', methods=['GET'])
def leaves_by_branch_and_spm():
    if not current_user.is_authenticated or current_user.role_default != 145:
        return redirect(url_for('access_denied'))

    zone_id = current_user.zone_id
    if zone_id is None:
        flash("Zone ID not found for the current user!", "danger")
        return redirect(url_for('dashboard'))

    branch_name = request.args.get('branch_name', 'All')

    try:
        with get_db_connection() as conn:
            # Fetch zone
            zone = conn.execute(
                "SELECT * FROM zones WHERE ID = ?", (zone_id,)
            ).fetchone()
            if not zone:
                flash("Zone not found!", "danger")
                return redirect(url_for('dashboard'))

            # Fetch branches in the zone
            branches_in_zone = conn.execute("""
                SELECT b.ID, b.Branch
                FROM branches b
                JOIN zone_branch zb ON b.ID = zb.branch_id
                WHERE zb.zone_id = ?
            """, (zone_id,)).fetchall()

            branch_names = [b["Branch"] for b in branches_in_zone]

            # Prepare SQL condition
            if branch_name == "All" or not branch_name:
                if not branch_names:
                    flash("No branches found in your zone.", "warning")
                    return redirect(url_for('dashboard'))
                placeholders = ', '.join(['?'] * len(branch_names))
                where_clause = f"l.branch IN ({placeholders})"
                params = tuple(branch_names)
            else:
                where_clause = "l.branch = ?"
                params = (branch_name,)
            query = f"""
                SELECT
                    l.id,
                    l.requested_by AS employee_name,
                    l.branch AS branch_name,
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
                    l.requested_by,
                    l.requested_by_roles
                FROM leaves l
                LEFT JOIN employees e ON l.employee_id = e.id
                WHERE {where_clause}
                
                AND l.requested_by_roles IN (35, 140)
                AND (
                    l.category = 'M'
                    OR (l.category = 'L' AND l.requested_by_roles != 140)
                    OR (l.type_of_leave IN ('H', 'D'))
                    OR (l.requested_by_roles = 140 AND l.type_of_leave = 'H')
                )
                AND NOT (l.requested_by_roles = 140 AND l.category = 'L')
                OR (l.requested_by_roles = 140 AND l.type_of_leave = 'H')
                OR (l.requested_by_roles = 20 AND l.category = 'L')
            """

            leaves = conn.execute(query, params).fetchall()

    except sqlite3.DatabaseError as e:
        flash(f"Database error: {e}", "danger")
        return redirect(url_for('dashboard'))

    return render_template(
        'leaves/leaves_spm_approve.html',
        leaves=leaves,
        branch_name=branch_name,
        branches_in_zone=branches_in_zone,
        zone=zone
    )


@app.route('/leaves/hrd', methods=['GET'])
def leaves_by_branch_and_hrd():
    if not current_user.is_authenticated or current_user.role_default != 160:
        return redirect(url_for('access_denied'))

    branch_name = request.args.get('branch_name', 'All')

    try:
        with get_db_connection() as conn:
            branches = conn.execute(
                "SELECT DISTINCT Branch FROM branches").fetchall()
            branch_names = [b["Branch"] for b in branches]

            if branch_name == "All" or not branch_name:
                placeholders = ', '.join(['?'] * len(branch_names))
                where_clause = f"l.branch IN ({placeholders})"
                params = tuple(branch_names)
            else:
                where_clause = "l.branch = ?"
                params = (branch_name,)

            query = f"""
                SELECT
                    l.id,
                    l.requested_by AS employee_name,
                    l.branch AS branch_name,
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
                WHERE {where_clause}
             
                AND (
                        (l.requested_by_roles = 140 AND l.category = 'L')
                        OR (l.requested_by_roles = 145 AND l.category = 'L')
                        OR (l.requested_by_roles = 145 AND l.category = 'M')
                        OR (l.requested_by_roles = 145 AND l.category = 'S')
                        OR (l.requested_by_roles = 145  AND l.type_of_leave = 'H')
                )
                AND l.status = 'Pending'
            """
            leaves = conn.execute(query, params).fetchall()

    except sqlite3.DatabaseError as e:
        return f"Database error: {e}", 500

    return render_template(
        'leaves/leaves_hrd_approve.html',
        leaves=leaves,
        branch_name=branch_name,
        branches_in_zone=branches,
        zone=None
    )


@app.route('/leaves/gm', methods=['GET'])
def leaves_by_gm():
    if not current_user.is_authenticated or current_user.role_default != 180:
        return redirect(url_for('access_denied'))

    query = '''
        SELECT
            l.id,
            e.name AS employee_name,
            l.branch AS branch_name,
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
            l.requested_by,
            l.requested_from
        FROM leaves l
        LEFT JOIN employees e ON l.employee_id = e.id
        WHERE
            (
                (l.category = 'L' AND l.verified_by IS NULL AND l.approved_by IS NULL)
                OR (l.category = 'M' AND l.requested_by_roles = 140)
                OR (l.category = 'M' AND l.requested_by_roles = 140)
                OR (l.category = 'L' AND l.requested_by_roles = 140)
                OR (l.category = 'L' AND l.requested_by_roles = 20)
                OR (l.category = 'L' AND l.requested_by_roles = 35)
                OR (l.requested_by_roles = 145 AND l.category IN ('L', 'M', 'S'))
                OR (l.requested_by_roles = 145 AND l.type_of_leave = 'H')
            )
            AND (
                l.status = 'Approved' AND
                l.verified_by IS NOT NULL AND
                (l.approved_by IS NULL OR TRIM(l.approved_by) = '')

            )
            OR (
                l.requested_by_roles = 20 
                AND l.category IN ('L', 'M')  
                AND l.verified_by IS NOT NULL 
                AND l.requested_from IS NOT NULL
                AND (l.approved_by IS NULL OR TRIM(l.approved_by) = '')
            )
    '''
    try:
        with get_db_connection() as conn:
            leaves = conn.execute(query).fetchall()
            employees = conn.execute('SELECT * FROM employees').fetchall()
    except sqlite3.DatabaseError as e:
        return f"Database error: {e}", 500

    return render_template(
        'leaves/leaves_gm_approve.html',
        leaves=leaves or [],
        employees=employees
    )


# @app.route('/leaves/department/crd/<string:branch_name>', methods=['GET'])
# @login_required
# def leaves_by_department_crd(branch_name):
#     if current_user.role_default == 200 and current_user.branch and current_user.branch != branch_name:
#         return redirect(url_for('filter_leaves_by_branch_name', branch_name=current_user.branch))

#     elif current_user.role_default != 200:
#         return redirect(url_for('access_denied'))

#     app.logger.debug(f"Filtering by branch: {branch_name}")

#     query = '''
#         SELECT
#             l.id,
#             l.requested_by AS employee_name,
#             l.branch AS branch_name,
#             l.leave_type,
#             l.start_date,
#             l.end_date,
#             l.reason,
#             l.status,
#             l.type_of_leave,
#             l.verified_by,
#             l.approved_by,
#             l.leave_hours,
#             l.service_count,
#             l.requested_by,
#             l.requested_by_roles,
#             l.requested_from

#         FROM leaves l
#         LEFT JOIN employees e ON l.employee_id = e.id
#         WHERE (
#             l.branch = ?
#             ANDl.requested_from  == 'CRD'
#             AND l.requested_by_roles != 140
#             AND l.requested_by_roles != 145

#             AND (
#                 l.category != 'L'
#                 OR l.category IS NULL
#                 OR l.type_of_leave = 'H'
#                 OR (
#                     l.category = 'S' AND l.verified_by IS NOT NULL
#                 )
#                 OR (
#                     l.category = 'M' AND (
#                         l.verified_by IS NULL OR l.requested_by_roles = 35
#                     )
#                 )
#             )
#         )
#         ORDER BY l.start_date DESC;
#     '''

#     params = (branch_name,)

#     try:
#         with get_db_connection() as conn:
#             leaves = conn.execute(query, params).fetchall()
#     except sqlite3.DatabaseError as e:
#         app.logger.error(f"Database error: {e}")
#         return "An error occurred while retrieving data. Please try again later.", 500

#     return render_template('leaves/leaves_deparment_crd.html', leaves=leaves, branch_name=branch_name)


@app.route('/leaves/department/crd/<string:branch_name>', methods=['GET'])
@login_required
def leaves_by_department_crd(branch_name):
    if current_user.role_default == 200 and current_user.branch and current_user.branch != branch_name:
        return redirect(url_for('filter_leaves_by_branch_name', branch_name=current_user.branch))

    elif current_user.role_default != 200:
        return redirect(url_for('access_denied'))

    app.logger.debug(f"Filtering by branch: {branch_name}")

    query = '''
        SELECT
            l.id,
            l.requested_by AS employee_name,
            l.branch AS branch_name,
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
            l.requested_by,
            l.requested_by_roles,
            l.requested_from
        FROM leaves l
        LEFT JOIN employees e ON l.employee_id = e.id
       WHERE
            l.branch = ?
            AND l.requested_from = 'CRD'
            AND (
                (
                    l.requested_by_roles = 20 
                    AND l.verified_by IS  NULL 
                    AND (l.approved_by IS NULL OR TRIM(l.approved_by) = '')
                )
                OR
                (
                    l.status = 'Pending'
                    AND l.verified_by IS  NULL
                    AND (l.approved_by IS NULL OR TRIM(l.approved_by) = '')
                )
            )
        ORDER BY l.start_date DESC;
    '''

    params = (branch_name,)

    try:
        with get_db_connection() as conn:
            leaves = conn.execute(query, params).fetchall()
    except sqlite3.DatabaseError as e:
        app.logger.error(f"Database error: {e}")
        return "An error occurred while retrieving data. Please try again later.", 500

    return render_template('leaves/leaves_department_crd.html', leaves=leaves, branch_name=branch_name)


@app.route('/leaves/branch/<string:branch_name>', methods=['GET'])
@login_required
def filter_leaves_by_branch_name(branch_name):
    if current_user.role_default == 140 and current_user.branch and current_user.branch != branch_name:
        return redirect(url_for('filter_leaves_by_branch_name', branch_name=current_user.branch))

    elif current_user.role_default != 140:
        return redirect(url_for('access_denied'))

    app.logger.debug(f"Filtering by branch: {branch_name}")

    query = '''
        SELECT
            l.id,
            l.requested_by AS employee_name,
            l.branch AS branch_name,
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
            l.requested_by,
            l.requested_by_roles
        FROM leaves l
        LEFT JOIN employees e ON l.employee_id = e.id
        WHERE (
            l.branch = ?
            AND l.requested_by_roles != 140
            AND l.requested_by_roles != 145
            AND (
                l.category != 'L'
                OR l.category IS NULL
                OR l.type_of_leave = 'H'
                OR (
                    l.category = 'S' AND l.verified_by IS NOT NULL
                )
                OR (
                    l.category = 'M' AND (
                        l.verified_by IS NULL OR l.requested_by_roles = 35
                    )
                )
            )
        )
        ORDER BY l.start_date DESC;
    '''

    params = (branch_name,)

    try:
        with get_db_connection() as conn:
            leaves = conn.execute(query, params).fetchall()
    except sqlite3.DatabaseError as e:
        app.logger.error(f"Database error: {e}")
        return "An error occurred while retrieving data. Please try again later.", 500

    return render_template('leaves/leaves_branch.html', leaves=leaves, branch_name=branch_name)


@app.route('/leave_hours/ccc/add/<string:branch>', methods=['GET', 'POST'])
@login_required
def add_leave_hours_ccc(branch):
    employees = []
    #   employees = conn.execute('SELECT id, name FROM employees').fetchall()
    users = []
    user_branch = branch if not current_user.is_authenticated else current_user.branch

    with get_db_connection() as conn:
        employees = conn.execute('SELECT id, name FROM employees').fetchall()
        users = conn.execute(
            'SELECT id, username FROM users WHERE RoleDefault IN (140) AND branch = ? AND Active = 1',
            (user_branch,)
        ).fetchall()

    if request.method == 'POST':
        employee_id = request.form['employee_id']
        leave_type = request.form['leave_type']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        branch = request.form['branch']
        requested_by = request.form['requested_by']
        user_ids = request.form.getlist('user_ids')
        requested_by_roles = request.form['requested_by_roles']

        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d %H:%M")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d %H:%M")

        # Validations...
        if end_date_obj <= start_date_obj:
            flash("កាលបរិច្ឆេទ/ពេលវេលាបញ្ចប់ត្រូវតែបន្ទាប់...", "error")
            return redirect(url_for('add_leave_hours_ccc', branch=branch))

        # Disallow leave hours on Saturday and Sunday
        if start_date_obj.weekday() >= 5 or end_date_obj.weekday() >= 5:
            flash("មិនអាចដាក់ម៉ោងឈប់សម្រាកនៅថ្ងៃសៅរ៍ ឬ អាទិត្យបានទេ។", "error")
            return redirect(url_for('add_leave_hours_ccc', branch=branch))

        if start_date_obj.hour < 7:
            flash("ម៉ោងឈប់សម្រាកត្រូវតែចាប់ពីម៉ោង 7:00 ព្រឹក...", "error")
            return redirect(url_for('add_leave_hours_ccc', branch=branch))

        if start_date_obj.hour > 17 or (start_date_obj.hour == 17 and start_date_obj.minute > 0) or \
           end_date_obj.hour > 17 or (end_date_obj.hour == 17 and end_date_obj.minute > 0):
            flash("ម៉ោងឈប់សម្រាកត្រូវតែចប់មុនម៉ោង 5:00 ល្ងាច...", "error")
            return redirect(url_for('add_leave_hours_ccc', branch=branch))

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

        # Check if leave hours are greater than 8
        if leave_hours > 8:
            flash("ម៉ោងឈប់សម្រាកមិនគួរធំជាង 8 ម៉ោងទេ។", "error")
            return redirect(url_for('add_leave_hours_ccc', branch=branch))

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO leaves(employee_id, leave_type, start_date, end_date, reason, leave_hours, requested_by, type_of_leave, branch, verified_by,requested_by_roles)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (employee_id, leave_type, start_date, end_date, reason, leave_hours, requested_by, 'H', branch, "Not required", requested_by_roles))

            leave_id = cursor.lastrowid

            for user_id in user_ids:
                cursor.execute('''
                    INSERT INTO user_leave (user_id, leave_id)
                    VALUES (?, ?)
                ''', (user_id, leave_id))

            conn.commit()

        return redirect(url_for('leaves_by_branch_and_ccc_dashboard', branch_name=branch))

    return render_template('/leaves/add_leave_hours_ccc.html', employees=employees, users=users, branch=branch)


@app.route('/leave_hours/pm/add/<string:branch>', methods=['GET', 'POST'])
@login_required
def add_leave_hours_pm(branch):
    employees = []
    users = []
    user_branch = branch if not current_user.is_authenticated else current_user.branch

    with get_db_connection() as conn:
        employees = conn.execute('SELECT id, name FROM employees').fetchall()
        # users = conn.execute(
        #     'SELECT id, username FROM users WHERE RoleDefault IN (145) AND branch = ? AND Active = 1',
        #     (user_branch,)
        # ).fetchall()

        users = []
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
                        users.append(user_info)
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
                users = conn.execute('''
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
                        AND Active = 1
                        AND u.ZoneID = ?
                ''', (zone_id,)).fetchall()

            else:
                print("Branch is NOT in zone_branch ❌")
        else:
            print("Branch not found.")

    if request.method == 'POST':
        employee_id = request.form['employee_id']
        leave_type = request.form['leave_type']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        branch = request.form['branch']
        requested_by = request.form['requested_by']
        user_ids = request.form.getlist('user_ids')
        requested_by_roles = request.form['requested_by_roles']

        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d %H:%M")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d %H:%M")

        # Validations...
        if end_date_obj <= start_date_obj:
            flash("កាលបរិច្ឆេទ/ពេលវេលាបញ្ចប់ត្រូវតែបន្ទាប់...", "error")
            return redirect(url_for('add_leave_hours_ccc', branch=branch))

        # Disallow leave hours on Saturday and Sunday
        if start_date_obj.weekday() >= 5 or end_date_obj.weekday() >= 5:
            flash("មិនអាចដាក់ម៉ោងឈប់សម្រាកនៅថ្ងៃសៅរ៍ ឬ អាទិត្យបានទេ។", "error")
            return redirect(url_for('add_leave_hours_ccc', branch=branch))

        if start_date_obj.hour < 7:
            flash("ម៉ោងឈប់សម្រាកត្រូវតែចាប់ពីម៉ោង 7:00 ព្រឹក...", "error")
            return redirect(url_for('add_leave_hours_ccc', branch=branch))

        if start_date_obj.hour > 17 or (start_date_obj.hour == 17 and start_date_obj.minute > 0) or \
           end_date_obj.hour > 17 or (end_date_obj.hour == 17 and end_date_obj.minute > 0):
            flash("ម៉ោងឈប់សម្រាកត្រូវតែចប់មុនម៉ោង 5:00 ល្ងាច...", "error")
            return redirect(url_for('add_leave_hours_ccc', branch=branch))

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

        # Check if leave hours are greater than 8
        if leave_hours > 8:
            flash("ម៉ោងឈប់សម្រាកមិនគួរធំជាង 8 ម៉ោងទេ។", "error")
            return redirect(url_for('add_leave_hours_ccc', branch=branch))

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO leaves(employee_id, leave_type, start_date, end_date, reason, leave_hours, requested_by, type_of_leave, branch, verified_by, requested_by_roles)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?  , ?)
            ''', (employee_id, leave_type, start_date, end_date, reason, leave_hours, requested_by, 'H', branch, "Not required", requested_by_roles))

            leave_id = cursor.lastrowid

            for user_id in user_ids:
                cursor.execute('''
                    INSERT INTO user_leave (user_id, leave_id)
                    VALUES (?, ?)
                ''', (user_id, leave_id))

            conn.commit()

        return redirect(url_for('leaves_by_branch_and_pm_report', branch_name=branch))

    return render_template('/leaves/add_leave_hours_pm.html', employees=employees, users=users, branch=branch)


@app.route('/leave_hours/spm/add/<string:branch>', methods=['GET', 'POST'])
@login_required
def add_leave_hours_spm(branch):
    employees = []
    users = []
    user_branch = branch if not current_user.is_authenticated else current_user.branch

    with get_db_connection() as conn:
        employees = conn.execute('SELECT id, name FROM employees').fetchall()
        users = []
        users2 = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault = 180 AND Active = 1'
        ).fetchall()

        users3 = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault = 160 AND Active = 1'
        ).fetchall()

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
                        users.append(user_info)
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
                users = conn.execute('''
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
                        AND Active = 1
                        AND u.ZoneID = ?
                ''', (zone_id,)).fetchall()

            else:
                print("Branch is NOT in zone_branch ❌")
        else:
            print("Branch not found.")

    if request.method == 'POST':
        employee_id = request.form['employee_id']
        leave_type = request.form['leave_type']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        branch = request.form['branch']
        requested_by = request.form['requested_by']
        user_ids = request.form.getlist('user_ids')
        requested_by_roles = request.form['requested_by_roles']

        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d %H:%M")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d %H:%M")

        # Validations...
        if end_date_obj <= start_date_obj:
            flash("កាលបរិច្ឆេទ/ពេលវេលាបញ្ចប់ត្រូវតែបន្ទាប់...", "error")
            return redirect(url_for('add_leave_hours_ccc', branch=branch))

        # Disallow leave hours on Saturday and Sunday
        if start_date_obj.weekday() >= 5 or end_date_obj.weekday() >= 5:
            flash("មិនអាចដាក់ម៉ោងឈប់សម្រាកនៅថ្ងៃសៅរ៍ ឬ អាទិត្យបានទេ។", "error")
            return redirect(url_for('add_leave_hours_ccc', branch=branch))

        if start_date_obj.hour < 7:
            flash("ម៉ោងឈប់សម្រាកត្រូវតែចាប់ពីម៉ោង 7:00 ព្រឹក...", "error")
            return redirect(url_for('add_leave_hours_ccc', branch=branch))

        if start_date_obj.hour > 17 or (start_date_obj.hour == 17 and start_date_obj.minute > 0) or \
           end_date_obj.hour > 17 or (end_date_obj.hour == 17 and end_date_obj.minute > 0):
            flash("ម៉ោងឈប់សម្រាកត្រូវតែចប់មុនម៉ោង 5:00 ល្ងាច...", "error")
            return redirect(url_for('add_leave_hours_ccc', branch=branch))

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

        # Check if leave hours are greater than 8
        if leave_hours > 8:
            flash("ម៉ោងឈប់សម្រាកមិនគួរធំជាង 8 ម៉ោងទេ។", "error")
            return redirect(url_for('add_leave_hours_ccc', branch=branch))

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO leaves(employee_id, leave_type, start_date, end_date, reason, leave_hours, requested_by, type_of_leave, branch, verified_by, requested_by_roles)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?  , ?)
            ''', (employee_id, leave_type, start_date, end_date, reason, leave_hours, requested_by, 'H', branch, "Not required", requested_by_roles))

            leave_id = cursor.lastrowid

            for user_id in user_ids:
                cursor.execute('''
                    INSERT INTO user_leave (user_id, leave_id)
                    VALUES (?, ?)
                ''', (user_id, leave_id))

            conn.commit()

        return redirect(url_for('leaves_by_branch_and_spm_report', branch_name=branch))

    return render_template('/leaves/add_leave_hours_spm.html', employees=employees, users=users, users2=users2, users3=users3, branch=branch)


@app.route('/leave_hours/add/<string:branch>', methods=['GET', 'POST'])
@login_required
def add_leave_hours(branch):
    employees = []
    users = []
    user_branch = branch if not current_user.is_authenticated else current_user.branch

    with get_db_connection() as conn:
        employees = conn.execute('SELECT id, name FROM employees').fetchall()
        users = conn.execute(
            'SELECT id, username FROM users WHERE RoleDefault IN (35,140) AND branch = ? AND Active = 1',
            (user_branch,)
        ).fetchall()

    if request.method == 'POST':
        employee_id = request.form['employee_id']
        leave_type = request.form['leave_type']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        branch = request.form['branch']
        requested_by = request.form['requested_by']
        user_ids = request.form.getlist('user_ids')
        requested_by_roles = request.form['requested_by_roles']

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

        # Check if leave hours are greater than 8
        if leave_hours > 8:
            flash("ម៉ោងឈប់សម្រាកមិនគួរធំជាង 8 ម៉ោងទេ។", "error")
            return redirect(url_for('add_leave_hours', branch=branch))

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO leaves(employee_id, leave_type, start_date, end_date, reason, leave_hours, requested_by, type_of_leave, branch, requested_by_roles)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (employee_id, leave_type, start_date, end_date, reason, leave_hours, requested_by, 'H', branch, requested_by_roles))

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


@app.route('/leave_days_hq/add/<string:branch>', methods=['GET', 'POST'])
@login_required
def add_leave_days_hq(branch):
    user_branch = current_user.branch if current_user.is_authenticated else branch
    current_user_department = current_user.department if current_user.department else ''
    print(current_user_department, 'dasdasd')

    with get_db_connection() as conn:
        employees = conn.execute(
            'SELECT id, name, branch FROM employees'
        ).fetchall()

        users = conn.execute(
            '''
            SELECT id, username, branch FROM users
            WHERE RoleDefault IN (35, 140)
              AND branch = ?
              AND Active = 1
            ''', (user_branch,)
        ).fetchall()

        users2 = conn.execute(
            '''
            SELECT u.id, u.username, u.branch, e.department
            FROM users u
            INNER JOIN employees e ON u.id = e.user_id
            WHERE u.branch = ?
              AND e.department = ?
              AND u.RoleDefault >= 200
              AND u.Active = 1
            ''', (user_branch, current_user_department)
        ).fetchall()

        print(users2, 'users2')

        users4 = conn.execute(
            '''
            SELECT id, username, branch FROM users
            WHERE RoleDefault = 180
              AND Active = 1
            '''
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
        requested_by_roles = request.form.getlist('requested_by_roles')
        requested_from = request.form['requested_from']

        branch = user_branch

        current_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        holiday_labels = [holiday["label"]
                          for holiday in get_holidays(current_date.year)]
        public_holidays_str = ",".join(holiday_labels)

        result = calculate_add_day_and_final_end_date(
            start_date, end_date, public_holidays_str)
        excluded_days = result['ExcludedDays']
        final_end_date = result['FinalEndDate']
        final_end_date_obj = datetime.strptime(str(final_end_date), "%Y-%m-%d")
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")

        service_count = calculate_service_count_1(
            start_date_obj, final_end_date_obj)

        category = "S" if service_count <= 2 else "M" if service_count <= 5 else "L"

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO leaves (
                    employee_id, leave_type, start_date, end_date, reason,
                    service_count, type_of_leave, requested_by, category, branch,
                    excluded_days, final_end_date, requested_by_roles, requested_from
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                employee_id, leave_type, start_date_obj.date(), final_end_date_obj.date(),
                reason, service_count, type_of_leave, requested_by, category, branch,
                excluded_days, final_end_date_obj.date(), ','.join(
                    requested_by_roles), requested_from
            ))

            leave_id = cursor.lastrowid

            for user_id in user_ids:
                cursor.execute(
                    'INSERT INTO user_leave (user_id, leave_id) VALUES (?, ?)',
                    (user_id, leave_id)
                )

            conn.commit()

        if current_user.role_default == 35:
            return redirect(url_for('leaves_by_branch_and_ccc_dashboard', branch_name=current_user.branch))
        else:
            return redirect(url_for('view_leaves'))

    return render_template(
        'leaves/add_hq_leaves_days.html',
        employees=employees,
        users=users,
        users2=users2,
        users4=users4,
        branch=user_branch
    )


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
                        AND Active = 1
                        AND u.ZoneID = ?
                ''', (zone_id,)).fetchall()

            else:
                print("Branch is NOT in zone_branch ❌")
        else:
            print("Branch not found.")
        employees = conn.execute(
            'SELECT id, name, branch FROM employees').fetchall()
        users = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault IN (35,140) AND branch = ? AND Active = 1', (
                user_branch,)
        ).fetchall()
        users2 = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault IN (140) AND branch = ? AND Active = 1', (
                user_branch,)
        ).fetchall()
        users4 = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault = 180 AND Active = 1'
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
        requested_by_roles = request.form.getlist('requested_by_roles')

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
                INSERT INTO leaves (employee_id, leave_type, start_date, end_date, reason, service_count, type_of_leave, requested_by, category, branch, excluded_days, final_end_date, requested_by_roles)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                employee_id, leave_type, start_date_obj.date(), final_end_date_obj.date(),
                reason, service_count, type_of_leave, requested_by, category, branch, excluded_days, final_end_date_obj.date(
                ), ','.join(requested_by_roles)
            ))

            leave_id = cursor.lastrowid

            for user_id in user_ids:
                cursor.execute('''
                    INSERT INTO user_leave (user_id, leave_id)
                    VALUES (?, ?)
                ''', (user_id, leave_id))

            conn.commit()
        if current_user.role_default == 35:
            return redirect(url_for('leaves_by_branch_and_ccc_dashboard', branch_name=current_user.branch))
        else:
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


# Leave days for CCC
@app.route('/leave_days_ccc/add/<string:branch>', methods=['GET', 'POST'])
@login_required
def add_leave_days_ccc(branch):
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
                        AND Active = 1
                        AND u.ZoneID = ?
                ''', (zone_id,)).fetchall()

            else:
                print("Branch is NOT in zone_branch ❌")
        else:
            print("Branch not found.")
        employees = conn.execute(
            'SELECT id, name, branch FROM employees').fetchall()
        users = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault IN (140) AND branch = ? AND Active = 1', (
                user_branch,)
        ).fetchall()
        users2 = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault IN (140) AND branch = ? AND Active = 1', (
                user_branch,)
        ).fetchall()
        users4 = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault = 180 AND Active = 1'
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
        requested_by_roles = request.form.getlist('requested_by_roles')

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
                INSERT INTO leaves (employee_id, leave_type, start_date, end_date, reason, service_count, type_of_leave, requested_by, category, branch, excluded_days, final_end_date, requested_by_roles)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                employee_id, leave_type, start_date_obj.date(), final_end_date_obj.date(),
                reason, service_count, type_of_leave, requested_by, category, branch, excluded_days, final_end_date_obj.date(
                ), ','.join(requested_by_roles)
            ))

            leave_id = cursor.lastrowid

            for user_id in user_ids:
                cursor.execute('''
                    INSERT INTO user_leave (user_id, leave_id)
                    VALUES (?, ?)
                ''', (user_id, leave_id))

            conn.commit()

        if current_user.role_default == 35:
            return redirect(url_for('leaves_by_branch_and_ccc_dashboard', branch_name=current_user.branch))
        else:
            return redirect(url_for('view_leaves'))

    return render_template(
        'leaves/leave_days_ccc.html',
        employees=employees,
        users=users,
        users2=users2,
        users3=users3,
        users4=users4,
        branch=user_branch
    )


@app.route('/leave_days/pm/add/<string:branch>', methods=['GET', 'POST'])
@login_required
def leave_days_pm(branch):
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
                        AND Active = 1
                        AND u.ZoneID = ?
                ''', (zone_id,)).fetchall()

            else:
                print("Branch is NOT in zone_branch ❌")
        else:
            print("Branch not found.")
        employees = conn.execute(
            'SELECT id, name, branch FROM employees').fetchall()
        users = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault IN (140) AND branch = ? AND Active = 1', (
                user_branch,)
        ).fetchall()
        users2 = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault IN (140) AND branch = ? AND Active = 1', (
                user_branch,)
        ).fetchall()
        users4 = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault = 180 AND Active = 1'
        ).fetchall()

        users5 = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault = 160 AND Active = 1'
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
        requested_by_roles = request.form.getlist('requested_by_roles')

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
                INSERT INTO leaves (employee_id, leave_type, start_date, end_date, reason, service_count, type_of_leave, requested_by, category, branch, excluded_days, final_end_date, requested_by_roles)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                employee_id, leave_type, start_date_obj.date(), final_end_date_obj.date(),
                reason, service_count, type_of_leave, requested_by, category, branch, excluded_days, final_end_date_obj.date(
                ), ','.join(requested_by_roles)
            ))

            leave_id = cursor.lastrowid

            for user_id in user_ids:
                cursor.execute('''
                    INSERT INTO user_leave (user_id, leave_id)
                    VALUES (?, ?)
                ''', (user_id, leave_id))

            conn.commit()

        return redirect(url_for('leaves_by_branch_and_pm_report', branch_name=current_user.branch))

    return render_template(
        'leaves/leave_days_pm.html',
        employees=employees,
        users=users,
        users2=users2,
        users3=users3,
        users4=users4,
        users5=users5,
        branch=user_branch
    )


@app.route('/leave_days/spm/add/<string:branch>', methods=['GET', 'POST'])
@login_required
def leave_days_spm(branch):
    user_branch = current_user.branch

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
                        AND Active = 1
                        AND u.ZoneID = ?
                ''', (zone_id,)).fetchall()

            else:
                print("Branch is NOT in zone_branch ❌")
        else:
            print("Branch not found.")
        employees = conn.execute(
            'SELECT id, name, branch FROM employees').fetchall()
        users = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault IN (140) AND branch = ? AND Active = 1', (
                user_branch,)
        ).fetchall()
        users2 = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault IN (140) AND branch = ? AND Active = 1', (
                user_branch,)
        ).fetchall()
        users4 = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault = 180 AND Active = 1'
        ).fetchall()

        users5 = conn.execute(
            'SELECT id, username, branch FROM users WHERE RoleDefault = 160 AND Active = 1'
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
        requested_by_roles = request.form.getlist('requested_by_roles')

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
                INSERT INTO leaves (employee_id, leave_type, start_date, end_date, reason, service_count, type_of_leave, requested_by, category, branch, excluded_days, final_end_date, requested_by_roles)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                employee_id, leave_type, start_date_obj.date(), final_end_date_obj.date(),
                reason, service_count, type_of_leave, requested_by, category, branch, excluded_days, final_end_date_obj.date(
                ), ','.join(requested_by_roles)
            ))

            leave_id = cursor.lastrowid

            for user_id in user_ids:
                cursor.execute('''
                    INSERT INTO user_leave (user_id, leave_id)
                    VALUES (?, ?)
                ''', (user_id, leave_id))

            conn.commit()

        return redirect(url_for('leaves_by_branch_and_spm_report', branch_name=current_user.branch))

    return render_template(
        'leaves/leave_days_spm.html',
        employees=employees,
        users=users,
        users2=users2,
        users3=users3,
        users4=users4,
        users5=users5,
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


# @app.route('/leave/edit_spm_approve/<int:id>', methods=['GET', 'POST'])
# def edit_leave_spm_approve(id):
#     with get_db_connection() as conn:
#         leave = conn.execute(
#             'SELECT * FROM leaves WHERE id = ?', (id,)).fetchone()

#     if request.method == 'POST':
#         leave_type = request.form['leave_type']
#         start_date = request.form['start_date']
#         end_date = request.form['end_date']
#         reason = request.form['reason']

#         # Calculate service count
#         start_date_obj = datetime.strptime(start_date[:10], "%Y-%m-%d")
#         end_date_obj = datetime.strptime(end_date[:10], "%Y-%m-%d")
#         service_count = (end_date_obj - start_date_obj).days + 1

#         # Determine leave category and set the appropriate fields
#         if service_count <= 2:
#             category = "S"
#             status = "Approved"
#             approved_by = current_user.username  # Automatically set current user
#             verified_by = request.form['verified_by']
#         elif 3 <= service_count <= 5:
#             category = "M"
#             status = "Verified"
#             approved_by = request.form['approved_by']
#             verified_by = current_user.username  # Automatically set current user
#         else:
#             category = "L"
#             status = request.form['status']
#             approved_by = request.form.get('approved_by', None)
#             verified_by = request.form.get('verified_by', None)

#         # Update the leave in the database
#         with get_db_connection() as conn:
#             conn.execute('''
#                 UPDATE leaves
#                 SET leave_type = ?, reason = ?, status = ?, approved_by = ?, verified_by = ?
#                 WHERE id = ?
#             ''', (leave_type, reason, status, approved_by, verified_by, id))

#         return redirect(url_for('view_leaves'))

#     return render_template('/leaves/edit_spm_leave.html', leave=leave)


# @app.route('/leave/edit_gm_approve/<int:id>', methods=['GET', 'POST'])
# def edit_leave_gm_approve(id):
#     user_role = 180 if current_user.is_authenticated and current_user.role_default == 180 else None

#     with get_db_connection() as conn:
#         leave = conn.execute(
#             'SELECT * FROM leaves WHERE id = ?', (id,)).fetchone()

#     if request.method == 'POST':
#         leave_type = request.form['leave_type']
#         start_date = request.form['start_date']
#         end_date = request.form['end_date']
#         reason = request.form['reason']

#         status = "Approved"
#         approved_by = current_user.username

#         with get_db_connection() as conn:
#             conn.execute('''
#                 UPDATE leaves
#                 SET leave_type = ?, reason = ?, status = ?, approved_by = ?
#                 WHERE id = ?
#             ''', (leave_type, reason, status, approved_by, id))

#         return redirect(url_for('leaves_by_gm'))

#     return render_template('/leaves/edit_gm_leave.html', leave=leave)


@app.route('/leave/edit_gm_approve/<int:id>', methods=['GET', 'POST'])
def edit_leave_gm_approve(id):
    user_role = 180 if current_user.is_authenticated and current_user.role_default == 180 else None

    with get_db_connection() as conn:
        leave = conn.execute(
            'SELECT * FROM leaves WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        leave_type = request.form['leave_type']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        status = request.form['status']  # <-- Now using form input
        approved_by = current_user.username

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE leaves
                SET leave_type = ?, reason = ?, status = ?, approved_by = ?
                WHERE id = ?
            ''', (leave_type, reason, status, approved_by, id))

        return redirect(url_for('leaves_by_gm'))

    return render_template('/leaves/edit_gm_leave.html', leave=leave)


@app.route('/leave/edit_spm_approve/<int:id>', methods=['GET', 'POST'])
def edit_leave_spm_approve(id):
    user_role = 160 if current_user.is_authenticated and current_user.role_default == 160 else None

    with get_db_connection() as conn:
        leave = conn.execute(
            'SELECT * FROM leaves WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        leave_type = request.form['leave_type']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        # ✅ Now included
        requested_by_roles = request.form['requested_by_roles']

        # Calculate service count
        start_date_obj = datetime.strptime(start_date[:10], "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date[:10], "%Y-%m-%d")
        service_count = (end_date_obj - start_date_obj).days + 1

        # # Determine leave category and set the appropriate fields
        # if service_count <= 2:
        #     category = "S"
        #     status = "Approved"
        #     approved_by = current_user.username
        #     verified_by = request.form['verified_by']
        # elif 3 <= service_count <= 5:
        #     category = "M"
        #     status = "Approved"
        #     approved_by = current_user.username
        #     approved_by = request.form['approved_by']
        # else:
        #     category = "L"
        #     status = request.form['status']
        #     approved_by = request.form.get('approved_by', None)
        #     verified_by = request.form.get('verified_by', None)
        # Determine leave category and set the appropriate fields
        if service_count <= 2:
            category = "S"
            status = "Approved"
            approved_by = current_user.username
            verified_by = request.form['verified_by']

        elif 3 <= service_count <= 5:
            category = "M"
            status = "Approved"
            approved_by = current_user.username
            verified_by = request.form['verified_by']  # Add this if needed

        else:
            category = "L"
            status = request.form['status']
            approved_by = request.form.get('approved_by', None)
            verified_by = request.form.get('verified_by', None)

        # Update the leave in the database
        with get_db_connection() as conn:
            conn.execute('''
                UPDATE leaves
                SET leave_type = ?, reason = ?, status = ?, approved_by = ?, verified_by = ?, requested_by_roles = ?
                WHERE id = ?
            ''', (leave_type, reason, status, approved_by, verified_by, requested_by_roles, id))  # ✅ Include in params

        if user_role == 160:
            return redirect(url_for('leaves_by_branch_and_hrd'))
        elif user_role == 145:
            return redirect(url_for('view_leaves'))
        return redirect(url_for('view_leaves'))

    return render_template('/leaves/edit_spm_leave.html', leave=leave)


@app.route('/leave/edit_spm_to_pm/<int:id>', methods=['GET', 'POST'])
def edit_leave_spm_to_pm_approve(id):
    user_role = 160 if current_user.is_authenticated and current_user.role_default == 160 else None

    with get_db_connection() as conn:
        leave = conn.execute(
            'SELECT * FROM leaves WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        leave_type = request.form['leave_type']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        requested_by_roles = request.form['requested_by_roles']

        # Calculate service count
        start_date_obj = datetime.strptime(start_date[:10], "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date[:10], "%Y-%m-%d")
        service_count = (end_date_obj - start_date_obj).days + 1

        approved_by = None
        verified_by = None

        # Determine leave category and status
        if service_count <= 2:
            category = "S"
            status = "Approved"
            approved_by = current_user.username
            verified_by = request.form['verified_by']
        elif 3 <= service_count <= 5:
            category = "M"
            status = "Approved"
            approved_by = None
            verified_by = current_user.username
        else:
            category = "L"
            status = request.form.get('status')
            approved_by = request.form.get('approved_by')
            verified_by = request.form.get('verified_by')

        # Update the leave record
        with get_db_connection() as conn:
            conn.execute('''
                UPDATE leaves
                SET leave_type = ?, reason = ?, status = ?, approved_by = ?, verified_by = ?, requested_by_roles = ?
                WHERE id = ?
            ''', (leave_type, reason, status, approved_by, verified_by, requested_by_roles, id))

        # Redirect based on role
        if user_role == 160:
            return redirect(url_for('leaves_by_branch_and_hrd'))
        return redirect(url_for('view_leaves'))

    return render_template('/leaves/edit_pm_request_leave.html', leave=leave)


@app.route('/leave/edit_hrd_spm/<int:id>', methods=['GET', 'POST'])
def edit_leave_hrd_spm_approve(id):
    user_role = 160 if current_user.is_authenticated and current_user.role_default == 160 else None

    with get_db_connection() as conn:
        leave = conn.execute(
            'SELECT * FROM leaves WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        leave_type = request.form.get('leave_type')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        reason = request.form.get('reason')
        requested_by_roles = request.form.get('requested_by_roles')

        # Dates and duration
        start_date_obj = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date_str, "%Y-%m-%d")
        service_count = (end_date_obj - start_date_obj).days + 1

        # Automatically verify all leaves
        status = "Approved"
        verified_by = current_user.username
        approved_by = None  # Approval not done here

        # Optional: assign category if still needed
        if service_count <= 2:
            category = "S"
        elif 3 <= service_count <= 5:
            category = "M"
        else:
            category = "L"

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE leaves
                SET leave_type = ?, start_date = ?, end_date = ?, reason = ?, 
                    status = ?, approved_by = ?, verified_by = ?
                WHERE id = ?
            ''', (leave_type, start_date_str, end_date_str, reason,
                  status, approved_by, verified_by, id))

        if user_role == 160:
            return redirect(url_for('leaves_by_branch_and_hrd'))
        return redirect(url_for('view_leaves'))

    return render_template('/leaves/edit_hrd_spm_leave.html', leave=leave)


@app.route('/leave/edit_hrd_approve/<int:id>', methods=['GET', 'POST'])
def edit_leave_hrd_approve(id):
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

        return redirect(url_for('leaves_by_branch_and_hrd'))

    return render_template('/leaves/edit_hrd_leave.html', leave=leave)


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
            status = "Approved"
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
                SET leave_type= ?,  reason= ?, status= ?, approved_by= ?, verified_by= ?
                WHERE id= ?
            ''', (leave_type, reason, status, approved_by, verified_by, id))

        return redirect(url_for('view_leaves'))

    return render_template('/leaves/edit_leave_pm.html', leave=leave)


@app.route('/leave_department/edit/<int:id>', methods=['GET', 'POST'])
def edit_leave_department(id):
    branch_name = current_user.branch
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
            status = "Approved"
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
                SET leave_type= ?,  reason= ?, status= ?, approved_by= ?, verified_by= ?
                WHERE id= ?
            ''', (leave_type, reason, status, approved_by, verified_by, id))

        return redirect(url_for('leaves_by_department_crd', branch_name=branch_name))

    return render_template('/leaves/edit_leave_department.html', leave=leave)


@app.route('/leave/edit/hours/ccc/<int:id>', methods=['GET', 'POST'])
def edit_leave(id):
    with get_db_connection() as conn:
        leave = conn.execute(
            'SELECT * FROM leaves WHERE id = ?', (id,)).fetchone()

    if not leave:
        return "Leave record not found", 404

    if request.method == 'POST':
        leave_type = request.form['leave_type']
        type_of_leave = request.form.get('type_of_leave')
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        # approved_by = request.form.get('approved_by')
        verified_by = request.form.get('verified_by')
        status = request.form.get('status')
        # status = "Pending"

        # Logic for half-day leave only
        if type_of_leave == 'H':
            status = "Approved"
            verified_by = request.form['verified_by']

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE leaves
                SET leave_type = ?, reason = ?, status = ?,
                    verified_by = ?,
                    start_date = ?, end_date = ?
                WHERE id = ?
            ''', (
                leave_type, reason, status,
                verified_by,
                start_date, end_date, id
            ))

        return redirect(url_for('view_leaves'))

    return render_template('/leaves/edit_leave.html', leave=leave)


@app.route('/leave/edit/hours/hrd/<int:id>', methods=['GET', 'POST'])
def edit_leave_hours_hrd(id):
    with get_db_connection() as conn:
        leave = conn.execute(
            'SELECT * FROM leaves WHERE id = ?', (id,)).fetchone()

    if not leave:
        return "Leave record not found", 404

    if request.method == 'POST':
        leave_type = request.form['leave_type']
        type_of_leave = request.form.get('type_of_leave')
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        # approved_by = request.form.get('approved_by')
        verified_by = request.form.get('verified_by')
        status = request.form.get('status')
        # status = "Pending"

        # Logic for half-day leave only
        if type_of_leave == 'H':
            status = "Approved"
            verified_by = request.form['verified_by']

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE leaves
                SET leave_type = ?, reason = ?, status = ?,
                    verified_by = ?,
                    start_date = ?, end_date = ?
                WHERE id = ?
            ''', (
                leave_type, reason, status,
                verified_by,
                start_date, end_date, id
            ))

        return redirect(url_for('leaves_by_branch_and_hrd'))

    return render_template('/leaves/edit_leave_hrd.html', leave=leave)


@app.route('/leave/edit/hours/spm/<int:id>', methods=['GET', 'POST'])
def edit_leave_hours_spm(id):
    with get_db_connection() as conn:
        leave = conn.execute(
            'SELECT * FROM leaves WHERE id = ?', (id,)).fetchone()

    if not leave:
        return "Leave record not found", 404

    if request.method == 'POST':
        leave_type = request.form['leave_type']
        type_of_leave = request.form.get('type_of_leave')
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        approved_by = request.form.get('approved_by')
        verified_by = request.form.get('verified_by')
        status = request.form.get('status')
        # status = "Pending"

        # Logic for half-day leave only
        if type_of_leave == 'H':
            status = "Approved"
            approved_by = request.form.get('approved_by')

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE leaves
                SET leave_type = ?, reason = ?, status = ?,
                    approved_by = ?,
                    start_date = ?, end_date = ?
                WHERE id = ?
            ''', (
                leave_type, reason, status,
                approved_by,
                start_date, end_date, id
            ))

        return redirect(url_for('leaves_by_branch_and_spm'))

    return render_template('/leaves/edit_leave_hours_spm.html', leave=leave)


@app.route('/leave/edit/hours/gm/<int:id>', methods=['GET', 'POST'])
def edit_leave_hours_gm(id):
    with get_db_connection() as conn:
        leave = conn.execute(
            'SELECT * FROM leaves WHERE id = ?', (id,)).fetchone()

    if not leave:
        return "Leave record not found", 404

    if request.method == 'POST':
        leave_type = request.form['leave_type']
        type_of_leave = request.form.get('type_of_leave')
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        approved_by = request.form.get('approved_by')
        # verified_by = request.form.get('verified_by')
        status = request.form.get('status')
        # status = "Pending"

        # Logic for half-day leave only
        if type_of_leave == 'H':
            status = "Approved"
            approved_by = request.form['approved_by']

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE leaves
                SET leave_type = ?, reason = ?, status = ?,
                    approved_by = ?,
                    start_date = ?, end_date = ?
                WHERE id = ?
            ''', (
                leave_type, reason, status,
                approved_by,
                start_date, end_date, id
            ))

        return redirect(url_for('leaves_by_gm'))

    return render_template('/leaves/edit_leave_gm.html', leave=leave)


@app.route('/leave/edit/hours/pm/<int:id>', methods=['GET', 'POST'])
def edit_leave_hours_pm(id):
    with get_db_connection() as conn:
        leave = conn.execute(
            'SELECT * FROM leaves WHERE id = ?', (id,)).fetchone()

    if not leave:
        return "Leave record not found", 404

    if request.method == 'POST':
        leave_type = request.form['leave_type']
        type_of_leave = request.form.get('type_of_leave', '').strip().upper()
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        approved_by = request.form.get('approved_by')
        status = request.form.get('status')

        # status = "Pending"

        if type_of_leave == 'H':
            status = "Approved"
            approved_by = request.form['approved_by']

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE leaves
                SET leave_type = ?, reason = ?, status = ?,
                    approved_by = ?,
                    start_date = ?, end_date = ?
                WHERE id = ?
            ''', (
                leave_type, reason, status,
                approved_by,
                start_date, end_date, id
            ))

        return redirect(url_for('view_leaves'))

    return render_template('/leaves/edit_leave_hours_pm.html', leave=leave)


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


@app.route('/leave/delete/<int:id>', methods=['POST'])
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


# @app.route('/register', methods=['GET', 'POST'])
# def register():
#     if request.method == 'POST':
#         username = request.form['username']
#         password = request.form['password']
#         email = request.form['email']
#         mobile1 = request.form['mobile1']
#         hashed_password = hashlib.sha256(password.encode()).hexdigest()

#         # Check if username or email already exists in the database
#         with get_db_connection() as conn:
#             cursor = conn.cursor()
#             cursor.execute(
#                 'SELECT * FROM users WHERE UserName = ? OR Email = ?', (username, email))
#             existing_user = cursor.fetchone()

#             if existing_user:
#                 flash('Username or Email already exists. Try again.', 'danger')
#                 return render_template('register.html')

#         # Insert user data into the database
#         with get_db_connection() as conn:
#             try:
#                 conn.execute('''
#                     INSERT INTO users(UserName, Password, Email, Mobile1)
#                     VALUES(?, ?, ?, ?)
#                 ''', (username, hashed_password, email, mobile1))
#                 conn.commit()

#                 # Generate OTP and store it in session
#                 session["otp"] = pyotp.TOTP(pyotp.random_base32()).now()

#                 # Send OTP and mobile number to the user's Telegram account
#                 otp_message = f"Verification Code: {session['otp']}\nYour mobile number: {mobile1}\nYour email: {email}"
#                 if send_telegram_message(otp_message):
#                     flash(
#                         "Registration successful! Check your Telegram for OTP.", "info")
#                 else:
#                     flash(
#                         "Failed to send OTP via Telegram. Please try again.", "danger")

#                 # Redirect to OTP verification page
#                 return redirect(url_for('verify_otp'))

#             except sqlite3.IntegrityError:
#                 flash("Username or Email already exists. Try again.", "danger")
#                 return render_template('register.html')

#     return render_template('register.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        # Default to 1111 if empty
        password = request.form['password'] or '1111'
        email = request.form['email']
        mobile1 = request.form['mobile1']
        first_name_kh = request.form['first_name_kh']
        last_name_kh = request.form['last_name_kh']
        first_name_en = request.form['first_name_en']
        last_name_en = request.form['last_name_en']
        branch = request.form['branch']
        language = request.form.get('language', 'en')
        role_default = request.form.get('role_default', 0)

        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM users WHERE UserName = ? OR Email = ?', (username, email))
            existing_user = cursor.fetchone()

            if existing_user:
                flash('Username or Email already exists. Try again.', 'danger')
                branches = conn.execute(
                    'SELECT Branch FROM branches').fetchall()
                return render_template('register.html', branches=branches)

        with get_db_connection() as conn:
            try:
                conn.execute('''
                    INSERT INTO users(
                        UserName, Password, Email, Mobile1, Active,
                        FirstNameKh, LastNameKh, FirstNameEn, LastNameEn,
                        Branch, Language, RoleDefault
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    username, hashed_password, email, mobile1, 0,
                    first_name_kh, last_name_kh, first_name_en, last_name_en,
                    branch, language, role_default
                ))
                conn.commit()
                flash("Registration successful! Awaiting activation.", "success")
                return redirect(url_for('inactive_user'))
            except sqlite3.IntegrityError:
                flash("Username or Email already exists. Try again.", "danger")
                branches = conn.execute(
                    'SELECT Branch FROM branches').fetchall()
                return render_template('register.html', branches=branches)

    with get_db_connection() as conn:
        branches = conn.execute('SELECT Branch FROM branches').fetchall()
    return render_template('register.html', branches=branches)


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


@app.route('/inactive')
def inactive_user():
    return render_template('inactive_user.html')


@app.errorhandler(RateLimitExceeded)
def handle_ratelimit(e):
    return jsonify({"error": "Too many requests. Please try again later."}), 429


@app.route('/session-info', methods=['GET'])
def session_info():
    return jsonify(dict(session))


@app.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    username = request.form['username']
    password = hashlib.sha256(request.form['password'].encode()).hexdigest()

    ip_address = request.remote_addr
    user_agent = request.user_agent.string
    city, region, country = get_geolocation(ip_address)

    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        user = conn.execute('''
            SELECT ID, UserName, Password, Email, Branch, IsAdmin,
                   COALESCE(RoleDefault, 1) AS RoleDefault, ZoneID, Active
            FROM users
            WHERE UserName = ? AND Password = ?
        ''', (username, password)).fetchone()

        # department = conn.execute('''
        #     SELECT Department FROM employees WHERE user_id = ?
        # ''', (user['ID'],)).fetchone()

    if not user:
        flash("Invalid username or password", 'error')
        return render_template('404.html'), 404

    user = dict(user)
    print("Fetched User Data:", user)

    # Check if the user is inactive
    if user.get('Active', 0) != 1:
        flash("Your account is inactive. Please contact the administrator.", "error")
        return redirect(url_for('inactive_user'))

    # Get employee ID if exists
    with get_db_connection() as conn:
        employee = conn.execute('''
            SELECT id , department FROM employees WHERE user_id = ?
        ''', (user['ID'],)).fetchone()
        employee_id = employee['id'] if employee else None
        print("Fetched Employee ID:", employee_id)
        department = employee['department'] if employee else None

        # Log login
        conn.execute('''
            INSERT INTO login_logs(user_id, ip_address, city, region, country, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user['ID'], ip_address, city, region, country, user_agent))

        # Add to online_users
        conn.execute('''
            INSERT OR REPLACE INTO online_users(user_id, login_time, last_active_time)
            VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (user['ID'],))
        conn.commit()

        # ✅ Set session variables (persistent session)
        # session['user_id'] = user['ID']
        # session['username'] = user['UserName']
        # session['email'] = user['Email']
        # session['employee_id'] = employee_id
        # session['role'] = user['RoleDefault']
        # session['zone_id'] = user['ZoneID']
        # session['is_admin'] = user['IsAdmin']
        # session.permanent = True  # ensure timeout is applied

    # Login user
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
        zone_id=user['ZoneID'],
        department=department
    )

    print("Logged in user:", user_obj)
    login_user(user_obj)

    return redirect(url_for('dashboard'))


@app.route('/logout', methods=['POST'])
def logout():
    # session.clear()
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

    # flash('You have been logged out successfully.', 'success')
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


@app.route('/force_reset_password', methods=['GET', 'POST'])
@login_required  # Optional: Add @admin_required if needed
def force_reset_password():
    if request.method == 'GET':
        return render_template('force_reset_password.html')

    # Handle POST form submission
    email = request.form.get('email')
    username = request.form.get('username')
    new_password = request.form.get('new_password')

    if not all([email, username, new_password]):
        return render_template(
            'force_reset_password.html',
            error="All fields are required."
        )

    hashed_password = hashlib.sha256(new_password.encode()).hexdigest()

    with get_db_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE Email = ? AND Username = ?",
            (email, username)
        ).fetchone()

        if not user:
            return render_template(
                'force_reset_password.html',
                error="User not found with the provided email and username."
            )

        conn.execute('''
            UPDATE users
            SET Password = ?, Force_Password_Change = 1
            WHERE Email = ? AND Username = ?
        ''', (hashed_password, email, username))
        conn.commit()

    return render_template(
        'force_reset_password.html',
        success=f"Password for user {username} has been reset."
    )


# @app.route('/users', methods=['GET'])
# @login_required
# def users():
#      if session.get('user_id') is None or session.get('is_admin') != 1:
#         flash("You must be an administrator to access this page.", "warning")
#         return render_template('access_denied.html')

#     filter_value = request.args.get('active', 'all')

#     # Use the helper functions to get users
#     if filter_value == '1':  # Active users
#         users = get_active_users()
#     elif filter_value == '0':  # Inactive users
#         users = get_inactive_users()
#     else:  # Default to show all users
#         users = get_all_users()

#     return render_template('users/users.html', users=users, active_filter=filter_value)

@app.route('/users', methods=['GET'])
@login_required
def users():
    # Ensure the user is logged in and is_admin == 1
    # if session.get('user_id') is None or session.get('is_admin') != 1:
    #     flash("You must be an administrator to access this page.", "warning")
    #     return render_template('access_denied.html')

    # Grab the filter parameter (defaults to 'all')
    filter_value = request.args.get('active', 'all')

    # Fetch users based on the filter
    if filter_value == '1':          # Active users
        users = get_active_users()
    elif filter_value == '0':        # Inactive users
        users = get_inactive_users()
    else:                            # All users
        users = get_all_users()

    return render_template('users/users.html', users=users, active_filter=filter_value)


def get_all_users():
    with get_db_connection() as conn:
        return conn.execute("""
            SELECT
                ID,
                UserName,
                Email,
                FirstNameKh,
                LastNameKh,
                FirstNameEn,
                LastNameEn,
                Branch,
                IsAdmin,
                Active,
                Menu,
                Language,
                Mobile1,
                Status,
                Note,
                RequestRole,
                RoleDefault,
                AcceptedTerms,
                ZoneID
            FROM users
        """).fetchall()


@app.route('/users/export', methods=['GET'])
@login_required
def export_users_csv():
    filter_value = request.args.get('active', 'all')

    # Retrieve users based on the filter
    if filter_value == '1':
        users = get_active_users()
    elif filter_value == '0':
        users = get_inactive_users()
    else:
        users = get_all_users()

    # Remove 'Password' field from each user dictionary
    cleaned_users = []
    for user in users:
        user_dict = dict(user)
        user_dict.pop('Password', None)
        cleaned_users.append(user_dict)

    # Create a CSV in memory with UTF-8 encoding
    output = BytesIO()
    wrapper = TextIOWrapper(output, encoding='utf-8-sig', newline='')
    writer = csv.writer(wrapper)

    # Write headers and data
    if cleaned_users:
        writer.writerow(cleaned_users[0].keys())
        for user in cleaned_users:
            writer.writerow(user.values())
    else:
        writer.writerow(["No data found"])

    # Flush and get byte value
    wrapper.flush()
    output.seek(0)

    # Generate a timestamped filename
    timestamp = datetime.now().strftime("%m-%d-%Y_%H-%M-%S")
    filename = f"users_export_{timestamp}.csv"

    # Return response with correct headers
    return Response(output.read(),
                    mimetype='text/csv',
                    headers={"Content-Disposition": f"attachment;filename={filename}"})


@app.route('/users/import', methods=['GET', 'POST'])
@login_required
def import_users_csv():
    if request.method == 'POST':
        file = request.files.get('file')

        if not file or not file.filename.endswith('.csv'):
            flash('Please upload a valid CSV file.', 'danger')
            return redirect(request.url)

        try:
            stream = TextIOWrapper(file.stream, encoding='utf-8')
            csv_reader = csv.DictReader(stream)

            with get_db_connection() as conn:
                cursor = conn.cursor()
                inserted = 0
                skipped = 0

                for row in csv_reader:
                    # Validate required fields
                    if not row.get('UserName') or not row.get('Email'):
                        skipped += 1
                        continue  # Skip rows with missing critical data

                    try:
                        # Hash the password '1111' before inserting
                        hashed_password = hashlib.sha256(
                            '1111'.encode()).hexdigest()

                        cursor.execute('''
                            INSERT INTO users (
                                UserName, Email, FirstNameKh, LastNameKh, FirstNameEn, LastNameEn, Branch,
                                IsAdmin, DisplayName, LoginName, StartDate, EndDate, Mobile1, Mobile2,
                                Active, Menu, Language, Status, Note, RequestRole, RoleDefault,
                                AcceptedTerms, ImageUrl, Image, Signature, FingerPrint, ZoneID, Force_Password_Change, Password
                            ) VALUES (
                                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                            )
                        ''', (
                            row['UserName'],
                            row['Email'],
                            row.get('FirstNameKh'),
                            row.get('LastNameKh'),
                            row.get('FirstNameEn'),
                            row.get('LastNameEn'),
                            row.get('Branch'),
                            int(row.get('IsAdmin', 0) or 0),
                            row.get('DisplayName'),
                            row.get('LoginName'),
                            row.get('StartDate'),
                            row.get('EndDate'),
                            row.get('Mobile1'),
                            row.get('Mobile2'),
                            int(row.get('Active', 1) or 1),
                            row.get('Menu'),
                            row.get('Language', 'en'),
                            row.get('Status'),
                            row.get('Note'),
                            row.get('RequestRole'),
                            int(row.get('RoleDefault', 0) or 0),
                            int(row.get('AcceptedTerms', 0) or 0),
                            row.get('ImageUrl'),
                            row.get('Image'),
                            row.get('Signature'),
                            row.get('FingerPrint'),
                            row.get('ZoneID'),
                            int(row.get('Force_Password_Change', 0) or 0),
                            hashed_password  # Store hashed password
                        ))
                        inserted += 1

                    except Exception as e:
                        app.logger.warning(f"Skipped row due to error: {e}")
                        skipped += 1

                conn.commit()

            flash(
                f'{inserted} users imported successfully. {skipped} rows skipped.', 'success')
            return redirect(url_for('users'))

        except Exception as e:
            app.logger.error(f"Import error: {e}")
            flash('There was an error importing the CSV.', 'danger')
            return redirect(request.url)

    return render_template('users/import_users.html')


@app.route('/users/import/template')
@login_required
def download_csv_template():
    headers = [
        "UserName", "Email", "FirstNameKh", "LastNameKh", "FirstNameEn", "LastNameEn", "Branch",
        "IsAdmin", "DisplayName", "LoginName", "StartDate", "EndDate", "Mobile1", "Mobile2",
        "Active", "Menu", "Language", "Status", "Note", "RequestRole", "RoleDefault",
        "AcceptedTerms", "ImageUrl", "Image", "Signature", "FingerPrint", "ZoneID", "Force_Password_Change"
    ]

    sample_row = [
        "jdoe", "jdoe@example.com", "ចន", "ដូ", "John", "Doe", "KPT",
        0, "John D.", "jdoe", "2025-01-01", "2025-12-31", "012345678", "098765432",
        1, "default", "en", "active", "Sample user", "user", 0,
        1, "", "", "", "", 1, 0
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerow(sample_row)

    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = 'attachment; filename=import_users_template.csv'
    return response


def get_active_users():
    with get_db_connection() as conn:
        return conn.execute("SELECT * FROM users WHERE Active = 1").fetchall()

# Helper function to get inactive users


def get_inactive_users():
    with get_db_connection() as conn:
        return conn.execute("SELECT * FROM users WHERE Active = 0").fetchall()


@app.route('/users/update_status/<int:user_id>', methods=['POST'])
@login_required
def update_user_status(user_id):
    # Get the new active status from the form or query parameters
    new_status = request.form.get('active_status')

    # Validating the status input (should be 0 or 1)
    if new_status not in ['0', '1']:
        return "Invalid status", 400

    # Update the user active status in the database
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE users
            SET Active = ?
            WHERE id = ?
        """, (new_status, user_id))
        conn.commit()

    # Redirect to the user list after the update
    return redirect(url_for('users'))


@app.route('/users/add', methods=['GET', 'POST'])
def add_user() -> Union[str, 'Response']:
    # if session.get('user_id') is None or session.get('is_admin') != 1:
    #     flash("You must be an administrator to access this page.", "warning")
    #     return render_template('access_denied.html')

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
        employees = conn.execute(
            "SELECT * FROM employees WHERE user_id = ?", (user_id,)).fetchall()

    if user_data:
        return render_template('/users/profile.html', user=user_data or [], branches=branches or [], employees=employees or [])
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


@app.route('/users/owner/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user_owner(id):
    # if current_user.is_admin == 0:
    #     flash("You don't have permission to view this page.", "danger")
    #     return redirect(url_for('dashboard'))

    with get_db_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE ID = ?", (id,)).fetchone()
        branches = conn.execute("SELECT * FROM branches").fetchall()

    if request.method == 'POST':
        first_name_kh = request.form['first_name_kh']
        last_name_kh = request.form['last_name_kh']
        first_name_en = request.form['first_name_en']
        last_name_en = request.form['last_name_en']
        mobile1 = request.form['mobile1']

        with get_db_connection() as conn:
            conn.execute("""
                UPDATE users
                SET FirstNameKh = ?, LastNameKh = ?, FirstNameEn = ?, LastNameEn = ?, Mobile1 = ?, UpdatedAt = CURRENT_TIMESTAMP
                WHERE ID = ?
            """, (first_name_kh, last_name_kh, first_name_en, last_name_en, mobile1, id))
            conn.commit()
        return redirect(url_for('profile', user_id=current_user.id))

    return render_template('/users/edit_user_owner.html', user=user, branches=branches)


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


# @app.route('/dashboard')
# @login_required
# def dashboard():

#     # if 'user_id' not in session:
#     #     return redirect(url_for('login'))
#     # # Admin dashboard
#     if getattr(current_user, 'is_admin', False):
#         return render_dashboard(current_user.id)

#     role = getattr(current_user, 'role_default', None)

#     # Employee dashboard
#     if role == 20:
#         with get_db_connection() as conn:
#             employee = conn.execute(
#                 "SELECT e.ID FROM employees e WHERE e.user_id = ?",
#                 (current_user.id,)
#             ).fetchone()
#         if employee:
#             return redirect(url_for('render_dashboard_employees', employee_id=employee[0]))
#         else:
#             flash("Employee not found!", "danger")
#             return render_template('access_denied.html')

#     # SPM dashboard
#     if role == 145:
#         return redirect(url_for('spm_dashboard'))

#     # SPM dashboard
#     if role == 160:
#         return redirect(url_for('hrd_dashboard'))

#     # GM dashboard
#     if role == 180:
#         return redirect(url_for('gm_dashboard'))

#     # Branch Manager dashboard
#     if role in [140, 35]:
#         branch = getattr(current_user, 'branch', None)
#         if branch:
#             return redirect(url_for('render_dashboard_branch_manager', branch_name=branch))
#         else:
#             flash("Branch information is missing.", "danger")
#             return render_template('access_denied.html')

#     # Default fallback (no redirect to dashboard again!)
#     flash("Access denied: You do not have permission to view this page.", "danger")
#     return render_template('access_denied.html')


# @app.route('/dashboard')
# @login_required
# def dashboard():
#     role = getattr(current_user, 'role_default', None)
#     user_id = current_user.id

#     # Admin Dashboard
#     if getattr(current_user, 'is_admin', False):
#         return render_dashboard(user_id)

#     # Role-based dashboards
#     dashboard_routes = {
#         145: 'spm_dashboard',
#         160: 'hrd_dashboard',
#         180: 'gm_dashboard',
#         140: 'render_dashboard_branch_manager',
#         35:  'render_dashboard_branch_manager'
#     }

#     # Employee (requires employee ID lookup)
#     if role == 20:
#         with get_db_connection() as conn:
#             employee = conn.execute(
#                 "SELECT e.ID FROM employees e WHERE e.user_id = ?", (user_id,)
#             ).fetchone()

#         if employee:
#             return redirect(url_for('render_dashboard_employees', employee_id=employee['ID']))
#         else:
#             flash("Employee not found!", "danger")
#             return render_template('access_denied.html')

#     # Branch Manager (requires branch info)
#     if role in [140, 35]:
#         branch = getattr(current_user, 'branch', None)
#         if branch:
#             return redirect(url_for('render_dashboard_branch_manager', branch_name=branch))
#         else:
#             flash("Branch information is missing.", "danger")
#             return render_template('access_denied.html')

#     # Other roles (direct redirect)
#     if role in dashboard_routes:
#         return redirect(url_for(dashboard_routes[role]))

#     # Fallback
#     flash("Access denied: You do not have permission to view this page.", "danger")
#     return render_template('access_denied.html')


@app.route('/dashboard')
@login_required
def dashboard():
    role = getattr(current_user, 'role_default', None)
    user_id = current_user.id

    # Admin Dashboard
    if getattr(current_user, 'is_admin', False):
        return render_dashboard(user_id)

    # Branch Manager roles that require 'branch_name'
    if role in [140, 35]:
        branch = getattr(current_user, 'branch', None)
        if branch:
            return redirect(url_for('render_dashboard_branch_manager', branch_name=branch), code=302)
        else:
            flash("Branch information is missing.", "danger")
            return render_template('access_denied.html')

    if role == 200:
        branch = getattr(current_user, 'branch', None)
        if branch:
            return redirect(url_for('render_dashboard_hq', branch_name=branch), code=302)
        else:
            flash("Branch information is missing.", "danger")
            return render_template('access_denied.html')

    # Role-based dashboards
    dashboard_routes = {
        145: 'spm_dashboard',
        160: 'hrd_dashboard',
        180: 'gm_dashboard',
        20: 'render_dashboard_employees'  # Regular employee
    }

    if role in dashboard_routes:
        return redirect(url_for(dashboard_routes[role]))

    # Fallback
    flash("Access denied: You do not have permission to view this page.", "danger")
    return render_template('access_denied.html')


@app.route('/gm/dashboard')
@login_required
def gm_dashboard():
    # if current_user.role_default != 180 :
    #     flash("Access denied to GM dashboard.", "danger")
    #     return render_template('access_denied.html')

    today_date = date.today()

    with get_db_connection() as conn:
        sun_zones = conn.execute("SELECT * FROM zones").fetchall()
        branches = conn.execute("SELECT * FROM branches").fetchall()
        employees = conn.execute("SELECT * FROM employees").fetchall()
        users = conn.execute("SELECT * FROM users").fetchall()

        # Employees on leave today
        employees_on_leave_today = conn.execute("""
                SELECT 
                    u.ID AS user_id,
                    u.UserName AS username,
                    l.requested_by AS employee_name,
                    l.branch AS employee_branch,
                    b.Branch AS branch_name,
                    l.start_date,
                    l.end_date,
                    l.reason,
                    l.service_count,
                    l.leave_hours
                FROM leaves l
                JOIN users u ON l.id = u.id
                JOIN employees e ON u.id = e.id
                JOIN branches b ON u.branch = b.Branch
                WHERE l.start_date IS NOT NULL AND l.end_date IS NOT NULL
                AND ? BETWEEN l.start_date AND l.end_date
            """, (today_date,)).fetchall()
        total_leave = len(employees_on_leave_today)

        # total_leave = len(employees_on_leave_today)

        # # Leave summary by branch
        leave_summary_by_branch = conn.execute("""
            SELECT 
                branch AS branch_name,
                SUM(service_count) AS total_leave_days,
                SUM(leave_hours) AS total_leave_hours
            FROM leaves
            GROUP BY branch
        """).fetchall()

        leave_summary_by_zone = conn.execute("""
           SELECT 
            z.Name AS zone_name,
            COUNT(DISTINCT l.employee_id) AS employee_count,
            SUM(julianday(l.end_date) - julianday(l.start_date) + 1) AS total_leave_days,
            SUM((julianday(l.end_date) - julianday(l.start_date) + 1) * 8) AS total_leave_hours
        FROM zones z
        LEFT JOIN zone_branch zb ON z.ID = zb.zone_id
        LEFT JOIN branches b ON zb.branch_id = b.ID
        LEFT JOIN users u ON u.branch = b.ID  -- Make sure this is branch ID
        LEFT JOIN leaves l 
            ON l.employee_id = u.id 
            AND l.start_date IS NOT NULL 
            AND l.end_date IS NOT NULL
        GROUP BY z.Name;
        """).fetchall()

    return render_template(
        'dashboard/gm_dashboard.html',
        sun_zones=sun_zones,
        branches=branches,
        employees=employees,
        users=users,
        employees_on_leave_today=employees_on_leave_today,
        total_leave=total_leave,
        leave_summary=leave_summary_by_branch,
        leave_summary_by_zone=leave_summary_by_zone
    )


@app.route('/hrd/dashboard')
@login_required
def hrd_dashboard():
    # if current_user.role_default != 180 :
    #     flash("Access denied to GM dashboard.", "danger")
    #     return render_template('access_denied.html')

    today_date = date.today()

    with get_db_connection() as conn:
        sun_zones = conn.execute("SELECT * FROM zones").fetchall()
        branches = conn.execute("SELECT * FROM branches").fetchall()
        employees = conn.execute("SELECT * FROM employees").fetchall()
        users = conn.execute("SELECT * FROM users").fetchall()

        # Employees on leave today
        employees_on_leave_today = conn.execute("""
                SELECT 
                    u.ID AS user_id,
                    u.UserName AS username,
                    l.requested_by AS employee_name,
                    l.branch AS employee_branch,
                    b.Branch AS branch_name,
                    l.start_date,
                    l.end_date,
                    l.reason,
                    l.service_count,
                    l.leave_hours
                FROM leaves l
                JOIN users u ON l.id = u.id
                JOIN employees e ON u.id = e.id
                JOIN branches b ON u.branch = b.Branch
                WHERE l.start_date IS NOT NULL AND l.end_date IS NOT NULL
                AND ? BETWEEN l.start_date AND l.end_date
            """, (today_date,)).fetchall()
        total_leave = len(employees_on_leave_today)

        # total_leave = len(employees_on_leave_today)

        # # Leave summary by branch
        leave_summary_by_branch = conn.execute("""
            SELECT 
                branch AS branch_name,
                SUM(service_count) AS total_leave_days,
                SUM(leave_hours) AS total_leave_hours
            FROM leaves
            GROUP BY branch
        """).fetchall()

        leave_summary_by_zone = conn.execute("""
           SELECT 
            z.Name AS zone_name,
            COUNT(DISTINCT l.employee_id) AS employee_count,
            SUM(julianday(l.end_date) - julianday(l.start_date) + 1) AS total_leave_days,
            SUM((julianday(l.end_date) - julianday(l.start_date) + 1) * 8) AS total_leave_hours
        FROM zones z
        LEFT JOIN zone_branch zb ON z.ID = zb.zone_id
        LEFT JOIN branches b ON zb.branch_id = b.ID
        LEFT JOIN users u ON u.branch = b.ID  -- Make sure this is branch ID
        LEFT JOIN leaves l 
            ON l.employee_id = u.id 
            AND l.start_date IS NOT NULL 
            AND l.end_date IS NOT NULL
        GROUP BY z.Name;
        """).fetchall()

    return render_template(
        'dashboard/hrd_dashboard.html',
        sun_zones=sun_zones,
        branches=branches,
        employees=employees,
        users=users,
        employees_on_leave_today=employees_on_leave_today,
        total_leave=total_leave,
        leave_summary=leave_summary_by_branch,
        leave_summary_by_zone=leave_summary_by_zone
    )


@app.route('/spm_dashboard')
@login_required
def spm_dashboard():
    today_date = date.today()
    if current_user.role_default != 145:
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    zone_id = current_user.zone_id
    if zone_id is None:
        flash("Zone ID not found for the current user!", "danger")
        return redirect(url_for('dashboard'))

    with get_db_connection() as conn:
        # Get the zone
        zone = conn.execute(
            "SELECT * FROM zones WHERE ID = ?", (zone_id,)
        ).fetchone()
        if zone is None:
            flash("Zone not found!", "danger")
            return redirect(url_for('dashboard'))

        # Get branches in the zone
        branches_in_zone = conn.execute(
            "SELECT b.ID, b.Branch, b.ContactNumber, b.BranchManagerName FROM branches b JOIN zone_branch zb ON b.ID = zb.branch_id WHERE zb.zone_id = ?", (
                zone_id,)
        ).fetchall()

        # Get total number of employees in the zone
        total_employees_in_zone = conn.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE branch IN (
                SELECT b.Branch
                FROM branches b
                JOIN zone_branch zb ON b.ID = zb.branch_id
                WHERE zb.zone_id = ?
            )
            AND RoleDefault = 20
            """, (zone_id,)
        ).fetchone()[0]

        # Count employees on leave today in the zone
        total_employees_on_leave_today = conn.execute(
            """
            SELECT COUNT(DISTINCT l.employee_id)
            FROM leaves l
            JOIN users u ON l.employee_id = u.id
            WHERE u.branch IN (
                SELECT b.Branch
                FROM branches b
                JOIN zone_branch zb ON b.ID = zb.branch_id
                WHERE zb.zone_id = ?
            )
         
            AND ? BETWEEN l.start_date AND l.end_date
            """,
            (zone_id, today_date)
        ).fetchone()[0]

        # Get list of employees on leave today in the zone
        employees_on_leave_today = conn.execute(
            """
            SELECT u.ID, u.UserName, u.Branch, l.start_date, l.end_date, l.reason
            FROM leaves l
            JOIN users u ON l.employee_id = u.id
            WHERE u.branch IN (
                SELECT b.Branch
                FROM branches b
                JOIN zone_branch zb ON b.ID = zb.branch_id
                WHERE zb.zone_id = ?
            )
            AND ? BETWEEN l.start_date AND l.end_date
            """,
            (zone_id, today_date)
        ).fetchall()

    data = {
        'message': "Welcome, " + current_user.username,
        'zone': zone,
        'branches': branches_in_zone,
        'total_employees_in_zone': total_employees_in_zone,
        'total_leave': total_employees_on_leave_today,
        'employees_on_leave_today': employees_on_leave_today
    }

    return render_template('/dashboard/spm_dashboard.html', data=data)


# @app.route('/dashboard/hq/<string:branch_name>')
# @login_required
# def render_dashboard_hq(branch_name):
#     today = date.today()

#     with get_db_connection() as conn:
#         # Fetch all employees in the branch
#         employees = conn.execute(
#             """
#             SELECT e.ID, e.Name, e.Age, e.Salary, e.Branch,
#                    p.PositionName AS Position,
#                    d.Name AS Department
#             FROM employees e
#             LEFT JOIN positions p ON e.position_id = p.ID
#             LEFT JOIN departments d ON p.department_id = d.ID
#             WHERE e.Branch = ?
#             """,
#             (branch_name,)
#         ).fetchall()

#         if not employees:
#             flash("No employees found in this branch!", "danger")
#             return redirect(url_for('dashboard'))

#         # Count employees in the branch
#         employee_count = len(employees)

#         # Count employees on leave today
#         employees_on_leave_today = conn.execute(
#             """
#             SELECT COUNT(*)
#             FROM leaves l
#             JOIN employees e ON l.employee_id = e.ID
#             WHERE e.Branch = ?
#               AND ? BETWEEN l.start_date AND l.end_date
#               AND l.status = 'Approved'
#             """,
#             (branch_name, today)
#         ).fetchone()[0]

#         # Prepare employee data for rendering
#         employee_data = [
#             {
#                 'ID': emp['ID'],
#                 'Name': emp['Name'],
#                 'Age': emp['Age'],
#                 'Salary': emp['Salary'],
#                 'Branch': emp['Branch'],
#                 'Position': emp['Position'],
#                 'Department': emp['Department']
#             }
#             for emp in employees
#         ]

#         return render_template(
#             'employees/hq_dashboard.html',
#             employees=employee_data or [],
#             employees_in_branch=employee_count or 0,
#             employees_on_leave_today=employees_on_leave_today or 0
#         )


@app.route('/dashboard/hq/<string:branch_name>')
@login_required
def render_dashboard_hq(branch_name):
    today = date.today()

    with get_db_connection() as conn:
        # Fetch all employees in the branch
        employees = conn.execute(
            """
            SELECT e.ID, e.Name, e.Age, e.Salary, e.Branch, 
                   p.PositionName AS Position, 
                   d.Name AS Department
            FROM employees e
            LEFT JOIN positions p ON e.position_id = p.ID
            LEFT JOIN departments d ON p.department_id = d.ID
            WHERE e.Branch = ?
            """,
            (branch_name,)
        ).fetchall()

        # Handle case where no employees are found
        if not employees:
            flash(f"No employees found in branch '{branch_name}'.", "warning")
            # ensure 'dashboard' route exists
            return redirect(url_for('dashboard'))

        # Count total employees
        employee_count = len(employees)

        # Count employees on approved leave today
        employees_on_leave_today = conn.execute(
            """
            SELECT COUNT(*)
            FROM leaves l
            JOIN employees e ON l.employee_id = e.ID
            WHERE e.Branch = ?
              AND ? BETWEEN l.start_date AND l.end_date
              AND l.status = 'Approved'
            """,
            (branch_name, today)
        ).fetchone()[0] or 0

        # Format data for the template
        employee_data = [
            {
                'ID': emp['ID'],
                'Name': emp['Name'],
                'Age': emp['Age'],
                'Salary': emp['Salary'],
                'Branch': emp['Branch'],
                'Position': emp['Position'],
                'Department': emp['Department']
            }
            for emp in employees
        ]

        return render_template(
            'employees/hq_dashboard.html',
            employees=employee_data,
            employees_in_branch=employee_count,
            employees_on_leave_today=employees_on_leave_today
        )


@app.route('/dashboard/branch_manager/<string:branch_name>')
@login_required
def render_dashboard_branch_manager(branch_name):
    today = date.today()

    with get_db_connection() as conn:
        # Fetch all employees in the branch
        employees = conn.execute(
            """
            SELECT e.ID, e.Name, e.Age, e.Salary, e.Branch, 
                   p.PositionName AS Position, 
                   d.Name AS Department
            FROM employees e
            LEFT JOIN positions p ON e.position_id = p.ID
            LEFT JOIN departments d ON p.department_id = d.ID
            WHERE e.Branch = ?
            """,
            (branch_name,)
        ).fetchall()

        if not employees:
            flash("No employees found in this branch!", "danger")
            return redirect(url_for('dashboard'))

        # Count employees in the branch
        employee_count = len(employees)

        # Count employees on leave today
        employees_on_leave_today = conn.execute(
            """
            SELECT COUNT(*)
            FROM leaves l
            JOIN employees e ON l.employee_id = e.ID
            WHERE e.Branch = ?
              AND ? BETWEEN l.start_date AND l.end_date
              AND l.status = 'Approved'
            """,
            (branch_name, today)
        ).fetchone()[0]

        # Prepare employee data for rendering
        employee_data = [
            {
                'ID': emp['ID'],
                'Name': emp['Name'],
                'Age': emp['Age'],
                'Salary': emp['Salary'],
                'Branch': emp['Branch'],
                'Position': emp['Position'],
                'Department': emp['Department']
            }
            for emp in employees
        ]

        return render_template(
            'employees/bm_dashboard.html',
            employees=employee_data,
            employees_in_branch=employee_count,
            employees_on_leave_today=employees_on_leave_today
        )


# @app.route('/dashboard/employee')
# @login_required
# def render_dashboard_employees():
#     # Optional: you could skip the 'start_date' and 'end_date' request arguments if they're not needed
#     start_date = request.args.get('start_date')
#     end_date = request.args.get('end_date')

#     with get_db_connection() as conn:
#         # If you want data for the current logged-in user, use `current_user.id`
#         employee_id = current_user.id

#         payroll_query = """
#             SELECT COALESCE(SUM(p.base_salary + p.bonus - p.deductions - p.tax), 0) AS total_salary
#             FROM payroll p
#             WHERE p.employee_id = ?
#         """

#         leave_by_day_query = """
#             SELECT
#                 DATE(l.start_date) AS leave_date,
#                 SUM(l.service_count) AS leave_count
#             FROM leaves l
#             WHERE l.employee_id = ?
#             GROUP BY leave_date
#             ORDER BY leave_date
#         """

#         leave_by_day_params = [employee_id]
#         if start_date and end_date:
#             leave_by_day_query = """
#                 SELECT
#                     DATE(l.start_date) AS leave_date,
#                     SUM(l.service_count) AS leave_count
#                 FROM leaves l
#                 WHERE l.employee_id = ?
#                 AND l.start_date >= ? AND l.end_date <= ?
#                 GROUP BY leave_date
#                 ORDER BY leave_date
#             """
#             leave_by_day_params.extend([start_date, end_date])

#         leave_by_day = conn.execute(
#             leave_by_day_query, leave_by_day_params).fetchall()

#         payroll_params = [employee_id]
#         if start_date and end_date:
#             payroll_query += " AND p.period_start_date >= ? AND p.period_end_date <= ?"
#             payroll_params.extend([start_date, end_date])

#         total_salary = conn.execute(payroll_query, payroll_params).fetchone()
#         total_salary = total_salary["total_salary"] if total_salary else 0

#         leaves_query = """
#             SELECT
#                 COALESCE(SUM(l.service_count), 0) AS total_leaves_days,
#                 COALESCE(SUM(l.leave_hours), 0) AS total_leaves_hours
#             FROM leaves l
#             WHERE l.employee_id = ?
#         """
#         leaves_params = [employee_id]
#         if start_date and end_date:
#             leaves_query += " AND l.start_date >= ? AND l.end_date <= ?"
#             leaves_params.extend([start_date, end_date])

#         leaves = conn.execute(leaves_query, leaves_params).fetchone()

#         total_leaves_days = leaves["total_leaves_days"] if leaves else 0
#         total_leaves_hours = leaves["total_leaves_hours"] if leaves else 0

#         # Build lists to send to the template
#         leave_days = [row['leave_date'] for row in leave_by_day]
#         leave_counts = [row['leave_count'] for row in leave_by_day]

#         # Calculate days and hours from leave hours
#         days, hours = divmod(total_leaves_hours, 8)
#         hours_to_days = days + (hours / 8)
#         cons_days = total_leaves_days + hours_to_days
#         formatted_value = math.trunc(cons_days)
#         mod_hours = round(hours / 8, 2)
#         total_leave_pretty = f"{int(hours_to_days)} Days | {int(mod_hours * 8)} hours"

#         return render_template(
#             'employees/employee_dashboard.html',
#             total_salary=total_salary,
#             total_leaves_days=total_leaves_days,
#             total_leaves_hours="{:.0f} hours".format(total_leaves_hours),
#             total_leave_hours_to_day=hours_to_days,
#             total_leave_pretty=total_leave_pretty,
#             cons_days=formatted_value,
#             leave_days=leave_days,
#             leave_counts=leave_counts
#         )


# @app.route('/dashboard/employee')
# @login_required
# def render_dashboard_employees():
#     # Optional: you could skip the 'start_date' and 'end_date' request arguments if they're not needed
#     start_date = request.args.get('start_date')
#     end_date = request.args.get('end_date')

#     with get_db_connection() as conn:
#         # If you want data for the current logged-in user, use `current_user.id`
#         employee_id = current_user.id

#         payroll_query = """
#             SELECT COALESCE(SUM(p.base_salary + p.bonus - p.deductions - p.tax), 0) AS total_salary
#             FROM payroll p
#             WHERE p.employee_id = ?
#         """

#         leave_by_day_query = """
#             SELECT
#                 DATE(l.start_date) AS leave_date,
#                 SUM(l.service_count) AS leave_count
#             FROM leaves l
#             WHERE l.employee_id = ?
#             GROUP BY leave_date
#             ORDER BY leave_date
#         """

#         leave_by_day_params = [employee_id]
#         if start_date and end_date:
#             leave_by_day_query = """
#                 SELECT
#                     DATE(l.start_date) AS leave_date,
#                     SUM(l.service_count) AS leave_count
#                 FROM leaves l
#                 WHERE l.employee_id = ?
#                 AND l.start_date >= ? AND l.end_date <= ?
#                 GROUP BY leave_date
#                 ORDER BY leave_date
#             """
#             leave_by_day_params.extend([start_date, end_date])

#         leave_by_day = conn.execute(
#             leave_by_day_query, leave_by_day_params).fetchall()

#         payroll_params = [employee_id]
#         if start_date and end_date:
#             payroll_query += " AND p.period_start_date >= ? AND p.period_end_date <= ?"
#             payroll_params.extend([start_date, end_date])

#         total_salary = conn.execute(payroll_query, payroll_params).fetchone()
#         total_salary = total_salary["total_salary"] if total_salary and total_salary["total_salary"] is not None else 0

#         leaves_query = """
#             SELECT
#                 COALESCE(SUM(l.service_count), 0) AS total_leaves_days,
#                 COALESCE(SUM(l.leave_hours), 0) AS total_leaves_hours
#             FROM leaves l
#             WHERE l.employee_id = ?
#         """
#         leaves_params = [employee_id]
#         if start_date and end_date:
#             leaves_query += " AND l.start_date >= ? AND l.end_date <= ?"
#             leaves_params.extend([start_date, end_date])

#         leaves = conn.execute(leaves_query, leaves_params).fetchone()

#         total_leaves_days = leaves["total_leaves_days"] if leaves and leaves["total_leaves_days"] is not None else 0
#         total_leaves_hours = leaves["total_leaves_hours"] if leaves and leaves["total_leaves_hours"] is not None else 0

#         # Build lists to send to the template
#         leave_days = [row['leave_date'] for row in leave_by_day]
#         leave_counts = [row['leave_count'] for row in leave_by_day]

#         # Calculate days and hours from leave hours
#         days, hours = divmod(total_leaves_hours, 8)
#         hours_to_days = days + (hours / 8)
#         cons_days = total_leaves_days + hours_to_days
#         formatted_value = math.trunc(cons_days)
#         mod_hours = round(hours / 8, 2)
#         total_leave_pretty = f"{int(hours_to_days)} Days | {int(mod_hours * 8)} hours"

#         return render_template(
#             'employees/employee_dashboard.html',
#             total_salary=total_salary,
#             total_leaves_days=total_leaves_days,
#             total_leaves_hours="{:.0f} hours".format(total_leaves_hours),
#             total_leave_hours_to_day=hours_to_days,
#             total_leave_pretty=total_leave_pretty,
#             cons_days=formatted_value,
#             leave_days=leave_days,
#             leave_counts=leave_counts
#         )


@app.route('/dashboard/employee')
@login_required
def render_dashboard_employees():
    # Optional: you could skip the 'start_date' and 'end_date' request arguments if they're not needed
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    with get_db_connection() as conn:
        # If you want data for the current logged-in user, use `current_user.id`
        employee_id = current_user.employee_id if current_user.employee_id is not None else 0

        payroll_query = """
            SELECT COALESCE(SUM(p.base_salary + p.bonus - p.deductions - p.tax), 0) AS total_salary
            FROM payroll p
            WHERE p.employee_id = ?
        """

        leave_by_day_query = """
            SELECT
                DATE(l.start_date) AS leave_date,
                SUM(l.service_count) AS leave_count
            FROM leaves l
            WHERE l.employee_id = ?
            GROUP BY leave_date
            ORDER BY leave_date
        """

        leave_by_day_params = [employee_id]
        if start_date and end_date:
            leave_by_day_query = """
                SELECT
                    DATE(l.start_date) AS leave_date,
                    SUM(l.service_count) AS leave_count
                FROM leaves l
                WHERE l.employee_id = ?
                AND l.start_date >= ? AND l.end_date <= ?
                GROUP BY leave_date
                ORDER BY leave_date
            """
            leave_by_day_params.extend([start_date, end_date])

        leave_by_day = conn.execute(
            leave_by_day_query, leave_by_day_params).fetchall()

        payroll_params = [employee_id]
        if start_date and end_date:
            payroll_query += " AND p.period_start_date >= ? AND p.period_end_date <= ?"
            payroll_params.extend([start_date, end_date])

        total_salary = conn.execute(payroll_query, payroll_params).fetchone()
        total_salary = total_salary["total_salary"] if total_salary and total_salary["total_salary"] is not None else 0

        leaves_query = """
            SELECT
                COALESCE(SUM(l.service_count), 0) AS total_leaves_days,
                COALESCE(SUM(l.leave_hours), 0) AS total_leaves_hours
            FROM leaves l
            WHERE l.employee_id = ?
        """
        leaves_params = [employee_id]
        if start_date and end_date:
            leaves_query += " AND l.start_date >= ? AND l.end_date <= ?"
            leaves_params.extend([start_date, end_date])

        leaves = conn.execute(leaves_query, leaves_params).fetchone()

        total_leaves_days = leaves["total_leaves_days"] if leaves and leaves["total_leaves_days"] is not None else 0
        total_leaves_hours = leaves["total_leaves_hours"] if leaves and leaves["total_leaves_hours"] is not None else 0

        # Build lists to send to the template
        leave_days = [row['leave_date'] for row in leave_by_day]
        leave_counts = [row['leave_count'] for row in leave_by_day]

        # Calculate days and hours from leave hours
        days, hours = divmod(total_leaves_hours, 8)
        hours_to_days = days + (hours / 8)
        cons_days = total_leaves_days + hours_to_days
        formatted_value = math.trunc(cons_days)
        mod_hours = round(hours / 8, 2)
        total_leave_pretty = f"{int(hours_to_days)} Days | {int(mod_hours * 8)} hours"

        # You can fetch employee details here if you need to display them
        employee_data = {
            'id': employee_id,
            # Add other employee details if needed
        }

        return render_template(
            'employees/employee_dashboard.html',
            employee=employee_data,  # Pass employee data to the template
            total_salary=total_salary,
            total_leaves_days=total_leaves_days,
            total_leaves_hours="{:.0f} hours".format(total_leaves_hours),
            total_leave_hours_to_day=hours_to_days,
            total_leave_pretty=total_leave_pretty,
            cons_days=formatted_value,
            leave_days=leave_days,
            leave_counts=leave_counts
        )


# @app.route('/dashboard/employee/<int:employee_id>')
# @login_required
# def render_dashboard_employees(employee_id):
#     start_date = request.args.get('start_date')
#     end_date = request.args.get('end_date')

#     with get_db_connection() as conn:
#         employee = conn.execute(
#             """
#             SELECT e.ID, e.Name, e.Age, e.Salary, e.Branch,
#                    p.PositionName AS Position, d.Name AS Department
#             FROM employees e
#             LEFT JOIN positions p ON e.position_id = p.ID
#             LEFT JOIN departments d ON p.department_id = d.ID
#             WHERE e.ID = ?
#             """,
#             (employee_id,)
#         ).fetchone()

#         if not employee:
#             flash("Employee not found!", "danger")
#             return redirect(url_for('dashboard', id=current_user.id))

#         employee_data = {
#             'ID': employee['ID'] or '',
#             'Name': employee['Name'] or '',
#             'Age': employee['Age'] or '',
#             'Salary': employee['Salary'] or '',
#             'Branch': employee['Branch'] or '',
#             'Position': employee['Position'] or '',
#             'Department': employee['Department'] or ''
#         }

#         payroll_query = """
#             SELECT COALESCE(SUM(p.base_salary + p.bonus - p.deductions - p.tax), 0) AS total_salary
#             FROM payroll p
#             WHERE p.employee_id = ?
#         """

#         leave_by_day_query = """
#             SELECT
#                 DATE(l.start_date) AS leave_date,
#                 SUM(l.service_count) AS leave_count
#             FROM leaves l
#             WHERE l.employee_id = ?
#             GROUP BY leave_date
#             ORDER BY leave_date
#         """
#         # leave_by_day_query
#         leave_by_day_params = [employee['ID']]
#         if start_date and end_date:
#             leave_by_day_query = """
#                 SELECT
#                     DATE(l.start_date) AS leave_date,
#                     SUM(l.service_count) AS leave_count
#                 FROM leaves l
#                 WHERE l.employee_id = ?
#                 AND l.start_date >= ? AND l.end_date <= ?
#                 GROUP BY leave_date
#                 ORDER BY leave_date
#             """
#             leave_by_day_params.extend([start_date, end_date])

#         leave_by_day = conn.execute(
#             leave_by_day_query, leave_by_day_params).fetchall()

#         payroll_params = [employee['ID']]
#         if start_date and end_date:
#             payroll_query += " AND p.period_start_date >= ? AND p.period_end_date <= ?"
#             payroll_params.extend([start_date, end_date])

#         total_salary = conn.execute(payroll_query, payroll_params).fetchone()
#         total_salary = total_salary["total_salary"] if total_salary else 0

#         leaves_query = """
#             SELECT
#                 COALESCE(SUM(l.service_count), 0) AS total_leaves_days,
#                 COALESCE(SUM(l.leave_hours), 0) AS total_leaves_hours
#             FROM leaves l
#             WHERE l.employee_id = ?
#         """
#         leaves_params = [employee['ID']]
#         if start_date and end_date:
#             leaves_query += " AND l.start_date >= ? AND l.end_date <= ?"
#             leaves_params.extend([start_date, end_date])

#         leaves = conn.execute(leaves_query, leaves_params).fetchone()

#         total_leaves_days = leaves["total_leaves_days"] if leaves else 0
#         # keep as number
#         total_leaves_hours = leaves["total_leaves_hours"] if leaves else 0
#         # Build lists to send to the template
#         leave_days = [row['leave_date'] for row in leave_by_day]
#         leave_counts = [row['leave_count'] for row in leave_by_day]

#         days, hours = divmod(total_leaves_hours, 8)
#         hours_to_days = days + (hours / 8)
#         cons_days = total_leaves_days + hours_to_days
#         formatted_value = math.trunc(cons_days)
#         mod_hours = round(hours / 8, 2)
#         total_leave_pretty = f"{int(hours_to_days)} Days | {int(mod_hours * 8)} hours"
#         # ---------------------------------

#         return render_template(
#             'employees/employee_dashboard.html',
#             employee=employee_data,
#             total_salary=total_salary,
#             total_leaves_days=total_leaves_days,
#             total_leaves_hours="{:.0f} hours".format(total_leaves_hours),
#             total_leave_hours_to_day=hours_to_days,
#             total_leave_pretty=total_leave_pretty,
#             cons_days=formatted_value,
#             leave_days=leave_days,
#             leave_counts=leave_counts
#         )


# def render_dashboard(user_id):
#     timeout_threshold = 15  # minutes

#     with get_db_connection() as conn:
#         total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
#         total_employees = conn.execute(
#             "SELECT COUNT(*) FROM employees").fetchone()[0]
#         average_age = conn.execute(
#             "SELECT AVG(Age) FROM employees").fetchone()[0] or 0
#         total_salary = conn.execute(
#             "SELECT SUM(Salary) FROM employees").fetchone()[0] or 0

#         # Employee count and total salary by branch
#         branch_data = conn.execute("""
#             SELECT Branch, COUNT(*) AS employee_count, SUM(Salary) AS total_salary
#             FROM employees
#             GROUP BY Branch
#         """).fetchall()

#         branch_names = [row['Branch'] for row in branch_data]
#         branch_counts = [row['employee_count'] for row in branch_data]
#         branch_salaries = [row['total_salary'] for row in branch_data]

#         total_branches = len(branch_names)
#         total_payroll = total_salary

#         # Fetch online users
#         online_users = conn.execute('''
#             SELECT u.ID AS user_id, u.UserName, u.Email, ou.last_active_time
#             FROM online_users ou
#             JOIN users u ON ou.user_id=u.ID
#             WHERE strftime('%s', 'now') - strftime('%s', ou.last_active_time) <= ? * 60
#         ''', (timeout_threshold,)).fetchall()

#     return render_template(
#         'dashboard.html',
#         total_users=total_users,
#         total_employees=total_employees,
#         average_age=average_age,
#         total_salary=total_salary,
#         total_branches=total_branches,
#         total_payroll=total_payroll,
#         branch_names=branch_names,
#         branch_counts=branch_counts,
#         branch_salaries=branch_salaries,
#         online_users=online_users
#     )


# def render_dashboard(user_id):
#     timeout_threshold = 15  # minutes

#     with get_db_connection() as conn:
#         total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
#         total_employees = conn.execute(
#             "SELECT COUNT(*) FROM employees").fetchone()[0]
#         average_age = conn.execute(
#             "SELECT AVG(Age) FROM employees").fetchone()[0] or 0
#         total_salary = conn.execute(
#             "SELECT SUM(Salary) FROM employees").fetchone()[0] or 0

#         # 📌 Add this query to count total leaves
#         total_leaves = conn.execute(
#             "SELECT COUNT(*) FROM leaves").fetchone()[0]

#         # Employee count and total salary by branch
#         branch_data = conn.execute("""
#             SELECT Branch, COUNT(*) AS employee_count, SUM(Salary) AS total_salary
#             FROM employees
#             GROUP BY Branch
#         """).fetchall()

#         branch_names = [row['Branch'] for row in branch_data]
#         branch_counts = [row['employee_count'] for row in branch_data]
#         branch_salaries = [row['total_salary'] for row in branch_data]

#         total_branches = len(branch_names)
#         total_payroll = total_salary

#         # Fetch online users
#         online_users = conn.execute('''
#             SELECT u.ID AS user_id, u.UserName, u.Email, ou.last_active_time
#             FROM online_users ou
#             JOIN users u ON ou.user_id=u.ID
#             WHERE strftime('%s', 'now') - strftime('%s', ou.last_active_time) <= ? * 60
#         ''', (timeout_threshold,)).fetchall()

#     return render_template(
#         'dashboard.html',
#         total_users=total_users,
#         total_employees=total_employees,
#         average_age=average_age,
#         total_salary=total_salary,
#         total_leaves=total_leaves,  # ✅ Pass to template
#         total_branches=total_branches,
#         total_payroll=total_payroll,
#         branch_names=branch_names,
#         branch_counts=branch_counts,
#         branch_salaries=branch_salaries,
#         online_users=online_users
#     )


def render_dashboard(user_id):
    timeout_threshold = 15  # minutes
    today = date.today().isoformat()  # e.g. '2025-06-16'

    with get_db_connection() as conn:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_employees = conn.execute(
            "SELECT COUNT(*) FROM employees").fetchone()[0]
        average_age = conn.execute(
            "SELECT AVG(Age) FROM employees").fetchone()[0] or 0
        total_salary = conn.execute(
            "SELECT SUM(Salary) FROM employees").fetchone()[0] or 0

        total_leaves = conn.execute(
            "SELECT COUNT(*) FROM leaves").fetchone()[0]

        # 📌 Query for leaves happening today
        leaves_today = conn.execute("""
            SELECT COUNT(*) FROM leaves
            WHERE date(?) BETWEEN date(start_date) AND date(end_date)
        """, (today,)).fetchone()[0]

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

        online_users = conn.execute('''
            SELECT u.ID AS user_id, u.UserName, u.Email, ou.last_active_time
            FROM online_users ou
            JOIN users u ON ou.user_id=u.ID
            WHERE strftime('%s', 'now') - strftime('%s', ou.last_active_time) <= ? * 60
        ''', (timeout_threshold,)).fetchall()

        # 📊 Leaves per branch
        # leaves_by_branch = conn.execute("""
        #     SELECT e.Branch, COUNT(l.id) AS leave_count
        #     FROM leaves l
        #     JOIN employees e ON e.ID = l.employee_id
        #     GROUP BY e.Branch
        # """).fetchall()
        leaves_by_branch = conn.execute("""
            SELECT e.Branch, SUM(l.service_count) AS total_service_count
            FROM leaves l
            JOIN employees e ON e.ID = l.employee_id
            GROUP BY e.Branch
        """).fetchall()

        leave_branch_names = [row['Branch'] for row in leaves_by_branch]
        leave_branch_counts = [row['total_service_count']
                               or 0 for row in leaves_by_branch]

    return render_template(
        'dashboard.html',
        total_users=total_users,
        total_employees=total_employees,
        average_age=average_age,
        total_salary=total_salary,
        total_leaves=total_leaves,
        leaves_today=leaves_today,  # ✅ New variable
        total_branches=total_branches,
        total_payroll=total_payroll,
        branch_names=branch_names,
        branch_counts=branch_counts,
        branch_salaries=branch_salaries,
        online_users=online_users,
        leave_branch_names=leave_branch_names,
        leave_branch_counts=leave_branch_counts,
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


@app.route('/employees/import', methods=['GET', 'POST'])
@login_required
def import_employees():
    if request.method == 'POST':
        f = request.files.get('excel_file')
        if not f or f.filename == '':
            flash('Please choose an Excel file.', 'error')
            return redirect(request.url)

        if not allowed_excel(f.filename):
            flash('Supported formats: .xlsx or .xls', 'error')
            return redirect(request.url)

        try:
            df = pd.read_excel(f)
        except Exception as e:
            flash(f'Could not read file: {e}', 'error')
            return redirect(request.url)

        required = [
            'name', 'age', 'department', 'salary', 'position_id', 'joining_date', 'status', 'branch', 'user_id',
            'phone_number', 'email', 'address', 'emergency_contact_name', 'emergency_contact_phone',
            'employees_height', 'ethnicity', 'nationality', 'religion', 'family_status', 'place_of_birth',
            'permanent_address', 'village', 'commune', 'district', 'province', 'home_number', 'street_number',
            'group_name', 'personal_phone_number', 'level_of_culture', 'skill', 'name_of_educational_institution',
            'knowledge_of_foreign_languages', 'current_function', 'id_card_number', 'work_at', 'employment_id',
            'employment_date', 'khmer_nationality_identity_card', 'passing_test_date', 'residence_book_or_family_book',
            'made_on', 'have_a_number_of_children', 'father_name', 'mother_name', 'father_status', 'father_occupation',
            'mother_occupation', 'mother_status', 'father_permanent_address', 'mother_permanent_address',
            'parents_village', 'parents_commune', 'parents_district', 'parents_province', 'parents_home_number',
            'parents_street_number', 'parents_group', 'parents_phone'
        ]

        missing = [c for c in required if c not in df.columns]
        if missing:
            flash(f'Missing columns: {", ".join(missing)}', 'error')
            return redirect(request.url)

        inserted, skipped = 0, 0
        with get_db_connection() as conn:
            for _, row in df.iterrows():
                if pd.isna(row['name']) or pd.isna(row['department']):
                    skipped += 1
                    continue

                jd = row['joining_date']
                if isinstance(jd, (pd.Timestamp, datetime)):
                    jd = jd.date()

                conn.execute("""
                    INSERT INTO employees (
                        name, age, department, salary, position_id, joining_date, status, branch, user_id,
                        phone_number, email, address, emergency_contact_name, emergency_contact_phone,
                        employees_height, ethnicity, nationality, religion, family_status, place_of_birth,
                        permanent_address, village, commune, district, province, home_number, street_number,
                        group_name, personal_phone_number, level_of_culture, skill, name_of_educational_institution,
                        knowledge_of_foreign_languages, current_function, id_card_number, work_at, employment_id,
                        employment_date, khmer_nationality_identity_card, passing_test_date, residence_book_or_family_book,
                        made_on, have_a_number_of_children, father_name, mother_name, father_status, father_occupation,
                        mother_occupation, mother_status, father_permanent_address, mother_permanent_address,
                        parents_village, parents_commune, parents_district, parents_province, parents_home_number,
                        parents_street_number, parents_group, parents_phone
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, tuple(row[col] for col in required))
                inserted += 1
            conn.commit()

        flash(f'Imported {inserted} employees ({skipped} skipped).', 'success')
        return redirect(url_for('list_employees'))

    return render_template('employees/import.html')


@app.route('/employees/import/template')
@login_required
def download_import_template():
    data = [
        {
            "name": "Suong Sambo",
            "age": 29,
            "department": "ITD",
            "salary": 850.00,
            "position_id": 1,
            "joining_date": "2022-03-15",
            "status": "Active",
            "branch": "Phnom Penh",
            "user_id": 1,
            "phone_number": "012345678",
            "email": "suong.sambo@example.com",
            "address": "House 15, St. 310, Phnom Penh",
            "emergency_contact_name": "Chanthy Dara",
            "emergency_contact_phone": "097654321",
            "employees_height": "175 cm",
            "ethnicity": "Khmer",
            "nationality": "Cambodian",
            "religion": "Buddhism",
            "family_status": "single",
            "place_of_birth": "Phnom Penh",
            "permanent_address": "Phnom Penh Cambodia",
            "village": "Prek Luong",
            "commune": "Svay Por",
            "district": "Phnom Penh",
            "province": "Phnom Penh",
            "home_number": "12A",
            "street_number": "310",
            "group_name": "Group 5",
            "personal_phone_number": "092112233",
            "level_of_culture": "bachelor_degree",
            "skill": "Accounting",
            "name_of_educational_institution": "Royal University of Law and Economics",
            "knowledge_of_foreign_languages": "English, Chinese",
            "current_function": "Senior Accountant",
            "id_card_number": "0203001234567",
            "work_at": "Phnom Penh Office",
            "employment_id": "EMP123456",
            "employment_date": "2022-03-01",
            "khmer_nationality_identity_card": "123456789",
            "passing_test_date": "2022-02-15",
            "residence_book_or_family_book": "Family Book No. 123",
            "made_on": "2022-03-10",
            "have_a_number_of_children": 0,
            "father_name": "Sok Vanna",
            "mother_name": "Vanny Nary",
            "father_status": "Alive",
            "father_occupation": "Teacher",
            "mother_occupation": "Farmer",
            "mother_status": "Alive",
            "father_permanent_address": "Phnom Penh Province",
            "mother_permanent_address": "Phnom Penh Province",
            "parents_village": "Prek Luong",
            "parents_commune": "Svay Por",
            "parents_district": "Phnom Penh",
            "parents_province": "Phnom Penh",
            "parents_home_number": "12A",
            "parents_street_number": "310",
            "parents_group": "Group 5",
            "parents_phone": "093876543"
        }


    ]
    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="employee_import_template.xlsx",
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@app.route('/employees/add', methods=['GET', 'POST'])
@login_required
def add_employee():
    branches = []
    users = []
    positions = []
    departments = []

    # Get branches, users, and positions from the database
    with get_db_connection() as conn:
        branches = conn.execute("SELECT * FROM branches").fetchall()

        users = conn.execute(
            "SELECT id, UserName FROM users"
        ).fetchall()
        positions = conn.execute("SELECT * FROM positions").fetchall()
        departments = conn.execute("SELECT * FROM departments").fetchall()

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
        passing_test_date = request.form.get('passing_test_date')
        residence_book_or_family_book = request.form.get(
            'residence_book_or_family_book')
        made_on = request.form.get('made_on')
        have_a_number_of_children = request.form.get(
            'have_a_number_of_children')
        father_name = request.form.get('father_name')
        mother_name = request.form.get('mother_name')
        father_status = request.form.get('father_status')
        father_occupation = request.form.get('father_occupation')
        mother_occupation = request.form.get('mother_occupation')
        mother_status = request.form.get('mother_status')
        father_permanent_address = request.form.get('father_permanent_address')
        mother_permanent_address = request.form.get('mother_permanent_address')
        parents_village = request.form.get('parents_village')
        parents_commune = request.form.get('parents_commune')
        parents_district = request.form.get('parents_district')
        parents_province = request.form.get('parents_province')
        parents_home_number = request.form.get('parents_home_number')
        parents_street_number = request.form.get('parents_street_number')
        parents_group = request.form.get('parents_group')
        parents_phone = request.form.get('parents_phone')

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
                    khmer_nationality_identity_card,
                    passing_test_date, residence_book_or_family_book, made_on, have_a_number_of_children,
                    father_name, mother_name, father_status, father_occupation, mother_occupation, mother_status,
                    father_permanent_address, mother_permanent_address, parents_village, parents_commune, parents_district,
                    parents_province, parents_home_number, parents_street_number, parents_group, parents_phone,
                    photo, fingerprints, signature)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? , ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, age, department, salary, position_id, joining_date, status, branch, user_id,
                 phone_number, email, address, emergency_contact_name, emergency_contact_phone,
                 employees_height, ethnicity, nationality, religion, family_status, place_of_birth, permanent_address, village,
                 commune, district, province, home_number, street_number, group_name,
                 personal_phone_number, level_of_culture, skill, name_of_educational_institution,
                 knowledge_of_foreign_languages, current_function, id_card_number, work_at, employment_id, employment_date,
                 khmer_nationality_identity_card, passing_test_date, residence_book_or_family_book, made_on, have_a_number_of_children,
                 father_name, mother_name, father_status, father_occupation, mother_occupation, mother_status,
                 father_permanent_address, mother_permanent_address, parents_village, parents_commune, parents_district,
                 parents_province, parents_home_number, parents_street_number, parents_group, parents_phone, photo_data, fingerprints_data, signature_data)
            )
            conn.commit()

        # Redirect to employee list after successful insertion
        return redirect(url_for('list_employees'))

    # Render the form to add a new employee with necessary context
    return render_template('employees/add_employee.html', branches=branches, users=users, positions=positions, departments=departments)


@app.route('/employees/complete/profile', methods=['GET', 'POST'])
@login_required
def add_employee_profile():
    branches = []
    users = []
    positions = []
    departments = []

    # Get branches, users, and positions from the database
    with get_db_connection() as conn:
        branches = conn.execute("SELECT * FROM branches").fetchall()

        users = conn.execute(
            "SELECT id, UserName FROM users"
        ).fetchall()
        positions = conn.execute("SELECT * FROM positions").fetchall()
        departments = conn.execute("SELECT * FROM departments").fetchall()

    if request.method == 'POST':
        # Collect all form data
        name = request.form['name']
        age = request.form['age']
        department = request.form['department']
        salary = request.form['salary']
        position_id = request.form['position_id']
        joining_date = request.form['joining_date']
        status = request.form.get('status', 'Active')
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
        passing_test_date = request.form.get('passing_test_date')
        residence_book_or_family_book = request.form.get(
            'residence_book_or_family_book')
        made_on = request.form.get('made_on')
        have_a_number_of_children = request.form.get(
            'have_a_number_of_children')
        father_name = request.form.get('father_name')
        mother_name = request.form.get('mother_name')
        father_status = request.form.get('father_status')
        father_occupation = request.form.get('father_occupation')
        mother_occupation = request.form.get('mother_occupation')
        mother_status = request.form.get('mother_status')
        father_permanent_address = request.form.get('father_permanent_address')
        mother_permanent_address = request.form.get('mother_permanent_address')
        parents_village = request.form.get('parents_village')
        parents_commune = request.form.get('parents_commune')
        parents_district = request.form.get('parents_district')
        parents_province = request.form.get('parents_province')
        parents_home_number = request.form.get('parents_home_number')
        parents_street_number = request.form.get('parents_street_number')
        parents_group = request.form.get('parents_group')
        parents_phone = request.form.get('parents_phone')

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
                    khmer_nationality_identity_card,
                    passing_test_date, residence_book_or_family_book, made_on, have_a_number_of_children,
                    father_name, mother_name, father_status, father_occupation, mother_occupation, mother_status,
                    father_permanent_address, mother_permanent_address, parents_village, parents_commune, parents_district,
                    parents_province, parents_home_number, parents_street_number, parents_group, parents_phone,
                    photo, fingerprints, signature)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? , ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, age, department, salary, position_id, joining_date, status, branch, user_id,
                 phone_number, email, address, emergency_contact_name, emergency_contact_phone,
                 employees_height, ethnicity, nationality, religion, family_status, place_of_birth, permanent_address, village,
                 commune, district, province, home_number, street_number, group_name,
                 personal_phone_number, level_of_culture, skill, name_of_educational_institution,
                 knowledge_of_foreign_languages, current_function, id_card_number, work_at, employment_id, employment_date,
                 khmer_nationality_identity_card, passing_test_date, residence_book_or_family_book, made_on, have_a_number_of_children,
                 father_name, mother_name, father_status, father_occupation, mother_occupation, mother_status,
                 father_permanent_address, mother_permanent_address, parents_village, parents_commune, parents_district,
                 parents_province, parents_home_number, parents_street_number, parents_group, parents_phone, photo_data, fingerprints_data, signature_data)
            )
            conn.commit()

        # Redirect to employee list after successful insertion
        return redirect(url_for('profile', user_id=current_user.id))

    # Render the form to add a new employee with necessary context
    return render_template('employees/add_employee_profile.html', branches=branches, users=users, positions=positions, departments=departments)


# @app.route('/employees/edit/<int:id>', methods=['GET', 'POST'])
# @login_required
# def edit_employee(id):
#     with get_db_connection() as conn:
#         employee = conn.execute(
#             "SELECT * FROM employees WHERE id = ?", (id,)).fetchone()
#         branches = conn.execute("SELECT * FROM branches").fetchall()
#         positions = conn.execute("SELECT * FROM positions").fetchall()

#     if request.method == 'POST':
#         name = request.form['name']
#         age = request.form['age']
#         department = request.form['department']
#         salary = request.form['salary']
#         position_id = request.form['position_id']
#         joining_date = request.form['joining_date']
#         status = request.form['status']
#         branch = request.form['branch']
#         phone_number = request.form['phone_number']
#         email = request.form['email']
#         address = request.form['address']
#         emergency_contact_name = request.form['emergency_contact_name']
#         emergency_contact_phone = request.form['emergency_contact_phone']

#         with get_db_connection() as conn:
#             conn.execute(
#                 """UPDATE employees SET name = ?, age = ?, department = ?, salary = ?, position_id = ?, joining_date = ?,
#                    status = ?, branch = ?, phone_number = ?, email = ?, address = ?, emergency_contact_name = ?, emergency_contact_phone = ?
#                    WHERE id = ?""",
#                 (name, age, department, salary, position_id, joining_date, status, branch,
#                  phone_number, email, address, emergency_contact_name, emergency_contact_phone, id)
#             )
#             conn.commit()
#         return redirect(url_for('list_employees'))

#     return render_template('/employees/edit_employee.html', employee=employee, branches=branches, positions=positions)


@app.route('/employees/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_employee(id):
    with get_db_connection() as conn:
        employee = conn.execute(
            "SELECT * FROM employees WHERE id = ?", (id,)
        ).fetchone()
        branches = conn.execute("SELECT * FROM branches").fetchall()
        positions = conn.execute("SELECT * FROM positions").fetchall()

    if request.method == 'POST':
        # Existing fields
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

        # New optional fields
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
        passing_test_date = request.form.get('passing_test_date')
        residence_book_or_family_book = request.form.get(
            'residence_book_or_family_book')
        made_on = request.form.get('made_on')
        have_a_number_of_children = request.form.get(
            'have_a_number_of_children')
        father_name = request.form.get('father_name')
        mother_name = request.form.get('mother_name')
        father_status = request.form.get('father_status')
        father_occupation = request.form.get('father_occupation')
        mother_occupation = request.form.get('mother_occupation')
        mother_status = request.form.get('mother_status')
        father_permanent_address = request.form.get('father_permanent_address')
        mother_permanent_address = request.form.get('mother_permanent_address')
        parents_village = request.form.get('parents_village')
        parents_commune = request.form.get('parents_commune')
        parents_district = request.form.get('parents_district')
        parents_province = request.form.get('parents_province')
        parents_home_number = request.form.get('parents_home_number')
        parents_street_number = request.form.get('parents_street_number')
        parents_group = request.form.get('parents_group')
        parents_phone = request.form.get('parents_phone')

        # Convert have_a_number_of_children to int if not None and not empty
        if have_a_number_of_children:
            try:
                have_a_number_of_children = int(have_a_number_of_children)
            except ValueError:
                have_a_number_of_children = None
        else:
            have_a_number_of_children = None

        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE employees SET
                    name = ?, age = ?, department = ?, salary = ?, position_id = ?, joining_date = ?,
                    status = ?, branch = ?, phone_number = ?, email = ?, address = ?, emergency_contact_name = ?, emergency_contact_phone = ?,
                    employees_height = ?, ethnicity = ?, nationality = ?, religion = ?, family_status = ?, place_of_birth = ?, permanent_address = ?,
                    village = ?, commune = ?, district = ?, province = ?, home_number = ?, street_number = ?, group_name = ?, personal_phone_number = ?,
                    level_of_culture = ?, skill = ?, name_of_educational_institution = ?, knowledge_of_foreign_languages = ?, current_function = ?,
                    id_card_number = ?, work_at = ?, employment_id = ?, employment_date = ?, khmer_nationality_identity_card = ?,
                    passing_test_date = ?, residence_book_or_family_book = ?, made_on = ?, have_a_number_of_children = ?, father_name = ?,
                    mother_name = ?, father_status = ?, father_occupation = ?, mother_occupation = ?, mother_status = ?,
                    father_permanent_address = ?, mother_permanent_address = ?, parents_village = ?, parents_commune = ?, parents_district = ?,
                    parents_province = ?, parents_home_number = ?, parents_street_number = ?, parents_group = ?, parents_phone = ?
                WHERE id = ?
                """,
                (name, age, department, salary, position_id, joining_date,
                 status, branch, phone_number, email, address,
                 emergency_contact_name, emergency_contact_phone,
                 employees_height, ethnicity, nationality, religion, family_status, place_of_birth, permanent_address,
                 village, commune, district, province, home_number, street_number, group_name, personal_phone_number,
                 level_of_culture, skill, name_of_educational_institution, knowledge_of_foreign_languages, current_function,
                 id_card_number, work_at, employment_id, employment_date, khmer_nationality_identity_card,
                 passing_test_date, residence_book_or_family_book, made_on, have_a_number_of_children, father_name,
                 mother_name, father_status, father_occupation, mother_occupation, mother_status,
                 father_permanent_address, mother_permanent_address, parents_village, parents_commune, parents_district,
                 parents_province, parents_home_number, parents_street_number, parents_group, parents_phone,
                 id)
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


if __name__ == "__main__":
    init_db()
    # socketio.run(app, debug=True)
    # start_scheduler()
    # app.run(ssl_context=('cert.pem', 'key.pem'))  # Use self-signed cert
    socketio.run(app, port=9000)