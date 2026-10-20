import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "data", "mediatheque.db"))


def get_db():
    """Ouvre une connexion à la base, en autorisant l'accès aux colonnes par leur nom."""
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # active les contraintes REFERENCES/CASCADE
    return conn


def init_db():
    """Crée les tables à partir de schema.sql si elles n'existent pas encore."""
    conn = get_db()
    with open(os.path.join(BASE_DIR, "schema.sql"), "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print("Base de données initialisée avec succès (" + DATABASE + ").")


if __name__ == "__main__":
    init_db()
