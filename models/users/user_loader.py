# models/users/user_loader.py
from models.user import User
import sqlite3
from config import Config
from flask import Flask
app = Flask(__name__)
app.config.from_object(Config)


def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn


def load_user(user_id):
    with get_db_connection() as conn:
        user_data = conn.execute(
            'SELECT * FROM users WHERE ID = ?', (user_id,)).fetchone()

        if user_data:
            # Fetch the employee ID associated with the user
            employee = conn.execute(
                'SELECT id FROM employees WHERE user_id = ?', (user_id,)).fetchone()
            employee_id = employee['id'] if employee else None

            department = conn.execute(
                'SELECT department FROM employees WHERE id = ?', (employee_id,)).fetchone()
            department = department['department'] if department else None

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
                department=department,
                zone_id=user_data['ZoneID']
            )
    return None
