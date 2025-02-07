import os
from werkzeug.utils import secure_filename
from flask import current_app

from utils.file_utils import allowed_file


def save_file(file, user_id, username, branch):
    """Save the uploaded file and return the filename."""
    if file and allowed_file(file.filename):  # Ensure file is valid
        filename = f"{user_id}_{username}_{branch}_{secure_filename(file.filename)}"
        # Save file to the upload folder
        file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
        return filename
    return None
