from flask import Blueprint, render_template, redirect, url_for, request
from models import User
from database import db

users_bp = Blueprint('users', __name__)

@app.route('/')
def index():
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        with get_db_connection() as conn:
            try:
                conn.execute('''
                    INSERT INTO users (UserName, Password, Email)
                    VALUES (?, ?, ?)
                ''', (username, hashed_password, email))
                conn.commit()
                return redirect(url_for('index'))
            except sqlite3.IntegrityError:
                return render_template('username_or_email_exists.html')
                #  "Username or Email already exists. Try again."

    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = hashlib.sha256(request.form['password'].encode()).hexdigest()

    with get_db_connection() as conn:
        user = conn.execute('''
            SELECT * FROM users WHERE UserName = ? AND Password = ?
        ''', (username, password)).fetchone()

    if user:
        session['user'] = username
        return redirect(url_for('dashboard'))
    else:
        return render_template('404.html'), 404

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/users/' , methods=['GET'])
def users():
    with get_db_connection() as conn:
        users = conn.execute("SELECT * FROM users").fetchall()
    return render_template('/users.html', users=users)

@app.route('/users/add', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
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
                INSERT INTO users (UserName, Password, Email, FirstNameKh, LastNameKh, FirstNameEn, LastNameEn, Branch, IsAdmin, Mobile1)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (username, password, email, first_name_kh, last_name_kh, first_name_en, last_name_en, branch, is_admin, mobile1))
            conn.commit()
        return redirect(url_for('list_users'))
    return render_template('/users/add_user.html')

@app.route('/users/edit/<int:id>', methods=['GET', 'POST'])
def edit_user(id):
    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE ID = ?", (id,)).fetchone()
    
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
def delete_user(id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM users WHERE ID = ?", (id,))
        conn.commit()
    return redirect(url_for('list_users'))



@app.route('/users')
def list_users():
    if 'user' not in session:
        return redirect(url_for('index'))

    with get_db_connection() as conn:
        users = conn.execute("SELECT * FROM users").fetchall()

    return render_template('/users/users.html', users=users)

@app.route('/users/<int:id>')
def view_user(id):
    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE ID = ?", (id,)).fetchone()

    if user:
        return render_template('/users/view_user.html', user=user)
    else:
        return "User not found", 404


@app.route('/users/search', methods=['GET'])
def search_users():
    if 'user' not in session:
        return redirect(url_for('index'))

    query = request.args.get('query', '')

    with get_db_connection() as conn:
        users = conn.execute("SELECT * FROM users WHERE UserName LIKE ?", ('%' + query + '%',)).fetchall()

    return render_template('/users/users.html', users=users)
