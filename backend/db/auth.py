import bcrypt

# A missing account still performs bcrypt work with the same default cost.
_DUMMY_HASH = '$2b$12$aXgo0UttwnwrHeTE/MisLOPBhIyqLfwkQmvRw2SA8LYc3w8UDQM2C'

def get_password_hash(password: str) -> str:
    encoded = password.encode('utf-8')
    if not 1 <= len(encoded) <= 72:
        raise ValueError('Password must contain 1–72 UTF-8 bytes')
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode('ascii')

def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    try:
        encoded = plain_password.encode('utf-8')
        if not 1 <= len(encoded) <= 72:
            return False
        candidate = (hashed_password if hashed_password is not None else _DUMMY_HASH).encode('ascii')
        matches = bcrypt.checkpw(encoded, candidate)
        return hashed_password is not None and matches
    except (ValueError, TypeError, AttributeError, UnicodeError):
        return False
