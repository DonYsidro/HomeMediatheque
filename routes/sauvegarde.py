import os
import json
import csv
import zipfile
import io
import shutil
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, send_file
from database import get_db

sauvegarde_bp = Blueprint("sauvegarde", __name__, url_prefix="/sauvegarde")

TABLES_SAUVEGARDE = ["genres", "personnes", "medias", "medias_genres", "medias_personnes", "cds", "livres", "bd_mangas"]


@sauvegarde_bp.route("")
def sauvegarde_page():
    return render_template("sauvegarde.html")


@sauvegarde_bp.route("/export.json")
def export_json():
    conn = get_db()
    data = {}
    for table in TABLES_SAUVEGARDE:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        data[table] = [dict(row) for row in rows]
    conn.close()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data.json", json.dumps(data, ensure_ascii=False, indent=2))
        dossier_uploads = os.path.join("static", "uploads")
        if os.path.isdir(dossier_uploads):
            for nom_fichier in os.listdir(dossier_uploads):
                chemin = os.path.join(dossier_uploads, nom_fichier)
                if os.path.isfile(chemin):
                    zf.write(chemin, arcname=f"uploads/{nom_fichier}")
    buffer.seek(0)
    date_str = datetime.now().strftime("%Y-%m-%d")
    return send_file(buffer, mimetype="application/zip", as_attachment=True,
                      download_name=f"mediatheque-sauvegarde-{date_str}.zip")


@sauvegarde_bp.route("/export.csv")
def export_csv():
    conn = get_db()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for table in TABLES_SAUVEGARDE:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            if not rows:
                continue
            csv_buffer = io.StringIO()
            writer = csv.DictWriter(csv_buffer, fieldnames=rows[0].keys())
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))
            zf.writestr(f"{table}.csv", csv_buffer.getvalue())
    conn.close()
    buffer.seek(0)
    date_str = datetime.now().strftime("%Y-%m-%d")
    return send_file(buffer, mimetype="application/zip", as_attachment=True,
                      download_name=f"mediatheque-export-csv-{date_str}.zip")


@sauvegarde_bp.route("/importer", methods=["POST"])
def importer_sauvegarde():
    fichier = request.files.get("fichier_sauvegarde")
    if not fichier or not fichier.filename.endswith(".zip"):
        return redirect(url_for(".sauvegarde_page"))

    with zipfile.ZipFile(fichier) as zf:
        with zf.open("data.json") as f:
            data = json.load(f)

        dossier_uploads = os.path.join("static", "uploads")
        os.makedirs(dossier_uploads, exist_ok=True)
        for nom in zf.namelist():
            if nom.startswith("uploads/") and not nom.endswith("/"):
                nom_fichier = os.path.basename(nom)
                with zf.open(nom) as source, open(os.path.join(dossier_uploads, nom_fichier), "wb") as dest:
                    shutil.copyfileobj(source, dest)

    conn = get_db()
    conn.execute("PRAGMA foreign_keys = OFF")

    ordre_suppression = ["medias_genres", "medias_personnes", "medias", "genres", "personnes", "cds", "livres", "bd_mangas"]
    for table in ordre_suppression:
        conn.execute(f"DELETE FROM {table}")

    for table in TABLES_SAUVEGARDE:
        lignes = data.get(table, [])
        for ligne in lignes:
            colonnes = ", ".join(ligne.keys())
            valeurs = ", ".join(["?"] * len(ligne))
            conn.execute(f"INSERT INTO {table} ({colonnes}) VALUES ({valeurs})", list(ligne.values()))

    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
    conn.close()
    return redirect(url_for("index"))


@sauvegarde_bp.route("/importer_csv", methods=["POST"])
def importer_csv():
    table = request.form.get("table")
    fichier = request.files.get("fichier_csv")

    if table not in TABLES_SAUVEGARDE:
        return "Table invalide", 400
    if not fichier or not fichier.filename.endswith(".csv"):
        return redirect(url_for(".sauvegarde_page"))

    contenu = fichier.read().decode("utf-8")
    lecteur = csv.DictReader(io.StringIO(contenu))

    conn = get_db()
    nb_maj = 0
    for ligne in lecteur:
        if "id" not in ligne or not ligne["id"]:
            continue
        id_ligne = ligne.pop("id")
        colonnes = list(ligne.keys())
        if not colonnes:
            continue
        set_clause = ", ".join([f"{col} = ?" for col in colonnes])
        valeurs = [ligne[col] if ligne[col] != "" else None for col in colonnes]
        valeurs.append(id_ligne)
        conn.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", valeurs)
        nb_maj += 1
    conn.commit()
    conn.close()

    return redirect(url_for(".sauvegarde_page", maj=nb_maj))
