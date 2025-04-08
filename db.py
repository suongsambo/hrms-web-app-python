import sqlite3
import hashlib
from flask import Flask
from config import Config
app = Flask(__name__)
app.config.from_object(Config)


def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database and create tables if they don't exist."""
    with get_db_connection() as conn:
        # Create users table
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
                RoleDefault INTEGER DEFAULT 0,
                AcceptedTerms INTEGER DEFAULT 0,
                ImageUrl TEXT,
                Image BLOB,
                Signature BLOB DEFAULT NULL,
                FingerPrint BLOB DEFAULT NULL,
                ZoneID INTEGER,
                FOREIGN KEY (ZoneID) REFERENCES zones(ID) ON DELETE SET NULL
            )
        ''')

        # Create employees table with foreign key to position
        conn.execute('''
             CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER NOT NULL CHECK(age >= 18 AND age <= 100),
                department TEXT NOT NULL,
                salary REAL NOT NULL CHECK(salary > 0),
                position_id INTEGER,  -- Reference to the position table
                joining_date TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT CHECK(status IN ('Active', 'Inactive', 'On Leave')) DEFAULT 'Active',
                branch TEXT,  -- Branch of the employee
                user_id INTEGER,  -- Reference to the user table
                phone_number TEXT,  -- Contact number of the employee
                email TEXT UNIQUE,  -- Email address of the employee
                address TEXT,  -- Employee address
                emergency_contact_name TEXT,
                emergency_contact_phone TEXT,
                employees_height DECIMAL(5, 2) NULL,  -- Optional field
                ethnicity TEXT NULL,                   -- Optional field
                nationality TEXT NULL,                 -- Optional field
                religion TEXT NULL,                    -- Optional field
                family_status TEXT CHECK(family_status IN ('single', 'married', 'other')) NULL, -- Optional field
                place_of_birth TEXT NULL,              -- Optional field
                permanent_address TEXT NULL,           -- Optional field
                village TEXT NULL,                     -- Optional field
                commune TEXT NULL,                     -- Optional field
                district TEXT NULL,                    -- Optional field
                province TEXT NULL,                    -- Optional field
                home_number TEXT NULL,                 -- Optional field
                street_number TEXT NULL,               -- Optional field
                group_name TEXT NULL,                  -- Optional field
                personal_phone_number TEXT NULL,       -- Optional field
                level_of_culture TEXT CHECK(level_of_culture IN ('diploma_degree', 'bachelor_degree', 'master_degree', 'doctor')) NULL,  -- Optional field
                skill TEXT NULL,                       -- Optional field
                name_of_educational_institution TEXT NULL, -- Optional field
                knowledge_of_foreign_languages TEXT NULL, -- Optional field
                current_function TEXT NULL,            -- Optional field
                id_card_number TEXT NULL,              -- Optional field
                work_at TEXT NULL,                     -- Optional field
                employment_id TEXT NULL,               -- Optional field
                employment_date TEXT NULL,             -- Optional field
                khmer_nationality_identity_card TEXT NULL, -- Optional field
                passing_test_date TEXT NULL,           -- Optional field
                residence_book_or_family_book TEXT NULL, -- Optional field
                made_on TEXT NULL,                     -- Optional field
                have_a_number_of_children INTEGER NULL,  -- Optional field
                father_name TEXT NULL,                 -- Optional field
                mother_name TEXT NULL,                 -- Optional field
                father_status TEXT CHECK(father_status IN ('dead', 'alive')) NULL,  -- Optional field
                father_occupation TEXT NULL,           -- Optional field
                mother_occupation TEXT NULL,           -- Optional field
                mother_status TEXT CHECK(mother_status IN ('dead', 'alive')) NULL, -- Optional field
                father_permanent_address TEXT NULL,    -- Optional field
                mother_permanent_address TEXT NULL,    -- Optional field
                parents_village TEXT NULL,             -- Optional field
                parents_commune TEXT NULL,             -- Optional field
                parents_district TEXT NULL,            -- Optional field
                parents_province TEXT NULL,            -- Optional field
                parents_home_number TEXT NULL,         -- Optional field
                parents_street_number TEXT NULL,       -- Optional field
                parents_group TEXT NULL,               -- Optional field
                parents_phone TEXT NULL,               -- Optional field
                photo BLOB NULL,                       -- Optional field
                fingerprints BLOB NULL,
                signature BLOB NULL,
                FOREIGN KEY (user_id) REFERENCES users(ID),
                FOREIGN KEY (position_id) REFERENCES positions(ID)
            )
        ''')

        # Create payroll table for employee payments
        conn.execute('''
            CREATE TABLE IF NOT EXISTS payroll (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                period_start_date TEXT NOT NULL,
                period_end_date TEXT NOT NULL,
                base_salary REAL NOT NULL,
                bonus REAL DEFAULT 0,
                deductions REAL DEFAULT 0,
                tax REAL DEFAULT 0,
                total_salary REAL NOT NULL,
                payment_date TEXT DEFAULT CURRENT_DATE,
                FOREIGN KEY (employee_id) REFERENCES employees (id)
            )
        ''')

        # Create branches table
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

        # Create zones table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS zones (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT NOT NULL,
                Description TEXT
            )
        ''')

        # Create zone_branch table (many-to-many relationship)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS zone_branch (
                zone_id INTEGER,
                branch_id INTEGER,
                PRIMARY KEY (zone_id, branch_id),
                FOREIGN KEY (zone_id) REFERENCES zones(ID) ON DELETE CASCADE,
                FOREIGN KEY (branch_id) REFERENCES branches(ID) ON DELETE CASCADE
            )
        ''')

        # Create roles table to manage user roles and related info
        conn.execute('''
            CREATE TABLE IF NOT EXISTS roles (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                UserID INTEGER NOT NULL,
                Role TEXT NOT NULL,
                RoleNumber INTEGER NOT NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                Status TEXT CHECK(Status IN ('Active', 'Inactive')) DEFAULT 'Active',
                Description TEXT,
                FOREIGN KEY (UserID) REFERENCES users(ID) ON DELETE CASCADE
            )
        ''')

        # Create user_branches table (many-to-many relationship between users and branches)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_branches (
                user_id INTEGER,
                branch_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (ID) ON DELETE CASCADE,
                FOREIGN KEY (branch_id) REFERENCES branches (ID) ON DELETE CASCADE,
                PRIMARY KEY (user_id, branch_id)
            )
        ''')

        # Create login_logs table
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

        # Create online_users table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS online_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (ID)
            )
        ''')

        # Create attendance table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS Attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT NOT NULL,
                date TEXT NOT NULL DEFAULT CURRENT_DATE,
                status TEXT NOT NULL,
                checkin_time TEXT,
                checkout_time TEXT,
                total_hours REAL DEFAULT 0,
                workday_count REAL DEFAULT 0
            )
        ''')

        # Create role table on user
        conn.execute('''
            CREATE TABLE IF NOT EXISTS role (
                UserID INTEGER NOT NULL,
                UserRoleID INTEGER NOT NULL,
                PRIMARY KEY (UserID, UserRoleID),
                FOREIGN KEY (UserID) REFERENCES users (ID) ON DELETE CASCADE,
                FOREIGN KEY (UserRoleID) REFERENCES roles (ID) ON DELETE CASCADE
            )
        ''')

        # Create messages table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create departments table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS departments (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT NOT NULL,
                Description TEXT,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create positions table with a foreign key reference to departments
        conn.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                PositionName TEXT NOT NULL UNIQUE,  -- Name of the position (e.g., Manager, Developer)
                Description TEXT,  -- Description of the position
                department_id INTEGER,  -- Reference to the departments table
                FOREIGN KEY (department_id) REFERENCES departments(ID)  -- Foreign key to departments
            )
        ''')

        # Create leave table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS leaves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                leave_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                reason TEXT NOT NULL,
                start_date_obj DATE,
                end_date_obj DATE,
                service_count INTEGER,
                leave_hours REAL,
                requested_by TEXT,
                verified_by TEXT,
                approved_by TEXT,
                type_of_leave TEXT,
                status TEXT DEFAULT 'Pending',
                spm_status TEXT DEFAULT 'Pending',
                dd_status TEXT DEFAULT 'Pending',
                manager_status TEXT DEFAULT 'Pending',
                branch TEXT,
                category TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees(ID) ON DELETE CASCADE
            )
        ''')

        # Create the association table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_leave (
                user_id INTEGER NOT NULL,
                leave_id INTEGER NOT NULL,
                PRIMARY KEY (user_id, leave_id),
                FOREIGN KEY (user_id) REFERENCES users(ID) ON DELETE CASCADE,
                FOREIGN KEY (leave_id) REFERENCES leaves(id) ON DELETE CASCADE
            )
        ''')

        # Create bankstatement table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS bankstatement (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                employee_id INTEGER NOT NULL,
                employee_name TEXT NOT NULL,
                account_name TEXT NOT NULL,
                account_number TEXT NOT NULL,
                bank_name TEXT NOT NULL,
                salary REAL NOT NULL,
                transaction_date DATE NOT NULL,
                transaction_type TEXT CHECK(transaction_type IN ('Credit', 'Debit')) NOT NULL,
                FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
            )
        ''')

        # Create Message table
        conn.execute('''
          CREATE TABLE IF NOT EXISTS Message (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create location table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS location (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                street TEXT,
                city TEXT,
                province TEXT,
                country TEXT,
                postal_code TEXT
            )
        ''')

        # Check if zone 'All' exists
        zone_exists = conn.execute(
            "SELECT 1 FROM zones WHERE name = 'All'").fetchone()

        if not zone_exists:
            conn.execute('''
                INSERT INTO zones (name)
                VALUES ('All')
            ''')

        # Check if the user 'bo' exists
        user_exists = conn.execute(
            "SELECT 1 FROM users WHERE UserName = 'bo'").fetchone()

        if not user_exists:

            hashed_password = hashlib.sha256('1111'.encode()).hexdigest()

            conn.execute('''
                INSERT INTO users (UserName, Password, Email, Mobile1, IsAdmin, Branch)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('bo', hashed_password, 'bo@example.com', '1234567890', 1, 'SYS'))

        # Create John Doe user
        user_exists = conn.execute(
            "SELECT 1 FROM users WHERE UserName = 'doe'").fetchone()
        if not user_exists:
            hashed_password = hashlib.sha256('1111'.encode()).hexdigest()
            conn.execute('''
                INSERT INTO users (UserName, Password, Email, Mobile1, IsAdmin, RoleDefault, Branch)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('doe', hashed_password, 'john_doe@example.com', '010655037', 0, 20, 'SYS'))

        user_exists = conn.execute(
            "SELECT 1 FROM users WHERE UserName = 'son'").fetchone()

        # Create John Doe user
        user_exists = conn.execute(
            "SELECT 1 FROM users WHERE UserName = 'hqs'").fetchone()
        if not user_exists:
            hashed_password = hashlib.sha256('1111'.encode()).hexdigest()
            conn.execute('''
                INSERT INTO users (UserName, Password, Email, Mobile1, IsAdmin, RoleDefault, Branch)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('hqs', hashed_password, 'hqs@example.com', '010655037', 0, 20, 'HQ'))

        user_exists = conn.execute(
            "SELECT 1 FROM users WHERE UserName = 'son'").fetchone()

        if not user_exists:

            hashed_password = hashlib.sha256('1111'.encode()).hexdigest()

            conn.execute('''
                INSERT INTO users (UserName, Password, Email, Mobile1, IsAdmin, RoleDefault, Branch)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('son', hashed_password, 'son@example.com', '010655037', 0, 20, 'SYS'))

        # Create John Doe user
        user_exists = conn.execute(
            "SELECT 1 FROM users WHERE UserName = 'pm'").fetchone()

        if not user_exists:

            hashed_password = hashlib.sha256('1111'.encode()).hexdigest()

            conn.execute('''
                INSERT INTO users (UserName, Password, Email, Mobile1, IsAdmin, RoleDefault, Branch)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('pm', hashed_password, 'pm@example.com', '010655037', 0, 140, 'SYS'))

        # Create SQM user
        user_exists = conn.execute(
            "SELECT 1 FROM users WHERE UserName = 'spm'").fetchone()

        if not user_exists:

            hashed_password = hashlib.sha256('1111'.encode()).hexdigest()

            conn.execute('''
                INSERT INTO users (UserName, Password, Email, Mobile1, IsAdmin, RoleDefault, Branch)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('spm', hashed_password, 'spm@example.com', '010655037', 0, 145, 'SYS'))

      # Create DC user
        user_exists = conn.execute(
            "SELECT 1 FROM users WHERE UserName = 'dgm'").fetchone()

        if not user_exists:

            hashed_password = hashlib.sha256('1111'.encode()).hexdigest()

            conn.execute('''
                INSERT INTO users (UserName, Password, Email, Mobile1, IsAdmin, RoleDefault, Branch)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('dgm', hashed_password, 'dgm@example.com', '010655037', 0, 175, 'SYS'))

        # Create gm user
        user_exists = conn.execute(
            "SELECT 1 FROM users WHERE UserName = 'gm'").fetchone()

        if not user_exists:

            hashed_password = hashlib.sha256('1111'.encode()).hexdigest()

            conn.execute('''
                INSERT INTO users (UserName, Password, Email, Mobile1, IsAdmin, RoleDefault, Branch)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('gm', hashed_password, 'gm@example.com', '010655037', 0, 180, 'SYS'))

        # Create CCA user
        user_exists = conn.execute(
            "SELECT 1 FROM users WHERE UserName = 'ccc'").fetchone()

        if not user_exists:

            hashed_password = hashlib.sha256('1111'.encode()).hexdigest()

            conn.execute('''
                INSERT INTO users (UserName, Password, Email, Mobile1, IsAdmin, RoleDefault, Branch)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('ccc', hashed_password, 'ccc@example.com', '010655037', 0, 35, 'SYS'))

        # Create CS user
        user_exists = conn.execute(
            "SELECT 1 FROM users WHERE UserName = 'cs'").fetchone()

        if not user_exists:

            hashed_password = hashlib.sha256('1111'.encode()).hexdigest()
            conn.execute('''
                INSERT INTO users (UserName, Password, Email, Mobile1, IsAdmin, RoleDefault, Branch)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('cs', hashed_password, 'cs@example.com', '010655037', 0, 165, 'SYS'))

        # Create Project Consultant user
        user_exists = conn.execute(
            "SELECT 1 FROM users WHERE UserName = 'hd'").fetchone()

        if not user_exists:
            hashed_password = hashlib.sha256('1111'.encode()).hexdigest()
            conn.execute('''
                INSERT INTO users (UserName, Password, Email, Mobile1, IsAdmin, RoleDefault, Branch)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('hd', hashed_password, 'hd@example.com', '010655037', 0, 170, 'SYS'))

        # Create HRC user
        user_exists = conn.execute(
            "SELECT 1 FROM users WHERE UserName = 'hrd'").fetchone()

        if not user_exists:
            hashed_password = hashlib.sha256('1111'.encode()).hexdigest()
            conn.execute('''
                INSERT INTO users (UserName, Password, Email, Mobile1, IsAdmin, RoleDefault, Branch)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('hrd', hashed_password, 'hrd@example.com', '010655037', 0, 160, 'SYS'))

        # Create CB user
        user_exists = conn.execute(
            "SELECT 1 FROM users WHERE UserName = 'cb'").fetchone()

        if not user_exists:
            hashed_password = hashlib.sha256('1111'.encode()).hexdigest()
            conn.execute('''
                INSERT INTO users (UserName, Password, Email, Mobile1, IsAdmin, RoleDefault, Branch)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('cb', hashed_password, 'cb@example.com', '010655037', 0, 190, 'SYS'))

        # Create IT user
        departments = [
            ("HRD", "Human Resources Department"),
            ("CRD", "Credit Department"),
            ("OPD", "Operations Department"),
            ("FND", "Finance Department"),
            ("TRD", "Training Department"),
            ("ITD", "Information Technology Department")
        ]

        # Loop through each department
        for department_name, description in departments:
            # Check if the department already exists
            department_exists = conn.execute(
                "SELECT 1 FROM departments WHERE Name = ?", (department_name,)).fetchone()

            # If the department doesn't exist, insert it
            if not department_exists:
                conn.execute('''
                    INSERT INTO departments (Name, Description)
                    VALUES (?, ?)
                ''', (department_name, description))
                print(f'Department {department_name} added successfully!')

        # Check if the 'HR Manager' position already exists
        position_exists = conn.execute(
            "SELECT 1 FROM positions WHERE PositionName = 'HR Manager'").fetchone()

        if not position_exists:

            department_id = conn.execute(
                "SELECT ID FROM departments WHERE Name = 'HRD'").fetchone()[0]

            conn.execute('''
                INSERT INTO positions (PositionName, Description, department_id)
                VALUES (?, ?, ?)
            ''', ('HR Manager', 'Responsible for managing human resources', department_id))

        branch_exists = conn.execute(
            "SELECT 1 FROM branches WHERE Branch = 'SYS'").fetchone()
        if not branch_exists:
            conn.execute('''
                INSERT INTO branches (Branch, Status, CreateDate, StartDate, Description, BranchManagerName, ContactNumber,
                                      Address, DistrictProvince, RegisterDate, LocalDescription, LocalAddress,
                                      LocalBranchManagerName, BranchProjectId, CapitalInjectionId, GroupID, MemberID)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', ('SYS', 'Active', '2025-02-28', '2025-02-28', 'System Default Branch', 'John Doe', '1234567890',
                  '1234 Main Street', 'Some District, Some Province', '2025-02-28', 'Default Local Description',
                  'Local Address Example', 'Jane Smith', 'Project123', 'Capital123', 'Group123', 'Member123'))

        branch_exists = conn.execute(
            "SELECT 1 FROM branches WHERE Branch = 'HQ'").fetchone()
        if not branch_exists:
            conn.execute('''
                INSERT INTO branches (Branch, Status, CreateDate, StartDate, Description, BranchManagerName, ContactNumber,
                                      Address, DistrictProvince, RegisterDate, LocalDescription, LocalAddress,
                                      LocalBranchManagerName, BranchProjectId, CapitalInjectionId, GroupID, MemberID)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', ('HQ', 'Active', '2025-02-28', '2025-02-28', 'System Default Branch', 'John Doe', '1234567890',
                  '1234 Main Street', 'Some District, Some Province', '2025-02-28', 'Default Local Description',
                  'Local Address Example', 'Jane Smith', 'Project123', 'Capital123', 'Group123', 'Member123'))

        # List of all branch values to insert
        branches = [
            "HQ", "AKC", "BSD", "BVL", "CHK", "CHP", "KPT", "KTR", "PKB", "PRN",
            "SNG", "TTG", "TTY", "BTB", "CBA", "DKR", "PNH", "KKD", "KTL", "PMR",
            "PPN", "PSC", "SAN", "KPS", "SAT", "SST", "SVR", "KPCA", "SUB", "SAB",
            "BTI", "KMP", "KAD", "MCH"
        ]

        # Loop through each branch in the list
        for branch in branches:
            branch_exists = conn.execute(
                "SELECT 1 FROM branches WHERE Branch = ?", (branch,)).fetchone()

            # If the branch doesn't exist, insert it
            if not branch_exists:
                conn.execute('''
                    INSERT INTO branches (Branch, Status, CreateDate, StartDate, Description, BranchManagerName, ContactNumber,
                                        Address, DistrictProvince, RegisterDate, LocalDescription, LocalAddress,
                                        LocalBranchManagerName, BranchProjectId, CapitalInjectionId, GroupID, MemberID)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    branch, 'Active', '2025-02-28', '2025-02-28', 'System Default Branch', 'John Doe', '1234567890',
                    '1234 Main Street', 'Some District, Some Province', '2025-02-28', 'Default Local Description',
                    'Local Address Example', 'Jane Smith', 'Project123', 'Capital123', 'Group123', 'Member123'
                ))
                print(f'Branch {branch} added successfully!')

        employee_exists = conn.execute(
            "SELECT 1 FROM employees WHERE email = 'john@example.com'").fetchone()

        if not employee_exists:
            conn.execute('''
                INSERT INTO employees (
                    name, age, department, salary, position_id, branch, user_id, phone_number, email,
                    joining_date, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                'John Doe',
                30,
                'HR',
                1000,
                1,
                'SYS',
                2,
                '010655037',
                'john@example.com',
                '2025-02-28',
                'Active'
            ))

        employee_exists = conn.execute(
            "SELECT 1 FROM employees WHERE email = 'john@example.com'").fetchone()

        if not employee_exists:
            conn.execute('''
                INSERT INTO employees (
                    name, age, department, salary, position_id, branch, user_id, phone_number, email,
                    joining_date, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                'John Doe',
                30,
                'HR',
                1000,
                1,
                'SYS',
                2,
                '010655037',
                'john@example.com',
                '2025-02-28',
                'Active'
            ))

        employee_exists = conn.execute(
            "SELECT 1 FROM employees WHERE email = 'kimminson@example.com'").fetchone()

        if not employee_exists:
            conn.execute('''
                INSERT INTO employees (
                    name, age, department, salary, position_id, branch, user_id, phone_number, email,
                    joining_date, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                'Kimmin Son',
                30,
                'HR',
                1000,
                1,
                'SYS',
                4,
                '010655037',
                'kimminson@example.com',
                '2025-02-28',
                'Active'
            ))

        employee_exists = conn.execute(
            "SELECT 1 FROM employees WHERE email = 'hqs@example.com'").fetchone()

        if not employee_exists:
            conn.execute('''
                INSERT INTO employees (
                    name, age, department, salary, position_id, branch, user_id, phone_number, email,
                    joining_date, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                'HQ Staff',
                30,
                'HR',
                1000,
                1,
                'HQ',
                3,
                '010655037',
                'hqs@example.com',
                '2025-02-28',
                'Active'
            ))

    conn.commit()
    conn.close()
