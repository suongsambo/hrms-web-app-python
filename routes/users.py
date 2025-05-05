# from your_app_name.helpers import allowed_file  # adjust import as needed
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from werkzeug.datastructures import FileStorage
from typing import Union
import hashlib
import sqlite3
from flask import Flask
from config import Config
app = Flask(__name__)

app.config.from_object(Config)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def allowed_file(filename: str) -> bool:
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn


users_bp = Blueprint('users', __name__, url_prefix='/users')


@users_bp.route('/', methods=['GET'])
@login_required
def list_users():
    with get_db_connection() as conn:
        users = conn.execute("SELECT * FROM users").fetchall()
    return render_template('/users/users.html', users=users)


@app.route('/add', methods=['GET', 'POST'])
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


@app.route('/<int:user_id>/signature')
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
@app.route('/<int:user_id>/signature/upload', methods=['GET', 'POST'])
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


@app.route('/<int:user_id>/image')
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


@app.route('/<int:user_id>/image/upload', methods=['GET', 'POST'])
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


@app.route('/profile/<int:user_id>')
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


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
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


@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_user(id):
    if current_user.is_admin == 0:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    with get_db_connection() as conn:
        conn.execute("DELETE FROM users WHERE ID = ?", (id,))
        conn.commit()
    return redirect(url_for('list_users'))
