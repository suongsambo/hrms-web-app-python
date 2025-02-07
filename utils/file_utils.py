# file_utils.py
import os
from werkzeug.utils import secure_filename


def allowed_file(filename, allowed_extensions):
    """Check if the file has a valid extension."""
    if not filename:
        return False  # No filename provided

    # Split the filename and check if it has an extension
    extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    # Check if the extension is in the allowed list
    return extension in allowed_extensions


def save_file(file, user_id, username, branch, upload_folder):
    """Save the file with a structured filename."""
    filename = f"{user_id}_{username}_{branch}_{secure_filename(file.filename)}"
    file.save(os.path.join(upload_folder, filename))
    return filename


def delete_file(filename, upload_folder):
    """Delete a file from the server."""
    file_path = os.path.join(upload_folder, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return True
    return False
