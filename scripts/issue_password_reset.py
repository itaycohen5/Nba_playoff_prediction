"""Issue a 30-minute reset code after verifying the account owner's identity."""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('username')
    args = parser.parse_args()
    if not os.getenv('DATABASE_URL'):
        parser.error('Set DATABASE_URL explicitly to the intended database')

    from backend.db.database import get_db
    from backend.db.recovery import issue_recovery_code

    session = get_db()
    try:
        db = next(session)
        code = issue_recovery_code(db, args.username.strip())
        db.commit()
    except LookupError as error:
        parser.error(str(error))
    finally:
        session.close()
    print(code)


if __name__ == '__main__':
    main()
