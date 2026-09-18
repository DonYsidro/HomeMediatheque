from flask import Blueprint, render_template, request, redirect, url_for
from database import get_db
from utils import valeur_image

films_bp = Blueprint("films", __name__)


def ajouter_personne(conn, media_id, nom, role):
    """Ajoute une personne (si elle n'existe pas déjà) et la relie au média avec un rôle."""
    conn.execute("INSERT OR IGNORE INTO personnes (nom) VALUES (?)", (nom,))
    personne_id = conn.execute("SELECT id FROM personnes WHERE nom = ?", (nom,)).fetchone()["id"]
    conn.execute("INSERT OR IGNORE INTO medias_personnes (media_id, personne_id, role) VALUES (?, ?, ?)",
                 (media_id, personne_id, role))


@films_bp.route("/films")
def films():
    conn = get_db()
    medias = conn.execute("SELECT * FROM medias ORDER BY titre").fetchall()
    conn.close()
    return render_template("films.html", medias=medias)


@films_bp.route("/ajouter", methods=["GET", "POST"])
def ajouter():
    conn = get_db()

    if request.method == "POST":
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

        genres_saisis = request.form.get("genres", "")
        for nom_genre in [g.strip() for g in genres_saisis.split(",") if g.strip()]:
            conn.execute("INSERT OR IGNORE INTO genres (nom) VALUES (?)", (nom_genre,))
            genre_id = conn.execute("SELECT id FROM genres WHERE nom = ?", (nom_genre,)).fetchone()["id"]
            conn.execute("INSERT OR IGNORE INTO medias_genres (media_id, genre_id) VALUES (?, ?)",
                         (media_id, genre_id))

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

    coffrets = conn.execute("SELECT id, titre FROM medias WHERE type = 'coffret'").fetchall()
    conn.close()
    return render_template("ajouter.html", coffrets=coffrets)


@films_bp.route("/recherche")
def recherche():
    conn = get_db()

    titre = request.args.get("titre", "").strip()
    artiste_filtre = request.args.get("artiste", "").strip()
    type_media = request.args.get("type", "")
    genre = request.args.get("genre", "")
    age_classification = request.args.get("age_classification", "")
    duree_max = request.args.get("duree_max", "")
    lieu_stockage = request.args.get("lieu_stockage", "").strip()
    disponible_only = request.args.get("disponible_only", "")

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

    resultats = []
    for m in medias:
        genres = conn.execute("""
            SELECT g.nom FROM genres g
            JOIN medias_genres mg ON g.id = mg.genre_id
            WHERE mg.media_id = ?
        """, (m["id"],)).fetchall()
        resultats.append({"media": m, "genres": [g["nom"] for g in genres]})

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


@films_bp.route("/modifier/<int:media_id>", methods=["GET", "POST"])
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

        conn.execute("DELETE FROM medias_genres WHERE media_id = ?", (media_id,))
        genres_saisis = request.form.get("genres", "")
        for nom_genre in [g.strip() for g in genres_saisis.split(",") if g.strip()]:
            conn.execute("INSERT OR IGNORE INTO genres (nom) VALUES (?)", (nom_genre,))
            genre_id = conn.execute("SELECT id FROM genres WHERE nom = ?", (nom_genre,)).fetchone()["id"]
            conn.execute("INSERT OR IGNORE INTO medias_genres (media_id, genre_id) VALUES (?, ?)",
                         (media_id, genre_id))

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
                            acteurs_str=acteurs_str, compositeurs_str=compositeurs_str)


@films_bp.route("/supprimer/<int:media_id>", methods=["POST"])
def supprimer(media_id):
    conn = get_db()
    conn.execute("DELETE FROM medias WHERE id = ?", (media_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@films_bp.route("/voir/<int:media_id>")
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
