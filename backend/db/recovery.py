"""Password recovery codes are separate from login cookies."""
import hashlib
import secrets
from datetime import timedelta

from backend.db.models import AuthSession, User, utcnow


def recovery_key(code):
    # A login session digest is always hexadecimal, so it cannot match this key.
    return 'reset:' + hashlib.sha256(code.encode('ascii')).hexdigest()[:58]


def issue_recovery_code(db, username):
    user = db.query(User).filter_by(username=username).with_for_update().first()
    if user is None:
        raise LookupError('Account not found')
    db.query(AuthSession).filter(
        AuthSession.user_id == user.id, AuthSession.token_hash.startswith('reset:')
    ).delete(synchronize_session=False)
    code = secrets.token_urlsafe(32)
    db.add(AuthSession(token_hash=recovery_key(code), user_id=user.id,
                       expires_at=utcnow() + timedelta(minutes=30)))
    return code
