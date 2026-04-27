import datetime
import sqlite3
import subprocess

DB_NAME = "prodz.db"


def pull_db():
    try:
        subprocess.run(["git", "pull"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        pass


def sync_db():
    try:
        subprocess.run(["git", "add", DB_NAME], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "update"], check=True, capture_output=True)
        subprocess.run(["git", "push"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        pass


def init_db(sync_enabled=False):
    """Initializes the database and creates the table if it doesn't exist."""
    if sync_enabled:
        pull_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            activity TEXT NOT NULL,
            duration_minutes REAL NOT NULL,
            comment TEXT
        )
    """
    )
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN comment TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()
    if sync_enabled:
        sync_db()


def log_session(activity, duration, comment="", sync_enabled=False):
    """Logs a completed work session to the database."""
    if sync_enabled:
        pull_db()
    init_db(sync_enabled=False)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    timestamp_str = now.isoformat()

    cursor.execute(
        """
        INSERT INTO sessions (date, timestamp, activity, duration_minutes, comment)
        VALUES (?, ?, ?, ?, ?)
    """,
        (date_str, timestamp_str, activity, float(duration), comment),
    )

    conn.commit()
    conn.close()
    if sync_enabled:
        sync_db()


def fetch_sessions(limit=None):
    """Returns stored sessions ordered by newest first."""
    init_db(sync_enabled=False)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    query = """
        SELECT id, date, timestamp, activity, duration_minutes, comment
        FROM sessions
        ORDER BY timestamp DESC
    """
    params = ()
    if limit is not None:
        query += " LIMIT ?"
        params = (int(limit),)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return rows
