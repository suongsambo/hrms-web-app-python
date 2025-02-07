import hashlib
from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from flask import Blueprint
from models import Branch, User
users_bp = Blueprint('users', __name__)


@users_bp.route('/users/add', methods=['GET', 'POST'])
@login_required
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
        is_admin = request.form.get('is_admin', 0)

        # Hash password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        # Check if username already exists
        if User.get_user_by_username(username):
            flash('Username already exists. Please choose another one.', 'danger')
            return redirect(url_for('users.add_user'))

        # Create new user and save to database
        user = User(
            username=username,
            password=hashed_password,
            email=email,
            mobile1=mobile1,
            first_name_kh=first_name_kh,
            last_name_kh=last_name_kh,
            first_name_en=first_name_en,
            last_name_en=last_name_en,
            branch=branch,
            is_admin=is_admin
        )
        user.save()  # Save the new user

        flash('User successfully added.', 'success')
        return redirect(url_for('users.list_users'))

    # Fetch all branches for selection
    branches = Branch.get_all_branches()  # Fetch branches from Branch model
    return render_template('users/add_user.html', branches=branches)

# Route to list all users


@users_bp.route('/users')
@login_required
def list_users():
    if current_user.is_admin == 0:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    users = User.get_all_users()  # Fetch all users
    return render_template('users/users.html', users=users)

# Route to view a user by ID


@users_bp.route('/users/<int:id>')
@login_required
def view_user(id):
    if current_user.is_admin == 0:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    user = User.get_user_by_id(id)  # Fetch user by ID
    if user:
        return render_template('users/view_user.html', user=user)
    flash("User not found", "danger")
    return redirect(url_for('users.list_users'))

# Route to edit user details


@users_bp.route('/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if current_user.is_admin == 0:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    user = User.get_user_by_id(id)
    if not user:
        flash("User not found", "danger")
        return redirect(url_for('users.list_users'))

    if request.method == 'POST':
        user.username = request.form['username']
        user.email = request.form['email']
        user.first_name_kh = request.form['first_name_kh']
        user.last_name_kh = request.form['last_name_kh']
        user.first_name_en = request.form['first_name_en']
        user.last_name_en = request.form['last_name_en']
        user.branch = request.form['branch']
        user.is_admin = request.form.get('is_admin', 0)
        user.mobile1 = request.form['mobile1']

        user.save()  # Save updated user to the database

        flash('User successfully updated.', 'success')
        return redirect(url_for('users.list_users'))

    return render_template('users/edit_user.html', user=user)

# Route to delete a user by ID


@users_bp.route('/users/delete/<int:id>', methods=['POST'])
@login_required
def delete_user(id):
    if current_user.is_admin == 0:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    user = User.get_user_by_id(id)
    if user:
        user.delete()  # Delete the user from the database
        flash('User successfully deleted.', 'success')
    else:
        flash("User not found", "danger")
    return redirect(url_for('users.list_users'))

# Route to search users


@users_bp.route('/users/search', methods=['GET'])
@login_required
def search_users():
    if current_user.is_admin == 0:
        flash("You don't have permission to view this page.", "danger")
        return redirect(url_for('dashboard'))

    query = request.args.get('query', '')

    # Use SQLAlchemy to search users
    users = User.query.filter(User.username.ilike(f"%{query}%")).all()

    return render_template('users/users.html', users=users)
