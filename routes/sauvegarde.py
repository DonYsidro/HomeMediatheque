
import csv
import io
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile

from datetime import datetime
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    send_file,
    current_app,
)
from admin_security import admin_requis
from database import get_db


sauvegarde_bp = Blueprint("sauvegarde", __name__, url_prefix="/sauvegarde")

TABLES_SAUVEGARDE = [
    "genres",
    "personnes",
    "medias",
    "medias_genres",
    "medias_personnes",
    "cds",
    "livres",
    "bd_mangas",
]

MAX_TAILLE_ARCHIVE = 100 * 1024 * 1024
MAX_TAILLE_DECOMPRESSEE = 300 * 1024 * 1024
MAX_NOMBRE_FICHIERS = 1000

DOSSIER_UPLOADS = os.path.join("static", "uploads")


def valider_archive_sauvegarde(zf):
    """Valide les chemins, le nombre de fichiers et les tailles du ZIP."""
    noms_vus = set()
    taille_totale = 0
    data_json_present = False

    membres = zf.infolist()

    if len(membres) > MAX_NOMBRE_FICHIERS:
        raise ValueError("Archive contenant trop de fichiers.")

    for membre in membres:
        nom = membre.filename

        if (
            not nom
            or nom.startswith(("/", "\\"))
            or "\\" in nom
            or "\x00" in nom
            or any(part in (".", "..") for part in nom.split("/"))
        ):
            raise ValueError("Chemin interdit dans l'archive.")

        if nom in noms_vus:
            raise ValueError("Entrée en double dans l'archive.")
        noms_vus.add(nom)

        if membre.flag_bits & 0x1:
            raise ValueError("Les archives chiffrées sont refusées.")

        # Refuse les liens symboliques et les types de fichiers spéciaux.
        type_unix = (membre.external_attr >> 16) & 0o170000
        if type_unix not in (0, 0o100000, 0o040000):
            raise ValueError("Type de fichier interdit dans l'archive.")

        if membre.is_dir():
            continue

        taille_totale += membre.file_size
        if taille_totale > MAX_TAILLE_DECOMPRESSEE:
            raise ValueError("Archive trop volumineuse après décompression.")

        if nom == "data.json":
            data_json_present = True
        elif nom.startswith("uploads/"):
            nom_fichier = nom[len("uploads/"):]
            if (
                not nom_fichier
                or "/" in nom_fichier
                or nom_fichier in (".", "..")
            ):
                raise ValueError("Chemin d'upload interdit.")
        else:
            raise ValueError("Fichier inattendu dans l'archive.")

    if not data_json_present:
        raise ValueError("Le fichier data.json est absent.")


def lire_et_valider_json(zf, colonnes_autorisees):
    """Lit le JSON et vérifie sa structure et les colonnes."""
    with zf.open("data.json") as fichier:
        data = json.load(fichier)

    if not isinstance(data, dict):
        raise ValueError("Structure JSON invalide.")

    if set(data) != set(TABLES_SAUVEGARDE):
        raise ValueError(
            "La sauvegarde est incomplète ou contient des tables inconnues."
        )

    for table, lignes in data.items():
        if not isinstance(lignes, list):
            raise ValueError(f"Liste invalide pour la table {table}.")

        for ligne in lignes:
            if not isinstance(ligne, dict) or not ligne:
                raise ValueError(f"Enregistrement invalide dans {table}.")

            if not set(ligne).issubset(colonnes_autorisees[table]):
                raise ValueError(f"Colonne inconnue dans la table {table}.")

    return data


def obtenir_colonnes(conn):
    """Retourne les colonnes autorisées pour chaque table."""
    resultat = {}

    for table in TABLES_SAUVEGARDE:
        infos = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        resultat[table] = {info["name"] for info in infos}

        if not resultat[table]:
            raise ValueError(f"Table absente ou inconnue : {table}")

    return resultat


def restaurer_fichiers_et_base(conn, data, zf):
    """Restaure la base et les fichiers en limitant les modifications partielles."""
    os.makedirs(DOSSIER_UPLOADS, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="mediatheque-import-") as temporaire:
        staging = os.path.join(temporaire, "staging")
        sauvegarde_fichiers = os.path.join(temporaire, "anciens")
        os.makedirs(staging)
        os.makedirs(sauvegarde_fichiers)

        # Décompresse les fichiers dans un espace temporaire, jamais directement
        # dans le dossier des uploads.
        taille_lue = 0

        for membre in zf.infolist():
            nom = membre.filename

            if not nom.startswith("uploads/") or membre.is_dir():
                continue

            nom_fichier = nom[len("uploads/"):]
            destination_temp = os.path.join(staging, nom_fichier)

            with zf.open(membre) as source, open(destination_temp, "wb") as dest:
                while True:
                    morceau = source.read(64 * 1024)
                    if not morceau:
                        break

                    taille_lue += len(morceau)
                    if taille_lue > MAX_TAILLE_DECOMPRESSEE:
                        raise ValueError("Taille réelle des fichiers excessive.")

                    dest.write(morceau)

        fichiers_remplaces = []
        nouveaux_fichiers = []
        transaction_demarree = False

        try:
            # La désactivation doit précéder le début de la transaction.
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("BEGIN")
            transaction_demarree = True

            ordre_suppression = [
                "medias_genres",
                "medias_personnes",
                "medias",
                "genres",
                "personnes",
                "cds",
                "livres",
                "bd_mangas",
            ]

            for table in ordre_suppression:
                conn.execute(f'DELETE FROM "{table}"')

            for table in TABLES_SAUVEGARDE:
                for ligne in data.get(table, []):
                    colonnes = list(ligne.keys())
                    noms_sql = ", ".join(f'"{col}"' for col in colonnes)
                    marqueurs = ", ".join("?" for _ in colonnes)
                    valeurs = [ligne[col] for col in colonnes]

                    conn.execute(
                        f'INSERT INTO "{table}" ({noms_sql}) VALUES ({marqueurs})',
                        valeurs,
                    )

            violation = conn.execute("PRAGMA foreign_key_check").fetchone()
            if violation:
                raise ValueError("La sauvegarde contient des relations invalides.")

            # Les fichiers ne sont remplacés qu'après validation de la base.
            for nom_fichier in os.listdir(staging):
                source = os.path.join(staging, nom_fichier)
                destination = os.path.join(DOSSIER_UPLOADS, nom_fichier)

                if os.path.exists(destination):
                    ancien = os.path.join(sauvegarde_fichiers, nom_fichier)
                    shutil.copy2(destination, ancien)
                    fichiers_remplaces.append((ancien, destination))
                else:
                    nouveaux_fichiers.append(destination)

                shutil.copy2(source, destination)

            conn.commit()
            transaction_demarree = False

        except Exception:
            if transaction_demarree:
                conn.rollback()

            # Supprime les nouveaux fichiers installés par cet import.
            for chemin in nouveaux_fichiers:
                if os.path.exists(chemin):
                    os.remove(chemin)

            # Restaure les versions précédentes des fichiers écrasés.
            for ancien, destination in reversed(fichiers_remplaces):
                if os.path.exists(ancien):
                    shutil.copy2(ancien, destination)
                elif os.path.exists(destination):
                    os.remove(destination)

            raise

        finally:
            conn.execute("PRAGMA foreign_keys = ON")


@sauvegarde_bp.route("")
@admin_requis
def sauvegarde_page():
    return render_template("sauvegarde.html")


@sauvegarde_bp.route("/export.json")
@admin_requis
def export_json():
    conn = get_db()

    try:
        data = {}

        for table in TABLES_SAUVEGARDE:
            rows = conn.execute(f'SELECT * FROM "{table}"').fetchall()
            data[table] = [dict(row) for row in rows]

    finally:
        conn.close()

    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "data.json",
            json.dumps(data, ensure_ascii=False, indent=2),
        )

        if os.path.isdir(DOSSIER_UPLOADS):
            for nom_fichier in os.listdir(DOSSIER_UPLOADS):
                chemin = os.path.join(DOSSIER_UPLOADS, nom_fichier)

                if os.path.isfile(chemin):
                    zf.write(chemin, arcname=f"uploads/{nom_fichier}")

    buffer.seek(0)
    date_str = datetime.now().strftime("%Y-%m-%d")

    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"mediatheque-sauvegarde-{date_str}.zip",
    )


@sauvegarde_bp.route("/export.csv")
@admin_requis
def export_csv():
    conn = get_db()

    try:
        buffer = io.BytesIO()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for table in TABLES_SAUVEGARDE:
                rows = conn.execute(f'SELECT * FROM "{table}"').fetchall()

                if not rows:
                    continue

                csv_buffer = io.StringIO()
                writer = csv.DictWriter(
                    csv_buffer,
                    fieldnames=rows[0].keys(),
                )
                writer.writeheader()

                for row in rows:
                    writer.writerow(dict(row))

                zf.writestr(f"{table}.csv", csv_buffer.getvalue())

    finally:
        conn.close()

    buffer.seek(0)
    date_str = datetime.now().strftime("%Y-%m-%d")

    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"mediatheque-export-csv-{date_str}.zip",
    )


@sauvegarde_bp.route("/importer", methods=["POST"])
@admin_requis
def importer_sauvegarde():
    fichier = request.files.get("fichier_sauvegarde")

    if not fichier or not fichier.filename.lower().endswith(".zip"):
        return redirect(url_for(".sauvegarde_page"))

    if (
        request.content_length is not None
        and request.content_length > MAX_TAILLE_ARCHIVE
    ):
        return "Archive trop volumineuse (limite de 100 Mio).", 413

    conn = None

    try:
        with zipfile.ZipFile(fichier) as zf:
            valider_archive_sauvegarde(zf)

            conn = get_db()
            colonnes = obtenir_colonnes(conn)
            data = lire_et_valider_json(zf, colonnes)

            restaurer_fichiers_et_base(conn, data, zf)

    except (
        zipfile.BadZipFile,
        KeyError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
        OSError,
        sqlite3.Error,
        RuntimeError,
    ) as exc :
        current_app.logger.exception(
            "Echec de l'importation de la sauvegarde ZIP"
        )
        return (
            "Import impossible : archive invalide, incompatible ou erreur "
            "de restauration. Vérifie la sauvegarde et les journaux du serveur.",
            400,
        )

    finally:
        if conn is not None:
            conn.close()

    return redirect(url_for("index"))


@sauvegarde_bp.route("/importer_csv", methods=["POST"])
@admin_requis
def importer_csv():
    table = request.form.get("table")
    fichier = request.files.get("fichier_csv")

    if table not in TABLES_SAUVEGARDE:
        return "Table invalide", 400

    if not fichier or not fichier.filename.lower().endswith(".csv"):
        return redirect(url_for(".sauvegarde_page"))

    conn = None

    try:
        contenu = fichier.read().decode("utf-8-sig")
        lecteur = csv.DictReader(io.StringIO(contenu))

        if (
            not lecteur.fieldnames
            or len(lecteur.fieldnames) != len(set(lecteur.fieldnames))
        ):
            return "En-têtes CSV absents ou dupliqués.", 400

        conn = get_db()
        colonnes_autorisees = obtenir_colonnes(conn)[table]

        if not set(lecteur.fieldnames).issubset(colonnes_autorisees):
            return "Le CSV contient des colonnes inconnues.", 400

        if "id" not in lecteur.fieldnames:
            return "La colonne id est obligatoire.", 400

        nb_maj = 0

        try:
            conn.execute("BEGIN")

            for ligne in lecteur:
                if None in ligne:
                    raise ValueError("Nombre de colonnes incorrect.")

                id_ligne = ligne.pop("id", None)

                if not id_ligne:
                    continue

                colonnes = list(ligne.keys())
                if not colonnes:
                    continue

                set_clause = ", ".join(
                    f'"{col}" = ?' for col in colonnes
                )
                valeurs = [
                    ligne[col] if ligne[col] != "" else None
                    for col in colonnes
                ]
                valeurs.append(id_ligne)

                conn.execute(
                    f'UPDATE "{table}" SET {set_clause} WHERE id = ?',
                    valeurs,
                )
                nb_maj += 1

            conn.commit()

        except (sqlite3.Error, ValueError):
            conn.rollback()
            return (
                "Import CSV invalide. Les modifications ont été annulées.",
                400,
            )

    except (UnicodeDecodeError, csv.Error, sqlite3.Error, ValueError):
        return "Fichier CSV invalide ou incompatible.", 400

    finally:
        if conn is not None:
            conn.close()

    return redirect(url_for(".sauvegarde_page", maj=nb_maj))
