# models.py
from flask_login import UserMixin


class User(UserMixin):
    def __init__(self, id, username, password, email, branch=None, is_admin=False):
        self.id = id
        self.username = username
        self.password = password
        self.email = email
        self.branch = branch
        self.is_admin = is_admin
