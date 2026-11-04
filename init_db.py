"""Initialize the schema without creating users or preset passwords."""
from backend.db.database import initialize_database


def init():
    initialize_database()
    print("Schema initialized. Create your account using the registration screen.")


if __name__ == "__main__":
    init()
