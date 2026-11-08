import re
import unicodedata
from contextlib import closing

from flask import Blueprint, render_template, request, redirect, url_for
from database import get_db

recherche_bp = Blueprint("recherche", __name__)

MAX_RESULTATS = 300   # nombre maximum de fiches affichées
MAX_MOTS = 8          # au-delà, les mots saisis en trop sont ignorés

# Filtre d'âge (« convient à un enfant de… ») mis de côté pour une évolution ultérieure.
# Passer FILTRE_AGE_ACTIF à True pour le réactiver : le menu réapparaît dans la page.
FILTRE_AGE_ACTIF = False
AGES_PROPOSES = [0, 6, 10, 12, 16]  # 0 = tous publics uniquement


def normaliser(texte):
    """Minuscules + sans accents : 'Été' et 'ete' deviennent identiques."""
    if texte is None:
        return ""
    decompose = unicodedata.normalize("NFD", str(texte))
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return sans_accents.casefold().replace("œ", "oe").replace("æ", "ae")


def age_minimum(classification):
    """Âge minimum déduit du texte libre de la classification (utilisé par le filtre d'âge).
    '12+', '-12', '12 ans' -> 12 ; 'Tous publics', 'TP' -> 0 ; vide ou illisible -> None."""
    if not classification:
        return None
    texte = normaliser(classification).strip()
    nombre = re.search(r"\d+", texte)
    if nombre:
        return int(nombre.group())
    if "tous" in texte or "all" in texte or texte in ("tp", "u", "g"):
        return 0
    return None


def echapper_like(mot):
    """Empêche % et _ saisis par l'utilisateur d'agir comme jokers dans LIKE."""
    return mot.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def texte_sql(*expressions):
    """Assemble les champs dans lesquels on cherche en un seul texte (les champs vides sont ignorés)."""
    return " || ' ' || ".join("COALESCE(" + e + ", '')" for e in expressions)


def pret_sql(alias):
    """Nom de l'emprunteur, seulement si la fiche est réellement prêtée."""
    return "CASE WHEN " + alias + ".est_prete = 1 THEN " + alias + ".prete_a END"


# Les 4 tables. 'texte' = tous les champs dans lesquels on cherche les mots saisis :
# pour chercher dans un champ de plus, il suffit de l'ajouter dans la liste de la table.
# 'categories' traduit la valeur du champ type en clé de traduction du libellé affiché sur la carte.
# 'endpoint' / 'param' servent à construire l'adresse de la fiche avec url_for (jamais écrite à la main).
TABLES = {
    "films": {
        "icone": "🎬",
        "endpoint": "films.voir_media",
        "param": "media_id",
        "select": """
            SELECT m.id, m.titre, m.serie, m.type AS type_cle, m.annee, NULL AS auteur,
                   m.affiche_url AS image, m.lieu_stockage, m.est_prete, m.prete_a
            FROM medias m
        """,
        "texte": texte_sql(
            "m.titre", "m.serie", "CAST(m.annee AS TEXT)", "m.support", "m.code_barre",
            "m.lieu_stockage", pret_sql("m"),
            "(SELECT GROUP_CONCAT(g.nom, ' ') FROM medias_genres mg JOIN genres g ON g.id = mg.genre_id"
            " WHERE mg.media_id = m.id)",
            "(SELECT GROUP_CONCAT(p.nom, ' ') FROM medias_personnes mp JOIN personnes p ON p.id = mp.personne_id"
            " WHERE mp.media_id = m.id)",
        ),
        "categories": {"film": "type_film", "coffret": "type_film", "serie": "type_serie",
                       "animation": "type_animation", "anime": "type_anime"},
        "colonne_age": "m.age_classification",
    },
    "cds": {
        "icone": "💿",
        "endpoint": "cds.voir_cd",
        "param": "cd_id",
        "select": """
            SELECT c.id, c.titre, NULL AS serie, NULL AS type_cle, c.annee, c.artiste AS auteur,
                   c.pochette_url AS image, c.lieu_stockage, c.est_prete, c.prete_a
            FROM cds c
        """,
        "texte": texte_sql(
            "c.titre", "c.artiste", "CAST(c.annee AS TEXT)", "c.genre", "c.pistes", "c.code_barre",
            "c.lieu_stockage", pret_sql("c"),
        ),
        "categories": {None: "type_cd"},
    },
    "livres": {
        "icone": "📚",
        "endpoint": "livres.voir_livre",
        "param": "livre_id",
        "select": """
            SELECT l.id, l.titre, l.serie, l.sous_type AS type_cle, l.annee, l.auteur,
                   l.couverture_url AS image, l.lieu_stockage, l.est_prete, l.prete_a
            FROM livres l
        """,
        "texte": texte_sql(
            "l.titre", "l.serie", "l.auteur", "l.editeur", "l.isbn", "l.langue", "CAST(l.annee AS TEXT)",
            "l.lieu_stockage", pret_sql("l"),
        ),
        "categories": "type_livre",  # une seule catégorie ; le sous-type (roman...) est affiché en détail
        "detail": True,
    },
    "bd_mangas": {
        "icone": "📖",
        "endpoint": "bd_mangas.voir_bd",
        "param": "item_id",
        "select": """
            SELECT b.id, b.titre, b.serie, b.type AS type_cle, b.annee, b.auteur,
                   b.couverture_url AS image, b.lieu_stockage, b.est_prete, b.prete_a
            FROM bd_mangas b
        """,
        "texte": texte_sql(
            "b.titre", "b.serie", "b.auteur", "b.editeur", "b.isbn", "b.langue", "CAST(b.annee AS TEXT)",
            "b.lieu_stockage", pret_sql("b"),
        ),
        "categories": {"bd": "type_bd", "manga": "type_manga"},
    },
}

# Filtre « catégorie » : clé -> (table, condition SQL en plus, paramètres, clé de traduction du libellé).
# Les anciens « coffrets » sont rangés avec les films, comme ailleurs dans l'appli.
FILTRES_CATEGORIE = {
    "film": ("films", "m.type IN ('film', 'coffret')", [], "cat_film"),
    "serie": ("films", "m.type = ?", ["serie"], "cat_serie"),
    "animation": ("films", "m.type = ?", ["animation"], "cat_animation"),
    "anime": ("films", "m.type = ?", ["anime"], "cat_anime"),
    "cd": ("cds", None, [], "cds"),
    "livre": ("livres", None, [], "livres"),
    "bd": ("bd_mangas", "b.type = ?", ["bd"], "type_bd"),
    "manga": ("bd_mangas", "b.type = ?", ["manga"], "type_manga"),
}


def categorie_de(table, type_cle):
    """Clé de traduction du libellé de catégorie affiché sur la carte."""
    categories = table["categories"]
    if isinstance(categories, str):
        return categories
    return categories.get(type_cle, "type_film")


def chercher(conn, mots, cat, age_max):
    """Retourne (fiches, tronque) : toutes les catégories mélangées, triées par titre."""
    table_voulue = FILTRES_CATEGORIE[cat][0] if cat else None
    fiches = []
    tronque = False
    for cle, table in TABLES.items():
        if table_voulue and cle != table_voulue:
            continue
        if age_max is not None and "colonne_age" not in table:
            continue  # seule la table des films a une classification d'âge

        conditions, parametres = [], []
        for mot in mots:
            conditions.append("norm(" + table["texte"] + ") LIKE ? ESCAPE '\\'")
            parametres.append("%" + echapper_like(normaliser(mot)) + "%")
        if cat and FILTRES_CATEGORIE[cat][1]:
            conditions.append(FILTRES_CATEGORIE[cat][1])
            parametres.extend(FILTRES_CATEGORIE[cat][2])
        if age_max is not None:
            # age_min(...) vaut NULL si l'âge est vide ou illisible : la fiche est alors écartée
            conditions.append("age_min(" + table["colonne_age"] + ") <= ?")
            parametres.append(age_max)

        sql = (table["select"] + " WHERE " + " AND ".join(conditions)
               + " ORDER BY titre COLLATE NOCASE LIMIT " + str(MAX_RESULTATS))
        lignes = conn.execute(sql, parametres).fetchall()
        if len(lignes) >= MAX_RESULTATS:
            tronque = True
        for ligne in lignes:
            fiche = dict(ligne)
            fiche["famille"] = cle
            fiche["icone"] = table["icone"]
            fiche["categorie_cle"] = categorie_de(table, fiche["type_cle"])
            fiche["detail_cle"] = "type_" + fiche["type_cle"] if table.get("detail") and fiche["type_cle"] else None
            fiche["url"] = url_for(table["endpoint"], **{table["param"]: fiche["id"]})
            fiches.append(fiche)

    # Grille mélangée, triée par titre sans tenir compte des accents ni des majuscules
    fiches.sort(key=lambda f: (normaliser(f["titre"]), f["famille"], f["id"]))
    if len(fiches) > MAX_RESULTATS:
        fiches = fiches[:MAX_RESULTATS]
        tronque = True
    return fiches, tronque


# '/chercher' (et non '/recherche...') pour ne pas être pris pour une section par le bandeau.
@recherche_bp.route("/chercher")
def chercher_partout():
    q = request.args.get("q", "").strip()
    mots = q.split()[:MAX_MOTS]

    cat = request.args.get("cat", "")
    if cat not in FILTRES_CATEGORIE:
        cat = ""

    # Le filtre d'âge n'existe que pour Films & Séries : ignoré pour CD, livres, BD, manga
    age_max = None
    age_txt = request.args.get("age", "")
    if FILTRE_AGE_ACTIF and cat in ("", "film", "serie", "animation", "anime"):
        if age_txt.isdigit() and int(age_txt) in AGES_PROPOSES:
            age_max = int(age_txt)

    # Champ vide = aucun résultat, même si une catégorie (ou un âge) est choisie
    fiches, tronque = [], False
    if mots:
        # closing() ferme la connexion quoi qu'il arrive, même si une requête échoue
        with closing(get_db()) as conn:
            conn.create_function("norm", 1, normaliser)
            conn.create_function("age_min", 1, age_minimum)
            fiches, tronque = chercher(conn, mots, cat, age_max)

    contexte = dict(q=q, cat=cat, age=age_max, fiches=fiches, tronque=tronque, max_resultats=MAX_RESULTATS)

    # La recherche instantanée ne redemande que la zone des résultats
    if request.args.get("partiel") == "1":
        return render_template("_resultats_recherche.html", **contexte)

    return render_template(
        "recherche_globale.html",
        categories=[(cle, v[3]) for cle, v in FILTRES_CATEGORIE.items()],
        ages=AGES_PROPOSES,
        filtre_age_actif=FILTRE_AGE_ACTIF,
        **contexte,
    )


# Ancienne adresse de la recherche Films : on renvoie vers la page unique.
@recherche_bp.route("/recherche")
def ancienne_recherche():
    return redirect(url_for("recherche.chercher_partout", q=request.args.get("titre", "")))
