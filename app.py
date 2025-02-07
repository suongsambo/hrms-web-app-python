from flask import request, jsonify
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import hashlib
import os
import pyotp
import requests
import glob
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from config import Config
from models.models import User

app = Flask(__name__)
app.config.from_object(Config)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize the Flask-Login manager
login_manager = LoginManager()
login_manager.init_app(app)

# Setup database connection


def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
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
        conn.execute('''
            CREATE TABLE IF NOT EXISTS branches (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                Status TEXT CHECK(Status IN ('Active', 'Inactive')) DEFAULT 'Active',
                CreateDate DATETIME,
                StartDate DATETIME,
                Description TEXT,
                Branch TEXT NOT NULL,
                BranchManagerName TEXT,
                ContactNumber TEXT,
                Address TEXT,
                DistrictProvince TEXT,
                RegisterDate DATETIME,
                LocalDescription TEXT,
                LocalAddress TEXT,
                LocalBranchManagerName TEXT,
                BranchProjectId TEXT,
                CapitalInjectionId TEXT,
                GroupID TEXT,
                MemberID TEXT
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_branches (
                user_id INTEGER,
                branch_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (ID) ON DELETE CASCADE,
                FOREIGN KEY (branch_id) REFERENCES branches (ID) ON DELETE CASCADE,
                PRIMARY KEY (user_id, branch_id)
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS login_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ip_address TEXT NOT NULL,
                city TEXT,
                region TEXT,
                country TEXT,
                user_agent TEXT,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (ID)
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS online_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (ID)
            )
        ''')
        conn.commit()

# Function to send OTP via Telegram


@app.before_request
def update_last_active_time():
    if current_user.is_authenticated:
        with get_db_connection() as conn:
            conn.execute('''
                UPDATE online_users
                SET last_active_time = CURRENT_TIMESTAMP
                WHERE user_id = ?
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
                    INSERT INTO users (UserName, Password, Email, Mobile1)
                    VALUES (?, ?, ?, ?)
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

# OTP verification route


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


# Test route for Telegram (for debugging)
@app.route("/test_telegram")
def test_telegram():
    test_message = "This is a test message from Flask!"
    try:
        send_telegram_message(test_message)
        return "Test message sent successfully!"
    except Exception as e:
        return f"Failed to send test message: {e}"


@login_manager.user_loader
def load_user(user_id):
    with get_db_connection() as conn:
        user_data = conn.execute(
            'SELECT * FROM users WHERE ID = ?', (user_id,)).fetchone()
        if user_data:
            return User(id=user_data['ID'], username=user_data['UserName'], password=user_data['Password'], email=user_data['Email'], branch=user_data['Branch'], is_admin=user_data['IsAdmin'])
        return None


@login_manager.unauthorized_handler
def unauthorized():
    return render_template('unauthorized.html'), 401


# Example uploaded_file route for displaying the uploaded image

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# @app.route('/file', methods=['GET', 'POST'])
# @login_required
# def upload_image():
#     if request.method == 'POST':

#         if 'file' not in request.files:
#             return 'No file part', 400

#         file = request.files['file']

#         if file.filename == '':
#             return 'No selected file', 400

#         if file and allowed_file(file.filename):
#             filename = f"{current_user.id}_{current_user.username}_{current_user.branch}_{secure_filename(file.filename)}"
#             file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
#             return redirect(url_for('list_user_files', filename=filename))

#     return render_template('/uploads/uploaded_file.html', current_user=current_user)


# # # Search File
# @app.route('/search_files', methods=['GET'])
# @login_required
# def search_files():
#     query = request.args.get('query', '').lower()

#     files = []
#     if query:
#         # Construct the search pattern
#         search_pattern = os.path.join(
#             app.config['UPLOAD_FOLDER'],
#             f"{current_user.id}_{current_user.username}_{current_user.branch}*{query}*"
#         )
#         # Use glob to find files matching the pattern
#         files = glob.glob(search_pattern)
#         # Extract filenames from the full paths
#         files = [os.path.basename(file) for file in files]

#     return render_template('/uploads/list_files.html', files=files, query=query, current_user=current_user)


# @app.route('/delete_file/<filename>', methods=['POST'])
# @login_required
# def delete_file(filename):
#     # Construct the full path of the file
#     file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

#     # Check if the file exists
#     if os.path.exists(file_path):
#         os.remove(file_path)  # Delete the file
#         flash('File deleted successfully', 'success')
#     else:
#         flash('File not found', 'error')

#     # Redirect to the file listing page
#     return redirect(url_for('list_user_files'))


# @app.route('/files', methods=['GET'])
# @login_required
# def list_user_files():
#     # Get the directory of the uploaded files
#     upload_folder = app.config['UPLOAD_FOLDER']

#     # Get the user's file prefix based on their ID, username, and branch
#     file_prefix = f"{current_user.id}_{current_user.username}_{current_user.branch}"

#     # List all files in the upload folder
#     files = os.listdir(upload_folder)

#     # Filter the files that match the pattern
#     user_files = [file for file in files if file.startswith(file_prefix)]

#     # Render a template to display the files (or return as a JSON response)
#     return render_template('/uploads/list_files.html', files=user_files, current_user=current_user)


# @app.route('/upload_files', methods=['GET', 'POST'])
# @login_required
# def upload_files():
#     if request.method != 'POST':
#         return render_template('/uploads/upload_files.html', current_user=current_user)
#     if 'files' not in request.files:
#         return 'No file part', 400

#     files = request.files.getlist('files')
#     if not files:
#         return 'No selected files', 400

#     upload_folder = app.config['UPLOAD_FOLDER']
#     file_prefix = f"{current_user.id}_{current_user.username}_{current_user.branch}"

#     for file in files:
#         if file.filename == '':
#             continue
#         if file and allowed_file(file.filename):
#             filename = f"{file_prefix}_{secure_filename(file.filename)}"
#             file.save(os.path.join(upload_folder, filename))

#     return redirect(url_for('list_user_files'))


# @app.route('/uploads/<filename>')
# def uploaded_file(filename):
#     return f'Image uploaded successfully: <img src="/static/uploads/{filename}" alt="uploaded image">'


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
    api_url = f"http://ipinfo.io/{ip}/json"  # Example API (ipinfo.io)
    response = requests.get(api_url)
    data = response.json()
    city = data.get('city', 'Unknown')
    region = data.get('region', 'Unknown')
    return city, region, data.get('country', 'Unknown')

# @app.route('/login', methods=['POST'])
# def login():
#     username = request.form['username']
#     password = hashlib.sha256(request.form['password'].encode()).hexdigest()

#     with get_db_connection() as conn:
#         user = conn.execute('''
#             SELECT * FROM users WHERE UserName = ? AND Password = ?
#         ''', (username, password)).fetchone()

#     if user:
#         user_obj = User(id=user['ID'], username=user['UserName'],
#                         password=user['Password'], email=user['Email'])
#         login_user(user_obj)  # Store the user session with Flask-Login
#         return redirect(url_for('dashboard'))

#     else:
#         return render_template('404.html'), 404


@app.route('/online_users', methods=['GET'])
# @login_required
def online_users():
    # Define the timeout threshold (e.g., 15 minutes)
    timeout_threshold = 15  # minutes

    with get_db_connection() as conn:
        online_users = conn.execute('''
            SELECT u.UserName, u.Email, ou.last_active_time
            FROM online_users ou
            JOIN users u ON ou.user_id = u.ID
            WHERE strftime('%s', 'now') - strftime('%s', ou.last_active_time) <= ? * 60
        ''', (timeout_threshold,)).fetchall()

    return render_template('online_users.html', online_users=online_users)


# @app.route('/login', methods=['POST'])
# def login():
#     username = request.form['username']
#     password = hashlib.sha256(request.form['password'].encode()).hexdigest()

#     # Get the user's IP address and user agent (browser/device info)
#     ip_address = request.remote_addr
#     user_agent = request.user_agent.string

#     # Optionally get the geolocation (City, Region, Country) based on IP address
#     city, region, country = get_geolocation(ip_address)

#     with get_db_connection() as conn:
#         user = conn.execute('''
#             SELECT * FROM users WHERE UserName = ? AND Password = ?
#         ''', (username, password)).fetchone()

#     if user:
#         # Log the login event (store user location and device info)
#         # You can log this information into the database, or print/log it
#         with get_db_connection() as conn:
#             conn.execute('''
#                 INSERT INTO login_logs (user_id, ip_address, city, region, country, user_agent)
#                 VALUES (?, ?, ?, ?, ?, ?)
#             ''', (user['ID'], ip_address, city, region, country, user_agent))
#             conn.commit()

#         # Create the user object and log the user in with Flask-Login
#         user_obj = User(id=user['ID'], username=user['UserName'],
#                         password=user['Password'], email=user['Email'])
#         login_user(user_obj)  # Store the user session with Flask-Login

#         flash(
#             f"Logged in from {city}, {region}, {country} using {user_agent}", 'success')
#         return redirect(url_for('dashboard'))

#     else:
#         flash("Invalid username or password", 'error')
#         return render_template('404.html'), 404


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
        user = conn.execute('''
            SELECT * FROM users WHERE UserName = ? AND Password = ?
        ''', (username, password)).fetchone()

    if user:
        # Log the login event (store user location and device info)
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO login_logs (user_id, ip_address, city, region, country, user_agent)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user['ID'], ip_address, city, region, country, user_agent))

            # Add user to online_users table or update if already exists
            conn.execute('''
                INSERT OR REPLACE INTO online_users (user_id, login_time, last_active_time)
                VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (user['ID'],))
            conn.commit()

        # Create the user object and log the user in with Flask-Login
        user_obj = User(id=user['ID'], username=user['UserName'],
                        password=user['Password'], email=user['Email'])
        login_user(user_obj)  # Store the user session with Flask-Login

        flash(
            f"Logged in from {city}, {region}, {country} using {user_agent}", 'success')
        return redirect(url_for('dashboard'))

    else:
        flash("Invalid username or password", 'error')
        return render_template('404.html'), 404


# @app.route('/logout', methods=['POST'])
# def logout():
#     logout_user()
#     return redirect(url_for('index'))


@app.route('/logout', methods=['POST'])
# @login_required
def logout():
    # Remove the user from the online_users table if logged in
    if current_user.is_authenticated:
        with get_db_connection() as conn:
            conn.execute('''
                DELETE FROM online_users WHERE user_id = ?
            ''', (current_user.id,))
            conn.commit()
        # Remove the user from the online_users table

    # Log out the user using Flask-Login
    logout_user()

    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('index'))


# @app.route('/change_password', methods=['GET', 'POST'])
# @login_required  # Ensure the user is logged in before accessing this route
# def change_password():
#     if request.method == 'POST':
#         old_password = request.form['old_password']
#         new_password = request.form['new_password']
#         confirm_password = request.form['confirm_password']

#         # Ensure new password and confirm password match
#         if new_password != confirm_password:
#             flash("New password and confirmation do not match", 'error')
#             return render_template('change_password.html')

#         # Hash the old password and check it against the stored password
#         old_password_hashed = hashlib.sha256(old_password.encode()).hexdigest()

#         with get_db_connection() as conn:
#             user = conn.execute('''
#                 SELECT * FROM users WHERE ID = ?
#             ''', (current_user.id,)).fetchone()

#             if user and user['Password'] == old_password_hashed:
#                 # Hash the new password and update the database
#                 new_password_hashed = hashlib.sha256(
#                     new_password.encode()).hexdigest()
#                 conn.execute('''
#                     UPDATE users
#                     SET Password = ?
#                     WHERE ID = ?
#                 ''', (new_password_hashed, current_user.id))
#                 conn.commit()

#                 flash("Your password has been updated successfully", 'success')
#                 return redirect(url_for('dashboard'))

#             else:
#                 flash("Incorrect old password", 'error')

#     return render_template('change_password.html')

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
                SELECT * FROM users WHERE ID = ?
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
                SET Password = ?
                WHERE ID = ?
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
            SELECT * FROM users WHERE ID = ?
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
def add_user():
    if current_user.is_admin == 0:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        mobile1 = request.form['mobile1']
        first_name_kh = request.form['first_name_kh']
        last_name_kh = request.form['last_name_kh']
        first_name_en = request.form['first_name_en']
        last_name_en = request.form['last_name_en']
        branch = request.form['branch']
        branch_id = request.form['branch']  # Get the branch ID from the form
        # Checkbox will return '1' if checked, else default to 0
        is_admin = request.form.get('is_admin', 0)
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        # Insert user into 'users' table
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Check if username already exists
            cursor.execute(
                'SELECT * FROM users WHERE UserName = ?', (username,))
            existing_user = cursor.fetchone()

            if existing_user:
                flash('Username already exists. Please choose another one.', 'danger')
                return redirect(url_for('add_user'))

            cursor.execute('''
                INSERT INTO users (UserName, Password, Email, Mobile1, FirstNameKh, LastNameKh, FirstNameEn, LastNameEn, Branch, IsAdmin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (username, hashed_password, email, mobile1, first_name_kh, last_name_kh, first_name_en, last_name_en, branch, is_admin))
            user_id = cursor.lastrowid

            # Insert relationship into 'user_branches' table
            cursor.execute('''
                INSERT INTO user_branches (user_id, branch_id)
                VALUES (?, ?)
            ''', (user_id, branch_id))
            conn.commit()

        return redirect(url_for('list_users'))

    # Fetch all branches for selection
    with get_db_connection() as conn:
        branches = conn.execute('SELECT * FROM branches').fetchall()

    return render_template('/users/add_user.html', branches=branches)


@app.route('/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if current_user.is_admin == 0:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    with get_db_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE ID = ?", (id,)).fetchone()

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        first_name_kh = request.form['first_name_kh']
        last_name_kh = request.form['last_name_kh']
        first_name_en = request.form['first_name_en']
        last_name_en = request.form['last_name_en']
        branch = request.form['branch']
        is_admin = request.form.get('is_admin', 0)
        mobile1 = request.form['mobile1']

        with get_db_connection() as conn:
            conn.execute("""
                UPDATE users SET UserName = ?, Email = ?, FirstNameKh = ?, LastNameKh = ?, FirstNameEn = ?, LastNameEn = ?, Branch = ?, IsAdmin = ?, Mobile1 = ?, UpdatedAt = CURRENT_TIMESTAMP
                WHERE ID = ?""",
                         (username, email, first_name_kh, last_name_kh, first_name_en, last_name_en, branch, is_admin, mobile1, id))
            conn.commit()
        return redirect(url_for('list_users'))

    return render_template('/users/edit_user.html', user=user)


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


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=current_user.username)


# @app.route('/users', methods=['GET'])
# @login_required
# def list_users():
#     if current_user.is_admin == 0:
#         flash("You don't have permission to view this page.", "danger")
#         return redirect(url_for('dashboard'))
#     with get_db_connection() as conn:
#         users = conn.execute("SELECT * FROM users").fetchall()
#     return render_template('/users/users.html', users=users)

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
        last_employee = employees[0] if employees else None
        notifications_employees = [
            {"title": "New Employee Added",
             "message": f"Employee {last_employee['name']} has been added."} if last_employee else None
        ]
    return render_template('/employees/employees.html', employees=employees, notifications_employees=notifications_employees)


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
@login_required
def edit_employee(id):
    with get_db_connection() as conn:
        employee = conn.execute(
            "SELECT * FROM employees WHERE id = ?", (id,)).fetchone()
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
                INSERT INTO branches (Description, Branch, BranchManagerName, ContactNumber, Address,
                                      RegisterDate, LocalDescription, LocalAddress, LocalBranchManagerName)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
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
            SET Status = ?, BranchManagerName = ?, Address = ?, Description = ?, Branch = ?, ContactNumber = ?, UpdatedAt = CURRENT_TIMESTAMP
            WHERE ID = ?''',
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


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
