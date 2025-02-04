from flask import Blueprint

# Import Blueprints from individual route files
from .users import users_bp
from .employees import employees_bp
from .branches import branches_bp

# Optional: If you want a single blueprint for all routes
main_bp = Blueprint('main', __name__)

# Register individual blueprints with the main blueprint
main_bp.register_blueprint(users_bp, url_prefix='/users')
main_bp.register_blueprint(employees_bp, url_prefix='/employees')
main_bp.register_blueprint(branches_bp, url_prefix='/branches')

# This allows `routes` to be imported from app.py without circular issues
__all__ = ['users_bp', 'employees_bp', 'branches_bp']
