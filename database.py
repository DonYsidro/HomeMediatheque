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


def mettre_a_niveau(conn, schema_sql):
    """Ajoute les colonnes présentes dans schema.sql mais absentes de la base (ajout uniquement)."""
    modele = sqlite3.connect(":memory:")
    modele.executescript(schema_sql)
    tables = [r[0] for r in modele.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    for table in tables:
        existantes = {r[1] for r in conn.execute("PRAGMA table_info(" + table + ")")}
        if not existantes:
            continue  # table absente : elle sera créée par schema.sql
        for cid, nom, type_, notnull, defaut, pk in modele.execute("PRAGMA table_info(" + table + ")"):
            if nom in existantes:
                continue
            if pk or (notnull and defaut is None):
                print("Attention : colonne " + table + "." + nom
                      + " non ajoutée (obligatoire sans valeur par défaut) : à ajouter à la main.")
                continue
            sql = "ALTER TABLE " + table + " ADD COLUMN " + nom + " " + type_
            if defaut is not None and not defaut.upper().startswith("CURRENT_"):
                sql += " DEFAULT " + defaut
            conn.execute(sql)
            print("Colonne ajoutée : " + table + "." + nom)
    modele.close()


def init_db():
    """Met la base à niveau, puis crée les tables manquantes à partir de schema.sql."""
    with open(os.path.join(BASE_DIR, "schema.sql"), "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn = get_db()
    mettre_a_niveau(conn, schema_sql)
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()
    print("Base de données initialisée avec succès (" + DATABASE + ").")


if __name__ == "__main__":
    init_db()
