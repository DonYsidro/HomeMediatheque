from flask import Flask, render_template, request, redirect, url_for
from database import get_db
import os
from dotenv import load_dotenv
import json
import csv
import zipfile
import io
import shutil
from datetime import datetime
from flask import send_file

load_dotenv()

TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
GOOGLEBOOKS_API_KEY = os.environ.get("GOOGLEBOOKS_API_KEY")
import uuid

def sauvegarder_photo_upload(fichier):
    if fichier and fichier.filename:
        extension = os.path.splitext(fichier.filename)[1].lower()
        nom_unique = f"{uuid.uuid4().hex}{extension}"
        dossier = os.path.join("static", "uploads")
        os.makedirs(dossier, exist_ok=True)
        fichier.save(os.path.join(dossier, nom_unique))
        return f"/static/uploads/{nom_unique}"
    return None

def valeur_image(champ_nom):
    photo = sauvegarder_photo_upload(request.files.get("photo"))
    if photo:
        return photo
    return request.form.get(champ_nom) or None

app = Flask(__name__)

from translations import TRANSLATIONS
from flask import make_response

def get_lang():
    return request.cookies.get("lang", "fr")

@app.context_processor
def inject_translations():
    lang = get_lang()
    def t(cle):
        return TRANSLATIONS.get(lang, TRANSLATIONS["fr"]).get(cle, cle)
    return dict(t=t, lang_actuelle=lang)

@app.route("/langue/<code>")
def changer_langue(code):
    reponse = make_response(redirect(request.referrer or url_for("index")))
    reponse.set_cookie("lang", code, max_age=60*60*24*365)
    return reponse

@app.route("/")
def index():
    conn = get_db()
    nb_films = conn.execute("SELECT COUNT(*) FROM medias").fetchone()[0]
    nb_cds = conn.execute("SELECT COUNT(*) FROM cds").fetchone()[0]
    nb_livres = conn.execute("SELECT COUNT(*) FROM livres").fetchone()[0]
    nb_bd = conn.execute("SELECT COUNT(*) FROM bd_mangas").fetchone()[0]
    conn.close()
    return render_template("index.html", nb_films=nb_films, nb_cds=nb_cds,
                            nb_livres=nb_livres, nb_bd=nb_bd)


@app.route("/films")
def films():
    conn = get_db()
    medias = conn.execute("SELECT * FROM medias ORDER BY titre").fetchall()
    conn.close()
    return render_template("films.html", medias=medias)

@app.route("/ajouter", methods=["GET", "POST"])
def ajouter():
    conn = get_db()

    if request.method == "POST":
        # 1. Insertion du média principal
        cur = conn.execute("""
            INSERT INTO medias (titre, type, annee, age_classification, duree_minutes,
                                 nb_episodes, nb_saisons, synopsis, affiche_url, code_barre,
                                 lieu_stockage, support, coffret_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form["titre"],
            request.form["type"],
            request.form.get("annee") or None,
            request.form.get("age_classification") or None,
            request.form.get("duree_minutes") or None,
            request.form.get("nb_episodes") or None,
            request.form.get("nb_saisons") or None,
            request.form.get("synopsis") or None,
            valeur_image("affiche_url"),
            request.form.get("code_barre") or None,
            request.form["lieu_stockage"],
            request.form.get("support") or None,
            request.form.get("coffret_id") or None,
        ))
        media_id = cur.lastrowid

        # 2. Genres (saisis séparés par des virgules dans le formulaire)
        genres_saisis = request.form.get("genres", "")
        for nom_genre in [g.strip() for g in genres_saisis.split(",") if g.strip()]:
            conn.execute("INSERT OR IGNORE INTO genres (nom) VALUES (?)", (nom_genre,))
            genre_id = conn.execute("SELECT id FROM genres WHERE nom = ?", (nom_genre,)).fetchone()["id"]
            conn.execute("INSERT OR IGNORE INTO medias_genres (media_id, genre_id) VALUES (?, ?)",
                         (media_id, genre_id))

        # 3. Personnes (réalisateur + acteurs, séparés par des virgules)
        realisateurs = request.form.get("realisateurs", "")
        for nom in [n.strip() for n in realisateurs.split(",") if n.strip()]:
            ajouter_personne(conn, media_id, nom, "realisateur")

        acteurs = request.form.get("acteurs", "")
        for nom in [n.strip() for n in acteurs.split(",") if n.strip()]:
            ajouter_personne(conn, media_id, nom, "acteur")

        compositeurs = request.form.get("compositeurs", "")
        for nom in [n.strip() for n in compositeurs.split(",") if n.strip()]:
            ajouter_personne(conn, media_id, nom, "compositeur")

        conn.commit()
        conn.close()
        return redirect(url_for("index"))

    # Méthode GET : afficher le formulaire, avec la liste des coffrets existants
    coffrets = conn.execute("SELECT id, titre FROM medias WHERE type = 'coffret'").fetchall()
    conn.close()
    return render_template("ajouter.html", coffrets=coffrets)


@app.route("/recherche")
def recherche():
    conn = get_db()

    # Récupération des filtres depuis l'URL (tous optionnels)
    titre = request.args.get("titre", "").strip()
    artiste_filtre = request.args.get("artiste", "").strip()
    type_media = request.args.get("type", "")
    genre = request.args.get("genre", "")
    age_classification = request.args.get("age_classification", "")
    duree_max = request.args.get("duree_max", "")
    lieu_stockage = request.args.get("lieu_stockage", "").strip()
    disponible_only = request.args.get("disponible_only", "")

    # Construction dynamique de la requête SQL
    query = """
        SELECT DISTINCT m.* FROM medias m
        LEFT JOIN medias_genres mg ON m.id = mg.media_id
        LEFT JOIN genres g ON mg.genre_id = g.id
        WHERE 1=1
    """
    params = []

    if titre:
        query += " AND m.titre LIKE ?"
        params.append(f"%{titre}%")
    if type_media:
        query += " AND m.type = ?"
        params.append(type_media)
    if genre:
        query += " AND g.nom = ?"
        params.append(genre)
    if age_classification:
        query += " AND m.age_classification = ?"
        params.append(age_classification)
    if duree_max:
        query += " AND m.duree_minutes <= ?"
        params.append(duree_max)
    if lieu_stockage:
        query += " AND m.lieu_stockage LIKE ?"
        params.append(f"%{lieu_stockage}%")
    if disponible_only:
        query += " AND m.est_prete = 0"

    query += " ORDER BY m.titre"

    medias = conn.execute(query, params).fetchall()

    # Pour chaque média, récupérer ses genres (affichage)
    resultats = []
    for m in medias:
        genres = conn.execute("""
            SELECT g.nom FROM genres g
            JOIN medias_genres mg ON g.id = mg.genre_id
            WHERE mg.media_id = ?
        """, (m["id"],)).fetchall()
        resultats.append({"media": m, "genres": [g["nom"] for g in genres]})

    # Listes pour remplir les menus déroulants des filtres
    tous_genres = conn.execute("SELECT nom FROM genres ORDER BY nom").fetchall()
    toutes_classifications = conn.execute(
        "SELECT DISTINCT age_classification FROM medias WHERE age_classification IS NOT NULL"
    ).fetchall()

    conn.close()
    return render_template("recherche.html",
                            resultats=resultats,
                            tous_genres=tous_genres,
                            toutes_classifications=toutes_classifications,
                            filtres=request.args)


def ajouter_personne(conn, media_id, nom, role):
    """Ajoute une personne (si elle n'existe pas déjà) et la relie au média avec un rôle."""
    conn.execute("INSERT OR IGNORE INTO personnes (nom) VALUES (?)", (nom,))
    personne_id = conn.execute("SELECT id FROM personnes WHERE nom = ?", (nom,)).fetchone()["id"]
    conn.execute("INSERT OR IGNORE INTO medias_personnes (media_id, personne_id, role) VALUES (?, ?, ?)",
                 (media_id, personne_id, role))

@app.route("/modifier/<int:media_id>", methods=["GET", "POST"])
def modifier(media_id):
    conn = get_db()

    if request.method == "POST":
        conn.execute("""
            UPDATE medias SET
                titre = ?, type = ?, annee = ?, age_classification = ?, duree_minutes = ?,
                nb_episodes = ?, nb_saisons = ?, synopsis = ?, affiche_url = ?, code_barre = ?,
                lieu_stockage = ?, support = ?, coffret_id = ?,
                est_prete = ?, prete_a = ?, date_pret = ?
            WHERE id = ?
        """, (
            request.form["titre"],
            request.form["type"],
            request.form.get("annee") or None,
            request.form.get("age_classification") or None,
            request.form.get("duree_minutes") or None,
            request.form.get("nb_episodes") or None,
            request.form.get("nb_saisons") or None,
            request.form.get("synopsis") or None,
            valeur_image("affiche_url"),
            request.form.get("code_barre") or None,
            request.form["lieu_stockage"],
            request.form.get("support") or None,
            request.form.get("coffret_id") or None,
            1 if request.form.get("est_prete") else 0,
            request.form.get("prete_a") or None,
            request.form.get("date_pret") or None,
            media_id,
        ))

        # Genres : on supprime les anciennes associations et on remet les nouvelles
        conn.execute("DELETE FROM medias_genres WHERE media_id = ?", (media_id,))
        genres_saisis = request.form.get("genres", "")
        for nom_genre in [g.strip() for g in genres_saisis.split(",") if g.strip()]:
            conn.execute("INSERT OR IGNORE INTO genres (nom) VALUES (?)", (nom_genre,))
            genre_id = conn.execute("SELECT id FROM genres WHERE nom = ?", (nom_genre,)).fetchone()["id"]
            conn.execute("INSERT OR IGNORE INTO medias_genres (media_id, genre_id) VALUES (?, ?)",
                         (media_id, genre_id))

        # Personnes : pareil, on repart de zéro pour ce média
        conn.execute("DELETE FROM medias_personnes WHERE media_id = ?", (media_id,))
        realisateurs = request.form.get("realisateurs", "")
        for nom in [n.strip() for n in realisateurs.split(",") if n.strip()]:
            ajouter_personne(conn, media_id, nom, "realisateur")
        acteurs = request.form.get("acteurs", "")
        for nom in [n.strip() for n in acteurs.split(",") if n.strip()]:
            ajouter_personne(conn, media_id, nom, "acteur")

        conn.commit()
        conn.close()
        return redirect(url_for("index"))

    # Méthode GET : charger les données actuelles pour pré-remplir le formulaire
    media = conn.execute("SELECT * FROM medias WHERE id = ?", (media_id,)).fetchone()

    genres_actuels = conn.execute("""
        SELECT g.nom FROM genres g
        JOIN medias_genres mg ON g.id = mg.genre_id
        WHERE mg.media_id = ?
    """, (media_id,)).fetchall()
    genres_str = ", ".join([g["nom"] for g in genres_actuels])

    realisateurs_actuels = conn.execute("""
        SELECT p.nom FROM personnes p
        JOIN medias_personnes mp ON p.id = mp.personne_id
        WHERE mp.media_id = ? AND mp.role = 'realisateur'
    """, (media_id,)).fetchall()
    realisateurs_str = ", ".join([p["nom"] for p in realisateurs_actuels])

    acteurs_actuels = conn.execute("""
        SELECT p.nom FROM personnes p
        JOIN medias_personnes mp ON p.id = mp.personne_id
        WHERE mp.media_id = ? AND mp.role = 'acteur'
    """, (media_id,)).fetchall()
    acteurs_str = ", ".join([p["nom"] for p in acteurs_actuels])

    compositeurs_actuels = conn.execute("""
        SELECT p.nom FROM personnes p
        JOIN medias_personnes mp ON p.id = mp.personne_id
        WHERE mp.media_id = ? AND mp.role = 'compositeur'
    """, (media_id,)).fetchall()
    compositeurs_str = ", ".join([p["nom"] for p in compositeurs_actuels])

    coffrets = conn.execute(
        "SELECT id, titre FROM medias WHERE type = 'coffret' AND id != ?", (media_id,)
    ).fetchall()

    conn.close()
    return render_template("modifier.html", media=media, coffrets=coffrets,
                            genres_str=genres_str, realisateurs_str=realisateurs_str,
                            acteurs_str=acteurs_str,compositeurs_str=compositeurs_str)


@app.route("/supprimer/<int:media_id>", methods=["POST"])
def supprimer(media_id):
    conn = get_db()
    conn.execute("DELETE FROM medias WHERE id = ?", (media_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

import requests

@app.route("/api/tmdb_search")
def tmdb_search():
    titre = request.args.get("titre", "").strip()
    artiste_filtre = request.args.get("artiste", "").strip()
    if not titre:
        return {"erreur": "Titre manquant"}, 400

    # Recherche multi (films + séries en une seule requête)
    resp = requests.get("https://api.themoviedb.org/3/search/multi", params={
        "api_key": TMDB_API_KEY,
        "query": titre,
        "language": "fr-FR"
    }, timeout=10)
    data = resp.json()
    resultats = [r for r in data.get("results", []) if r.get("media_type") in ("movie", "tv")]

    if not resultats:
        return {"erreur": "Aucun résultat trouvé"}, 404

    # On prend le premier résultat (le plus pertinent selon TMDB)
    premier = resultats[0]
    media_type = premier["media_type"]  # "movie" ou "tv"
    tmdb_id = premier["id"]

    # Détails complets, avec équipe technique et casting en une seule requête
    detail_resp = requests.get(f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}", params={
        "api_key": TMDB_API_KEY,
        "language": "fr-FR",
        "append_to_response": "credits"
    }, timeout=10)
    detail = detail_resp.json()

    # Réalisateur (pour un film) : présent dans l'équipe technique avec le job "Director"
    realisateurs = []
    if media_type == "movie":
        realisateurs = [c["name"] for c in detail.get("credits", {}).get("crew", []) if c.get("job") == "Director"]
    else:
        # Pour une série, TMDB fournit "created_by" directement
        realisateurs = [c["name"] for c in detail.get("created_by", [])]

    # Acteurs principaux : les 5 premiers du casting, triés par ordre d'importance
    acteurs = [c["name"] for c in detail.get("credits", {}).get("cast", [])[:5]]

    # Compositeur(s) de la bande son
    compositeurs = [c["name"] for c in detail.get("credits", {}).get("crew", []) if c.get("job") == "Original Music Composer"]

    # Genres : déjà nommés dans la réponse détaillée
    genres = [g["nom"] if "nom" in g else g["name"] for g in detail.get("genres", [])]

    resultat = {
        "titre": detail.get("title") or detail.get("name"),
        "type": "film" if media_type == "movie" else "serie",
        "annee": (detail.get("release_date") or detail.get("first_air_date") or "")[:4],
        "duree_minutes": detail.get("runtime") or (detail.get("episode_run_time") or [None])[0],
        "nb_episodes": detail.get("number_of_episodes"),
        "nb_saisons": detail.get("number_of_seasons"),
        "synopsis": detail.get("overview"),
        "affiche_url": f"https://image.tmdb.org/t/p/w500{detail['poster_path']}" if detail.get("poster_path") else None,
        "genres": ", ".join(genres),
        "realisateurs": ", ".join(realisateurs),
        "acteurs": ", ".join(acteurs),
        "compositeurs": ", ".join(compositeurs),
    }
    return resultat

@app.route("/api/musicbrainz_search")
def musicbrainz_search():
    titre = request.args.get("titre", "").strip()
    artiste_filtre = request.args.get("artiste", "").strip()
    if not titre:
        return {"erreur": "Titre manquant"}, 400

    headers = {"User-Agent": "MediathequeFamiliale/1.0 (usage personnel)"}

    resp = requests.get("https://musicbrainz.org/ws/2/release/", params={
        "query": (f'release:"{titre}" AND artist:"{artiste_filtre}"' if artiste_filtre else f"release:{titre}"),
        "fmt": "json",
        "limit": 1
    }, headers=headers, timeout=10)
    data = resp.json()

    releases = data.get("releases", [])
    if not releases:
        return {"erreur": "Aucun résultat trouvé"}, 404

    release = releases[0]
    release_id = release["id"]
    artiste = ", ".join([c["artist"]["name"] for c in release.get("artist-credit", []) if isinstance(c, dict) and "artist" in c])
    annee = (release.get("date") or "")[:4]

    # Détails du disque : nombre de pistes et durée totale
    import time
    time.sleep(1.1)
    detail_resp = requests.get(f"https://musicbrainz.org/ws/2/release/{release_id}", params={
        "fmt": "json",
        "inc": "recordings"
    }, headers=headers, timeout=10)
    detail = detail_resp.json()

    nb_pistes = 0
    duree_totale_ms = 0
    liste_pistes = []
    for media in detail.get("media", []):
        nb_pistes += media.get("track-count", 0)
        for piste in media.get("tracks", []):
            duree_totale_ms += piste.get("length") or 0
            liste_pistes.append(piste.get("title", ""))
    duree_minutes = round(duree_totale_ms / 60000) if duree_totale_ms else None
    pistes_texte = "\n".join(liste_pistes)

    # Pochette (pas toujours disponible, on tente sans faire échouer si absente)
    pochette_url = None
    try:
        cover_resp = requests.get(f"https://coverartarchive.org/release/{release_id}", headers=headers, timeout=5)
        if cover_resp.ok:
            images = cover_resp.json().get("images", [])
            if images:
                pochette_url = images[0].get("image")
    except requests.RequestException:
        pass

    return {
        "titre": release.get("title"),
        "artiste": artiste,
        "annee": annee,
        "nb_pistes": nb_pistes,
        "duree_minutes": duree_minutes,
        "pochette_url": pochette_url,
	"pistes": pistes_texte,
    }

@app.route("/cds")
def cds():
    conn = get_db()
    tous_cds = conn.execute("SELECT * FROM cds ORDER BY artiste, titre").fetchall()
    conn.close()

    artistes = {}
    sans_artiste = []
    for c in tous_cds:
        if c["artiste"]:
            cle = c["artiste"]
            if cle not in artistes:
                artistes[cle] = {"artiste": cle, "pochette_url": None, "albums": 0, "un_prete": False}
            artistes[cle]["albums"] += 1
            if c["est_prete"]:
                artistes[cle]["un_prete"] = True
            if not artistes[cle]["pochette_url"] and c["pochette_url"]:
                artistes[cle]["pochette_url"] = c["pochette_url"]
        else:
            sans_artiste.append(c)

    liste_artistes = sorted(artistes.values(), key=lambda a: a["artiste"])
    return render_template("cds.html", artistes=liste_artistes, cds_sans_artiste=sans_artiste, nb_total=len(tous_cds))


@app.route("/cds/artiste")
def cds_artiste_detail():
    artiste = request.args.get("artiste", "")
    conn = get_db()
    albums = conn.execute("SELECT * FROM cds WHERE artiste = ? ORDER BY annee, titre", (artiste,)).fetchall()
    conn.close()
    return render_template("cds_artiste_detail.html", albums=albums, artiste=artiste)


@app.route("/cds/ajouter", methods=["GET", "POST"])
def ajouter_cd():
    conn = get_db()
    if request.method == "POST":
        conn.execute("""
            INSERT INTO cds (titre, artiste, annee, nb_pistes, duree_minutes, genre,
                              pochette_url, code_barre, lieu_stockage, pistes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form["titre"],
            request.form.get("artiste") or None,
            request.form.get("annee") or None,
            request.form.get("nb_pistes") or None,
            request.form.get("duree_minutes") or None,
            request.form.get("genre") or None,
            valeur_image("pochette_url"),
            request.form.get("code_barre") or None,
            request.form["lieu_stockage"],
            request.form.get("pistes") or None,
        ))
        conn.commit()
        conn.close()
        return redirect(url_for("cds"))
    conn.close()
    return render_template("ajouter_cd.html")


@app.route("/cds/modifier/<int:cd_id>", methods=["GET", "POST"])
def modifier_cd(cd_id):
    conn = get_db()
    if request.method == "POST":
        conn.execute("""
            UPDATE cds SET titre=?, artiste=?, annee=?, nb_pistes=?, duree_minutes=?,
                           genre=?, pochette_url=?, code_barre=?, lieu_stockage=?,
                           est_prete=?, prete_a=?, date_pret=?, pistes=?
            WHERE id=?
        """, (
            request.form["titre"],
            request.form.get("artiste") or None,
            request.form.get("annee") or None,
            request.form.get("nb_pistes") or None,
            request.form.get("duree_minutes") or None,
            request.form.get("genre") or None,
            valeur_image("pochette_url"),
            request.form.get("code_barre") or None,
            request.form["lieu_stockage"],
            1 if request.form.get("est_prete") else 0,
            request.form.get("prete_a") or None,
            request.form.get("date_pret") or None,
            request.form.get("pistes") or None,
            cd_id,
        ))
        conn.commit()
        conn.close()
        return redirect(url_for("cds"))
    cd = conn.execute("SELECT * FROM cds WHERE id = ?", (cd_id,)).fetchone()
    conn.close()
    return render_template("modifier_cd.html", cd=cd)


@app.route("/cds/supprimer/<int:cd_id>", methods=["POST"])
def supprimer_cd(cd_id):
    conn = get_db()
    conn.execute("DELETE FROM cds WHERE id = ?", (cd_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("cds"))

@app.route("/api/googlebooks_search")
def googlebooks_search():
    titre = request.args.get("titre", "").strip()
    artiste_filtre = request.args.get("artiste", "").strip()
    isbn = request.args.get("isbn", "").strip()

    if not titre and not isbn:
        return {"erreur": "Titre ou ISBN manquant"}, 400

    # Priorité à l'ISBN s'il est renseigné : recherche beaucoup plus précise
    if isbn:
        requete = f"isbn:{isbn}"
    else:
        requete = titre

    resp = requests.get("https://www.googleapis.com/books/v1/volumes", params={
        "q": requete,
        "maxResults": 10,
        "langRestrict": "fr",
        "key": GOOGLEBOOKS_API_KEY
    }, timeout=10)
    data = resp.json()
    items = data.get("items", [])

    # Si rien trouvé en français, on retente sans restriction de langue
    if not items:
        resp = requests.get("https://www.googleapis.com/books/v1/volumes", params={
            "q": requete,
            "maxResults": 1,
            "key": GOOGLEBOOKS_API_KEY
        }, timeout=10)
        data = resp.json()
        items = data.get("items", [])

    if not items:
        return {"erreur": "Aucun résultat trouvé"}, 404

    info = items[0].get("volumeInfo", {})

    isbn_trouve = None
    for identifiant in info.get("industryIdentifiers", []):
        if identifiant.get("type") in ("ISBN_13", "ISBN_10"):
            isbn_trouve = identifiant.get("identifier")
            break

    return {
        "titre": info.get("title"),
        "auteur": ", ".join(info.get("authors", [])),
        "annee": (info.get("publishedDate") or "")[:4],
        "editeur": info.get("publisher"),
        "nb_pages": info.get("pageCount"),
        "isbn": isbn_trouve,
        "langue": info.get("language"),
        "synopsis": info.get("description"),
        "couverture_url": info.get("imageLinks", {}).get("thumbnail"),
    }

@app.route("/livres")
def livres():
    conn = get_db()
    sous_type = request.args.get("sous_type", "")
    if sous_type:
        tous_livres = conn.execute(
            "SELECT * FROM livres WHERE sous_type = ? ORDER BY serie, auteur, titre, numero_tome", (sous_type,)
        ).fetchall()
    else:
        tous_livres = conn.execute("SELECT * FROM livres ORDER BY serie, auteur, titre, numero_tome").fetchall()
    conn.close()

    series = {}
    individuels = []
    for l in tous_livres:
        if l["serie"]:
            cle = l["serie"]
            if cle not in series:
                series[cle] = {
                    "serie": cle,
                    "auteur": l["auteur"],
                    "sous_type": l["sous_type"],
                    "couverture_url": l["couverture_url"],
                    "tomes_possedes": 0,
                    "un_prete": False,
                }
            series[cle]["tomes_possedes"] += 1
            if l["est_prete"]:
                series[cle]["un_prete"] = True
            if not series[cle]["couverture_url"] and l["couverture_url"]:
                series[cle]["couverture_url"] = l["couverture_url"]
        else:
            individuels.append(l)

    liste_series = sorted(series.values(), key=lambda s: s["serie"])
    return render_template("livres.html", series=liste_series, livres=individuels, sous_type_actif=sous_type)


@app.route("/livres/serie")
def livres_serie_detail():
    serie = request.args.get("serie", "")
    conn = get_db()
    tomes = conn.execute(
        "SELECT * FROM livres WHERE serie = ? ORDER BY numero_tome", (serie,)
    ).fetchall()
    conn.close()
    return render_template("livres_serie_detail.html", tomes=tomes, serie=serie)

@app.route("/livres/ajouter", methods=["GET", "POST"])
def ajouter_livre():
    conn = get_db()
    if request.method == "POST":
        conn.execute("""
            INSERT INTO livres (titre, serie, numero_tome, auteur, sous_type, annee, editeur, nb_pages, isbn,
                                 langue, synopsis, couverture_url, lieu_stockage)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form["titre"],
            request.form.get("serie") or None,
            request.form.get("numero_tome") or None,
            request.form.get("auteur") or None,
            request.form["sous_type"],
            request.form.get("annee") or None,
            request.form.get("editeur") or None,
            request.form.get("nb_pages") or None,
            request.form.get("isbn") or None,
            request.form.get("langue") or None,
            request.form.get("synopsis") or None,
            valeur_image("couverture_url"),
            request.form["lieu_stockage"],
        ))
        conn.commit()
        conn.close()
        return redirect(url_for("livres"))
    conn.close()
    return render_template("ajouter_livre.html")


@app.route("/livres/modifier/<int:livre_id>", methods=["GET", "POST"])
def modifier_livre(livre_id):
    conn = get_db()
    if request.method == "POST":
        conn.execute("""
            UPDATE livres SET titre=?, serie=?, numero_tome=?, auteur=?, sous_type=?, annee=?, editeur=?,
                               nb_pages=?, isbn=?, langue=?, synopsis=?, couverture_url=?, lieu_stockage=?,
                               est_prete=?, prete_a=?, date_pret=?
            WHERE id=?
        """, (
            request.form["titre"],
            request.form.get("serie") or None,
            request.form.get("numero_tome") or None,
            request.form.get("auteur") or None,
            request.form["sous_type"],
            request.form.get("annee") or None,
            request.form.get("editeur") or None,
            request.form.get("nb_pages") or None,
            request.form.get("isbn") or None,
            request.form.get("langue") or None,
            request.form.get("synopsis") or None,
            valeur_image("couverture_url"),
            request.form["lieu_stockage"],
            1 if request.form.get("est_prete") else 0,
            request.form.get("prete_a") or None,
            request.form.get("date_pret") or None,
            livre_id,
        ))
        conn.commit()
        conn.close()
        return redirect(url_for("livres"))
    livre = conn.execute("SELECT * FROM livres WHERE id = ?", (livre_id,)).fetchone()
    conn.close()
    return render_template("modifier_livre.html", livre=livre)


@app.route("/livres/supprimer/<int:livre_id>", methods=["POST"])
def supprimer_livre(livre_id):
    conn = get_db()
    conn.execute("DELETE FROM livres WHERE id = ?", (livre_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("livres"))

@app.route("/api/googlebooks_couvertures")
def googlebooks_couvertures():
    titre = request.args.get("titre", "").strip()
    artiste_filtre = request.args.get("artiste", "").strip()
    if not titre:
        return {"erreur": "Titre manquant"}, 400

    resp = requests.get("https://www.googleapis.com/books/v1/volumes", params={
        "q": titre,
        "maxResults": 8,
        "key": GOOGLEBOOKS_API_KEY
    }, timeout=10)
    data = resp.json()

    resultats = []
    for item in data.get("items", []):
        info = item.get("volumeInfo", {})
        couverture = info.get("imageLinks", {}).get("thumbnail")
        if couverture:
            resultats.append({
                "titre": info.get("title"),
                "auteur": ", ".join(info.get("authors", [])),
                "couverture_url": couverture
            })
        if len(resultats) >= 10:
            break

    if not resultats:
        return {"erreur": "Aucune couverture trouvée"}, 404

    return {"resultats": resultats}

@app.route("/bd-mangas")
def bd_mangas():
    conn = get_db()
    tous = conn.execute("SELECT * FROM bd_mangas ORDER BY serie, titre, numero_tome").fetchall()
    conn.close()

    series = {}
    for item in tous:
        cle = item["serie"] or item["titre"]
        if cle not in series:
            series[cle] = {
                "serie": cle,
                "type": item["type"],
                "auteur": item["auteur"],
                "nb_tomes_serie": item["nb_tomes_serie"],
                "couverture_url": item["couverture_url"],
                "tomes_possedes": 0,
                "un_prete": False,
            }
        series[cle]["tomes_possedes"] += 1
        if item["est_prete"]:
            series[cle]["un_prete"] = True
        if not series[cle]["couverture_url"] and item["couverture_url"]:
            series[cle]["couverture_url"] = item["couverture_url"]

    liste_series = sorted(series.values(), key=lambda s: s["serie"])
    return render_template("bd_mangas.html", series=liste_series, nb_total=len(tous))


@app.route("/bd-mangas/serie")
def bd_serie_detail():
    serie = request.args.get("serie", "")
    conn = get_db()
    tomes = conn.execute(
        "SELECT * FROM bd_mangas WHERE COALESCE(serie, titre) = ? ORDER BY numero_tome", (serie,)
    ).fetchall()
    conn.close()
    return render_template("bd_serie_detail.html", tomes=tomes, serie=serie)


@app.route("/bd-mangas/ajouter", methods=["GET", "POST"])
def ajouter_bd():
    conn = get_db()
    if request.method == "POST":
        conn.execute("""
            INSERT INTO bd_mangas (titre, serie, auteur, type, numero_tome, nb_tomes_serie, annee,
                                    editeur, isbn, langue, synopsis, couverture_url, lieu_stockage)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form["titre"],
            request.form["serie"],
            request.form.get("auteur") or None,
            request.form["type"],
            request.form.get("numero_tome") or None,
            request.form.get("nb_tomes_serie") or None,
            request.form.get("annee") or None,
            request.form.get("editeur") or None,
            request.form.get("isbn") or None,
            request.form.get("langue") or None,
            request.form.get("synopsis") or None,
            valeur_image("couverture_url"),
            request.form["lieu_stockage"],
        ))
        conn.commit()
        conn.close()
        return redirect(url_for("bd_mangas"))
    conn.close()
    return render_template("ajouter_bd.html")


@app.route("/bd-mangas/modifier/<int:item_id>", methods=["GET", "POST"])
def modifier_bd(item_id):
    conn = get_db()
    if request.method == "POST":
        conn.execute("""
            UPDATE bd_mangas SET titre=?, serie=?, type=?, numero_tome=?, nb_tomes_serie=?,
                                  annee=?, editeur=?, isbn=?, langue=?, synopsis=?, couverture_url=?,
                                  lieu_stockage=?, est_prete=?, prete_a=?, date_pret=?
            WHERE id=?
        """, (
            request.form["titre"],
            request.form["serie"],
            request.form["type"],
            request.form.get("numero_tome") or None,
            request.form.get("nb_tomes_serie") or None,
            request.form.get("annee") or None,
            request.form.get("editeur") or None,
            request.form.get("isbn") or None,
            request.form.get("langue") or None,
            request.form.get("synopsis") or None,
            valeur_image("couverture_url"),
            request.form["lieu_stockage"],
            1 if request.form.get("est_prete") else 0,
            request.form.get("prete_a") or None,
            request.form.get("date_pret") or None,
            item_id,
        ))
        conn.commit()
        conn.close()
        return redirect(url_for("bd_mangas"))
    item = conn.execute("SELECT * FROM bd_mangas WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    return render_template("modifier_bd.html", item=item)

@app.route("/bd-mangas/supprimer/<int:item_id>", methods=["POST"])
def supprimer_bd(item_id):
    conn = get_db()
    conn.execute("DELETE FROM bd_mangas WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("bd_mangas"))

@app.route("/api/tmdb_couvertures")
def tmdb_couvertures():
    titre = request.args.get("titre", "").strip()
    artiste_filtre = request.args.get("artiste", "").strip()
    if not titre:
        return {"erreur": "Titre manquant"}, 400

    resp = requests.get("https://api.themoviedb.org/3/search/multi", params={
        "api_key": TMDB_API_KEY,
        "query": titre,
        "language": "fr-FR"
    }, timeout=10)
    data = resp.json()

    resultats = []
    for r in data.get("results", []):
        if r.get("media_type") not in ("movie", "tv"):
            continue
        if not r.get("poster_path"):
            continue
        resultats.append({
            "titre": r.get("title") or r.get("name"),
            "annee": (r.get("release_date") or r.get("first_air_date") or "")[:4],
            "affiche_url": f"https://image.tmdb.org/t/p/w500{r['poster_path']}"
        })
        if len(resultats) >= 10:
            break

    if not resultats:
        return {"erreur": "Aucune affiche trouvée"}, 404
    return {"resultats": resultats}


@app.route("/api/musicbrainz_couvertures")
def musicbrainz_couvertures():
    titre = request.args.get("titre", "").strip()
    artiste_filtre = request.args.get("artiste", "").strip()
    if not titre:
        return {"erreur": "Titre manquant"}, 400

    headers = {"User-Agent": "MediathequeFamiliale/1.0 (usage personnel)"}
    resp = requests.get("https://musicbrainz.org/ws/2/release/", params={
        "query": (f'release:"{titre}" AND artist:"{artiste_filtre}"' if artiste_filtre else f"release:{titre}"),
        "fmt": "json",
        "limit": 10
    }, headers=headers, timeout=10)
    data = resp.json()

    resultats = []
    for release in data.get("releases", []):
        artiste = ", ".join([c["artist"]["name"] for c in release.get("artist-credit", []) if isinstance(c, dict) and "artist" in c])
        resultats.append({
            "titre": release.get("title"),
            "artiste": artiste,
            "pochette_url": f"https://coverartarchive.org/release/{release['id']}/front-250"
        })

    if not resultats:
        return {"erreur": "Aucune pochette trouvée"}, 404
    return {"resultats": resultats}

TABLES_SAUVEGARDE = ["genres", "personnes", "medias", "medias_genres", "medias_personnes", "cds", "livres", "bd_mangas"]

@app.route("/sauvegarde")
def sauvegarde_page():
    return render_template("sauvegarde.html")


@app.route("/sauvegarde/export.json")
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


@app.route("/sauvegarde/export.csv")
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


@app.route("/sauvegarde/importer", methods=["POST"])
def importer_sauvegarde():
    fichier = request.files.get("fichier_sauvegarde")
    if not fichier or not fichier.filename.endswith(".zip"):
        return redirect(url_for("sauvegarde_page"))

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

@app.route("/sauvegarde/importer_csv", methods=["POST"])
def importer_csv():
    table = request.form.get("table")
    fichier = request.files.get("fichier_csv")

    if table not in TABLES_SAUVEGARDE:
        return "Table invalide", 400
    if not fichier or not fichier.filename.endswith(".csv"):
        return redirect(url_for("sauvegarde_page"))

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

    return redirect(url_for("sauvegarde_page", maj=nb_maj))


@app.route("/voir/<int:media_id>")
def voir_media(media_id):
    conn = get_db()
    media = conn.execute("SELECT * FROM medias WHERE id = ?", (media_id,)).fetchone()
    genres = conn.execute("""
        SELECT g.nom FROM genres g JOIN medias_genres mg ON g.id = mg.genre_id
        WHERE mg.media_id = ?
    """, (media_id,)).fetchall()
    realisateurs = conn.execute("""
        SELECT p.nom FROM personnes p JOIN medias_personnes mp ON p.id = mp.personne_id
        WHERE mp.media_id = ? AND mp.role = 'realisateur'
    """, (media_id,)).fetchall()
    acteurs = conn.execute("""
        SELECT p.nom FROM personnes p JOIN medias_personnes mp ON p.id = mp.personne_id
        WHERE mp.media_id = ? AND mp.role = 'acteur'
    """, (media_id,)).fetchall()
    compositeurs = conn.execute("""
        SELECT p.nom FROM personnes p JOIN medias_personnes mp ON p.id = mp.personne_id
        WHERE mp.media_id = ? AND mp.role = 'compositeur'
    """, (media_id,)).fetchall()
    conn.close()
    return render_template("voir.html", media=media,
                            genres=[g["nom"] for g in genres],
                            realisateurs=[p["nom"] for p in realisateurs],
                            acteurs=[p["nom"] for p in acteurs],
                            compositeurs=[p["nom"] for p in compositeurs])


@app.route("/cds/voir/<int:cd_id>")
def voir_cd(cd_id):
    conn = get_db()
    cd = conn.execute("SELECT * FROM cds WHERE id = ?", (cd_id,)).fetchone()
    conn.close()
    return render_template("voir_cd.html", cd=cd)


@app.route("/livres/voir/<int:livre_id>")
def voir_livre(livre_id):
    conn = get_db()
    livre = conn.execute("SELECT * FROM livres WHERE id = ?", (livre_id,)).fetchone()
    conn.close()
    return render_template("voir_livre.html", livre=livre)


@app.route("/bd-mangas/voir/<int:item_id>")
def voir_bd(item_id):
    conn = get_db()
    item = conn.execute("SELECT * FROM bd_mangas WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    return render_template("voir_bd.html", item=item)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
