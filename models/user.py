# models/user.py
from flask_login import UserMixin
from typing import Optional


class User(UserMixin):
    def __init__(self, id: int, username: str, password: str, email: str,
                 branch: Optional[str] = None, employee_id: Optional[int] = None, is_admin: bool = False,
                 role_default: Optional[int] = 0, image_data: Optional[bytes] = None,
                 zone_id: Optional[int] = None, department: Optional[str] = None):
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
        self.department = department

    def get_id(self):
        """Override get_id method to work with Flask-Login."""
        return str(self.id)

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"
