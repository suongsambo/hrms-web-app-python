# limiter_config.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def custom_key():
    from flask import request
    return request.headers.get("X-API-KEY") or get_remote_address()


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
