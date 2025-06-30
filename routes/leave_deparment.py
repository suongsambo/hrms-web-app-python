import sqlite3
from flask import Blueprint, render_template, redirect, url_for, current_app
from flask_login import current_user, login_required

from config import Config

leaves_bp = Blueprint('leaves', __name__, url_prefix='/leaves')


def get_db_connection():
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


@leaves_bp.route('/department/itd/<string:branch_name>', methods=['GET'])
@login_required
def leaves_by_department_itd(branch_name):
    if current_user.role_default == 700 and current_user.branch and current_user.branch != branch_name:
        return redirect(url_for('filter_leaves_by_branch_name', branch_name=current_user.branch))
    elif current_user.role_default != 700:
        return redirect(url_for('access_denied'))

    current_app.logger.debug(f"Filtering by branch: {branch_name}")

    query = '''
        SELECT
            l.id,
            l.requested_by AS employee_name,
            l.branch AS branch_name,
            l.leave_type,
            l.start_date,
            l.end_date,
            l.reason,
            l.status,
            l.type_of_leave,
            l.verified_by,
            l.approved_by,
            l.leave_hours,
            l.service_count,
            l.requested_by,
            l.requested_by_roles,
            l.requested_from
        FROM leaves l
        LEFT JOIN employees e ON l.employee_id = e.id
        WHERE
            l.branch = ?
            AND l.requested_from = 'ITD'
            AND (
                (
                    l.requested_by_roles = 20 
                    AND l.verified_by IS NULL 
                    AND (l.approved_by IS NULL OR TRIM(l.approved_by) = '')
                    OR l.type_of_leave = 'H'
                )
                OR
                (
                    l.status = 'Pending'
                    AND l.verified_by IS NULL
                    AND (l.approved_by IS NULL OR TRIM(l.approved_by) = '')
                )
            )
        ORDER BY l.start_date DESC;
    '''

    params = (branch_name,)
    try:
        with get_db_connection() as conn:
            leaves = conn.execute(query, params).fetchall()
    except sqlite3.DatabaseError as e:
        current_app.logger.error(f"Database error: {e}")
        return "An error occurred while retrieving data. Please try again later.", 500

    return render_template('leaves/leaves_department_itd.html', leaves=leaves, branch_name=branch_name)
