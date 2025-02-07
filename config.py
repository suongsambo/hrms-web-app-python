import os
from dotenv import load_dotenv

# Load environment variables from a .env file if it exists
load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret_key')
    SESSION_COOKIE_NAME = os.getenv(
        'SESSION_COOKIE_NAME', 'default_session_cookie_name')
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB\
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}
    UPLOAD_FOLDER = 'static/uploads'
    TELEGRAM_BOT_TOKEN = os.getenv(
        'TELEGRAM_BOT_TOKEN', 'your_default_bot_token')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', 'your_default_chat_id')
    DATABASE = os.path.join(os.path.dirname(
        os.path.abspath(__file__)), 'database/hr_management.db')
