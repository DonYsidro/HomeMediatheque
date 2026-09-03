import sqlite3

DATABASE = "mediatheque.db"

def get_db():
    """Ouvre une connexion à la base, en autorisant l'accès aux colonnes par leur nom."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # active les contraintes REFERENCES/CASCADE
    return conn

def init_db():
    """Crée les tables à partir de schema.sql si elles n'existent pas encore."""
    conn = get_db()
    with open("schema.sql", "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print("Base de données initialisée avec succès.")

if __name__ == "__main__":
    init_db()
