from werkzeug.security import check_password_hash, generate_password_hash
from flaskr.db import get_db


class UserModel:
    """Data-access layer for the User table."""

    @staticmethod
    def get_by_id(user_id: int):
        """Return a User row by primary key, or None."""
        return get_db().execute(
            'SELECT * FROM User WHERE id = ?', (user_id,)
        ).fetchone()

    @staticmethod
    def get_by_email(email: str):
        """Return a User row by e-mail address, or None."""
        return get_db().execute(
            'SELECT * FROM User WHERE email = ?', (email,)
        ).fetchone()

    @staticmethod
    def create(name: str, email: str, password: str) -> None:
        """Insert a new user.  Raises db.IntegrityError on duplicate e-mail."""
        db = get_db()
        db.execute(
            'INSERT INTO User (name, email, password) VALUES (?, ?, ?)',
            (name, email, generate_password_hash(password)),
        )
        db.commit()

    @staticmethod
    def verify_password(user, password: str) -> bool:
        """Return True if *password* matches the stored hash."""
        return check_password_hash(user['password'], password)
