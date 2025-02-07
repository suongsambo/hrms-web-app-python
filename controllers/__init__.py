from flask import Blueprint
# Import blueprints from individual controller files
from .user_controller import users_bp
# Define a list of blueprints to register in app.py
blueprints = [users_bp]
