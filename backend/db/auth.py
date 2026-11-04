import bcrypt

def get_password_hash(password: str) -> str:
    encoded = password.encode('utf-8')
    if not 1 <= len(encoded) <= 72:
        raise ValueError('Password must contain 1–72 UTF-8 bytes')
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode('ascii')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        encoded = plain_password.encode('utf-8')
        return 0 < len(encoded) <= 72 and bcrypt.checkpw(encoded, hashed_password.encode('ascii'))
    except (ValueError, TypeError, AttributeError, UnicodeError):
        return False
