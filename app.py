from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import hashlib
import os
import glob
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "Suong_Sambo_Admin_System@#$9999_Key546444"
app.config['SESSION_COOKIE_NAME'] = 'Suong_Sambo_Admin_System@#$9999'


# Set the folder for image uploads
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif' , 'doc', 'docx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size



DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database/hr_management.db')
# Initialize the Flask-Login manager
login_manager = LoginManager()
login_manager.init_app(app)

# Setup database connection
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# User class to integrate with Flask-Login
class User(UserMixin):
    def __init__(self, id, username, password, email, branch=None, is_admin=False):
        self.id = id
        self.username = username
        self.password = password
        self.email = email
        self.branch = branch
        self.is_admin = is_admin

# User loader function for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    with get_db_connection() as conn:
        user_data = conn.execute('SELECT * FROM users WHERE ID = ?', (user_id,)).fetchone()
        if user_data:
            return User(id=user_data['ID'], username=user_data['UserName'], password=user_data['Password'], email=user_data['Email'], branch=user_data['Branch'], is_admin=user_data['IsAdmin'])
        return None




def get_db_connection():
    conn = sqlite3.connect(DATABASE)
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
        conn.commit()


@login_manager.unauthorized_handler
def unauthorized():
    return render_template('unauthorized.html'), 401


# Example uploaded_file route for displaying the uploaded image

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/file', methods=['GET', 'POST'])
@login_required
def upload_image():
    if request.method == 'POST':

        if 'file' not in request.files:
            return 'No file part', 400
    
        file = request.files['file']
        
        if file.filename == '':
            return 'No selected file', 400
        
        if file and allowed_file(file.filename):
            filename = f"{current_user.id}_{current_user.username}_{current_user.branch}_{secure_filename(file.filename)}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename)) 
            return redirect(url_for('list_user_files', filename=filename))
    
    return render_template('uploaded_file.html', current_user=current_user)



# # Search File
@app.route('/search_files', methods=['GET'])
@login_required
def search_files():
    query = request.args.get('query', '').lower()

    files = []
    if query:
        # Construct the search pattern
        search_pattern = os.path.join(
            app.config['UPLOAD_FOLDER'],
            f"{current_user.id}_{current_user.username}_{current_user.branch}_{query}*"
        )
        # Use glob to find files matching the pattern
        files = glob.glob(search_pattern)
        # Extract filenames from the full paths
        files = [os.path.basename(file) for file in files]

    return render_template('list_files.html', files=files, query=query, current_user=current_user)


@app.route('/delete_file/<filename>', methods=['POST'])
@login_required
def delete_file(filename):
    # Construct the full path of the file
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    # Check if the file exists
    if os.path.exists(file_path):
        os.remove(file_path)  # Delete the file
        flash('File deleted successfully', 'success')
    else:
        flash('File not found', 'error')
    
    # Redirect to the file listing page
    return redirect(url_for('list_user_files'))

@app.route('/files', methods=['GET'])
@login_required
def list_user_files():
    # Get the directory of the uploaded files
    upload_folder = app.config['UPLOAD_FOLDER']
    
    # Get the user's file prefix based on their ID, username, and branch
    file_prefix = f"{current_user.id}_{current_user.username}_{current_user.branch}"
    
    # List all files in the upload folder
    files = os.listdir(upload_folder)
    
    # Filter the files that match the pattern
    user_files = [file for file in files if file.startswith(file_prefix)]
    
    # Render a template to display the files (or return as a JSON response)
    return render_template('list_files.html', files=user_files, current_user=current_user)




@app.route('/upload_files', methods=['GET', 'POST'])
@login_required
def upload_files():
    if request.method == 'POST':
        if 'files' not in request.files:
            return 'No file part', 400

        files = request.files.getlist('files')
        if not files:
            return 'No selected files', 400

        upload_folder = app.config['UPLOAD_FOLDER']
        file_prefix = f"{current_user.id}_{current_user.username}_{current_user.branch}"

        for file in files:
            if file.filename == '':
                continue
            if file and allowed_file(file.filename):
                filename = f"{file_prefix}_{secure_filename(file.filename)}"
                file.save(os.path.join(upload_folder, filename))

        return redirect(url_for('list_user_files'))

    return render_template('upload_files.html', current_user=current_user)




@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return f'Image uploaded successfully: <img src="/static/uploads/{filename}" alt="uploaded image">'

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        mobile1 = request.form['mobile1']
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        with get_db_connection() as conn:
            try:
                conn.execute('''
                    INSERT INTO users (UserName, Password, Email, Mobile1)
                    VALUES (?, ?, ?, ?)
                ''', (username, hashed_password, email,  mobile1))
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
        user_obj = User(id=user['ID'], username=user['UserName'], password=user['Password'], email=user['Email'])
        login_user(user_obj)  # Store the user session with Flask-Login
        return redirect(url_for('dashboard'))
    
    else:
        return render_template('404.html'), 404

@app.route('/logout', methods=['POST'])
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/users/', methods=['GET'])
@login_required
def users():
    with get_db_connection() as conn:
        users = conn.execute("SELECT * FROM users").fetchall()
    return render_template('/users/users.html', users=users)

# @app.route('/users/add', methods=['GET', 'POST'])
# @login_required
# def add_user():
#     if request.method == 'POST':
#         username = request.form['username']
#         password = hashlib.sha256(request.form['password'].encode()).hexdigest()
#         email = request.form['email']
#         first_name_kh = request.form['first_name_kh']
#         last_name_kh = request.form['last_name_kh']
#         first_name_en = request.form['first_name_en']
#         last_name_en = request.form['last_name_en']
#         branch = request.form['branch']
#         is_admin = request.form.get('is_admin', 0)
#         mobile1 = request.form['mobile1']
#         with get_db_connection() as conn:
#             conn.execute("""
#                 INSERT INTO users (UserName, Password, Email, FirstNameKh, LastNameKh, FirstNameEn, LastNameEn, Branch, IsAdmin, Mobile1)
#                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
#                 (username, password, email, first_name_kh, last_name_kh, first_name_en, last_name_en, branch, is_admin, mobile1))
#             conn.commit()
#         return redirect(url_for('list_users'))
#     return render_template('/users/add_user.html')



# Route to add a new user
# @app.route('/users/add', methods=['GET', 'POST'])
# def add_user():
#     if request.method == 'POST':
#         username = request.form['username']
#         password = request.form['password']
#         email = request.form['email']
#         branches = request.form.getlist('branches')  # Multi-select branches
#         hashed_password = hashlib.sha256(password.encode()).hexdigest()

#         # Insert user into 'users' table
#         with get_db_connection() as conn:
#             cursor = conn.cursor()
#             cursor.execute('''
#                 INSERT INTO users (UserName, Password, Email)
#                 VALUES (?, ?, ?)
#             ''', (username, hashed_password, email))
#             user_id = cursor.lastrowid

#             # Insert relationships into 'user_branches'
#             for branch_id in branches:
#                 cursor.execute('''
#                     INSERT INTO user_branches (user_id, branch_id)
#                     VALUES (?, ?)
#                 ''', (user_id, branch_id))
#             conn.commit()

#         return redirect(url_for('list_users'))
    
#     # Fetch all branches for selection
#     with get_db_connection() as conn:
#         branches = conn.execute('SELECT * FROM branches').fetchall()
#     return render_template('/users/add_user.html')
#     # return render_template('add_user.html', branches=branches)

@app.route('/users/add', methods=['GET', 'POST'])
def add_user():
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
        is_admin = request.form.get('is_admin', 0)  # Checkbox will return '1' if checked, else default to 0
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        # Insert user into 'users' table
        with get_db_connection() as conn:
            cursor = conn.cursor()
                 # Check if username already exists
            cursor.execute('SELECT * FROM users WHERE UserName = ?', (username,))
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
@login_required
def delete_user(id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM users WHERE ID = ?", (id,))
        conn.commit()
    return redirect(url_for('list_users'))



@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=current_user.username)
    
@app.route('/users' , methods=['GET'])
@login_required
def list_users():
    with get_db_connection() as conn:
        users = conn.execute("SELECT * FROM users").fetchall()

    return render_template('/users/users.html', users=users)

@app.route('/users/<int:id>')
@login_required
def view_user(id):
    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE ID = ?", (id,)).fetchone()

    if user:
        return render_template('/users/view_user.html', user=user)
    else:
        return "User not found", 404


@app.route('/users/search', methods=['GET'])
@login_required
def search_users():

    query = request.args.get('query', '')

    with get_db_connection() as conn:
        users = conn.execute("SELECT * FROM users WHERE UserName LIKE ?", ('%' + query + '%',)).fetchall()

    return render_template('/users/users.html', users=users)


@app.route('/employees')
@login_required
def list_employees():
    with get_db_connection() as conn:
        employees = conn.execute("SELECT * FROM employees").fetchall()

    return render_template('/employees/employees.html', employees=employees)

@app.route('/employees/search', methods=['GET'])
@login_required
def search_employees():

    query = request.args.get('query', '')

    with get_db_connection() as conn:
        employees = conn.execute("SELECT * FROM employees WHERE name LIKE ?", ('%' + query + '%',)).fetchall()

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
        employee = conn.execute("SELECT * FROM employees WHERE id = ?", (id,)).fetchone()

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
        employee = conn.execute("SELECT * FROM employees WHERE id = ?", (id,)).fetchone()

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

# Route to add a new branch
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
    branch = conn.execute('SELECT * FROM branches WHERE ID = ?', (id,)).fetchone()

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
        branch = conn.execute("SELECT * FROM branches WHERE ID = ?", (id,)).fetchone()

    if branch:
        return render_template('/branches/view_branch.html', branch=branch)
    else:
        return "Branch not found", 404

@app.route('/branches/search', methods=['GET'])
@login_required
def search_branches():

    query = request.args.get('query', '')

    with get_db_connection() as conn:
        branches = conn.execute("SELECT * FROM branches WHERE Branch LIKE ?", ('%' + query + '%',)).fetchall()

    return render_template('/branches/branches.html', branches=branches)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)