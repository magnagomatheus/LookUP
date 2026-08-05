from flaskr.db import get_db


class SavedLocationModel:
    """Data-access layer for the SavedLocation table."""

    @staticmethod
    def get_all_by_user(user_id: int):
        """Return all saved locations for a user, newest first."""
        return get_db().execute(
            'SELECT * FROM SavedLocation WHERE fk_user = ? ORDER BY created_at DESC',
            (user_id,)
        ).fetchall()

    @staticmethod
    def get_by_id_and_user(loc_id: int, user_id: int):
        """Return a single saved location owned by the given user, or None."""
        return get_db().execute(
            'SELECT * FROM SavedLocation WHERE id = ? AND fk_user = ?',
            (loc_id, user_id)
        ).fetchone()

    @staticmethod
    def exists(user_id: int, city: str, state: str, country: str) -> bool:
        """Return True if this user already has a location with the same city/state/country."""
        row = get_db().execute(
            'SELECT id FROM SavedLocation '
            'WHERE fk_user = ? AND city = ? AND state = ? AND country = ?',
            (user_id, city, state, country)
        ).fetchone()
        return row is not None

    @staticmethod
    def create(label: str, country: str, state: str, city: str,
               latitude: str, longitude: str, user_id: int) -> None:
        """Insert a new saved location."""
        db = get_db()
        db.execute(
            'INSERT INTO SavedLocation '
            '(label, country, state, city, latitude, longitude, fk_user) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (label, country, state, city, latitude, longitude, user_id),
        )
        db.commit()

    @staticmethod
    def delete(loc_id: int) -> None:
        """Delete a saved location by id."""
        db = get_db()
        db.execute('DELETE FROM SavedLocation WHERE id = ?', (loc_id,))
        db.commit()
