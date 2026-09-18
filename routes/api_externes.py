import requests
from flask import Blueprint, request
from config import TMDB_API_KEY, GOOGLEBOOKS_API_KEY, DISCOGS_TOKEN

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/tmdb_search")
def tmdb_search():
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
    resultats = [r for r in data.get("results", []) if r.get("media_type") in ("movie", "tv")]

    if not resultats:
        return {"erreur": "Aucun résultat trouvé"}, 404

    premier = resultats[0]
    media_type = premier["media_type"]
    tmdb_id = premier["id"]

    detail_resp = requests.get(f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}", params={
        "api_key": TMDB_API_KEY,
        "language": "fr-FR",
        "append_to_response": "credits"
    }, timeout=10)
    detail = detail_resp.json()

    realisateurs = []
    if media_type == "movie":
        realisateurs = [c["name"] for c in detail.get("credits", {}).get("crew", []) if c.get("job") == "Director"]
    else:
        realisateurs = [c["name"] for c in detail.get("created_by", [])]

    acteurs = [c["name"] for c in detail.get("credits", {}).get("cast", [])[:5]]

    compositeurs = [c["name"] for c in detail.get("credits", {}).get("crew", []) if c.get("job") == "Original Music Composer"]

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


@api_bp.route("/tmdb_couvertures")
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


@api_bp.route("/discogs_search")
def discogs_search():
    titre = request.args.get("titre", "").strip()
    artiste_filtre = request.args.get("artiste", "").strip()
    code_barre = request.args.get("code_barre", "").strip()

    if not titre and not code_barre:
        return {"erreur": "Titre ou code-barre manquant"}, 400

    headers = {"User-Agent": "MediathequeFamiliale/1.0 (usage personnel)"}
    params = {"type": "release", "token": DISCOGS_TOKEN}

    if code_barre:
        params["barcode"] = code_barre
    else:
        params["release_title"] = titre
        if artiste_filtre:
            params["artist"] = artiste_filtre

    resp = requests.get("https://api.discogs.com/database/search", params=params, headers=headers, timeout=10)
    data = resp.json()
    resultats = data.get("results", [])
    if not resultats:
        return {"erreur": "Aucun résultat trouvé"}, 404

    premier = resultats[0]
    discogs_id = premier.get("id")

    detail_resp = requests.get(f"https://api.discogs.com/releases/{discogs_id}", params={"token": DISCOGS_TOKEN}, headers=headers, timeout=10)
    detail = detail_resp.json()

    artistes_noms = ", ".join([a.get("name", "") for a in detail.get("artists", [])])
    liste_pistes = [p.get("title", "") for p in detail.get("tracklist", []) if p.get("type_") == "track" or "title" in p]
    pistes_texte = "\n".join(liste_pistes)
    genres = ", ".join(detail.get("genres", []) or detail.get("styles", []))
    pochette_url = None
    images = detail.get("images", [])
    if images:
        pochette_url = images[0].get("uri")

    return {
        "titre": detail.get("title"),
        "artiste": artistes_noms,
        "annee": detail.get("year"),
        "nb_pistes": len(liste_pistes),
        "pistes": pistes_texte,
        "genre": genres,
        "pochette_url": pochette_url,
        "code_barre": code_barre or None,
    }


@api_bp.route("/discogs_couvertures")
def discogs_couvertures():
    titre = request.args.get("titre", "").strip()
    artiste_filtre = request.args.get("artiste", "").strip()
    if not titre:
        return {"erreur": "Titre manquant"}, 400

    headers = {"User-Agent": "MediathequeFamiliale/1.0 (usage personnel)"}
    params = {"type": "release", "release_title": titre, "token": DISCOGS_TOKEN, "per_page": 10}
    if artiste_filtre:
        params["artist"] = artiste_filtre

    resp = requests.get("https://api.discogs.com/database/search", params=params, headers=headers, timeout=10)
    data = resp.json()

    resultats = []
    for r in data.get("results", []):
        if not r.get("cover_image"):
            continue
        resultats.append({
            "titre": r.get("title"),
            "artiste": "",
            "pochette_url": r.get("cover_image"),
        })
        if len(resultats) >= 10:
            break

    if not resultats:
        return {"erreur": "Aucune pochette trouvée"}, 404
    return {"resultats": resultats}


@api_bp.route("/googlebooks_search")
def googlebooks_search():
    titre = request.args.get("titre", "").strip()
    artiste_filtre = request.args.get("artiste", "").strip()
    isbn = request.args.get("isbn", "").strip()

    if not titre and not isbn:
        return {"erreur": "Titre ou ISBN manquant"}, 400

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


@api_bp.route("/googlebooks_couvertures")
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
