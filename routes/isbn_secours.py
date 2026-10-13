import re
import xml.etree.ElementTree as ET

import requests

NS_DC = "{http://purl.org/dc/elements/1.1/}"
NS_SRW = "{http://www.loc.gov/zing/srw/}"
LANGUES = {"fre": "fr", "eng": "en", "jpn": "ja", "spa": "es", "ger": "de", "ita": "it"}


def couverture_openlibrary(isbn):
    """URL de la couverture Open Library si elle existe, sinon None."""
    url = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
    try:
        r = requests.head(url + "?default=false", timeout=3, allow_redirects=True)
        if r.status_code == 200:
            return url
    except requests.RequestException:
        pass
    return None


def nettoyer_auteur(brut):
    """'Deteindre, Stéphane (1967-....). Auteur du texte' -> 'Stéphane Deteindre'"""
    if " (" in brut:
        nom = brut.split(" (")[0]
    elif ". " in brut:
        nom = brut.rsplit(". ", 1)[0]
    else:
        nom = brut
    nom = nom.strip()
    if "," in nom:
        famille, prenom = nom.split(",", 1)
        nom = f"{prenom.strip()} {famille.strip()}"
    return nom


def chercher_isbn_bnf(isbn):
    """Catalogue de la BnF (SRU, sans clé) : bien couvert pour les éditions françaises."""
    try:
        resp = requests.get("https://catalogue.bnf.fr/api/SRU", params={
            "version": "1.2",
            "operation": "searchRetrieve",
            "query": 'bib.isbn all "' + isbn + '"',
            "recordSchema": "dublincore",
            "maximumRecords": 1,
        }, timeout=6)
        racine = ET.fromstring(resp.content)
    except (requests.RequestException, ET.ParseError):
        return None

    nb = racine.find(f".//{NS_SRW}numberOfRecords")
    if nb is None or not nb.text or nb.text.strip() == "0":
        return None

    def champ(nom):
        el = racine.find(f".//{NS_DC}{nom}")
        return el.text.strip() if el is not None and el.text else ""

    titre = champ("title").split(" / ")[0].strip()

    auteurs = []
    for el in racine.findall(f".//{NS_DC}creator"):
        if el.text:
            nom = nettoyer_auteur(el.text.strip())
            if nom and nom not in auteurs:
                auteurs.append(nom)

    editeur = re.sub(r"\s*\(.*?\)\s*$", "", champ("publisher")).strip()
    m_annee = re.search(r"\d{4}", champ("date"))
    m_pages = re.search(r"(\d+)\s*p\.", champ("format"))

    return {
        "titre": titre,
        "auteur": ", ".join(auteurs[:3]),
        "annee": m_annee.group(0) if m_annee else "",
        "editeur": editeur,
        "nb_pages": int(m_pages.group(1)) if m_pages else None,
        "isbn": isbn,
        "langue": LANGUES.get(champ("language"), champ("language")[:2]),
        "synopsis": None,
        "couverture_url": couverture_openlibrary(isbn),
    }


def chercher_isbn_openlibrary(isbn):
    try:
        resp = requests.get("https://openlibrary.org/api/books", params={
            "bibkeys": "ISBN:" + isbn, "format": "json", "jscmd": "data",
        }, timeout=6)
        data = resp.json().get("ISBN:" + isbn)
    except (requests.RequestException, ValueError):
        return None
    if not data:
        return None

    m_annee = re.search(r"\d{4}", data.get("publish_date") or "")
    cover = data.get("cover") or {}
    return {
        "titre": data.get("title"),
        "auteur": ", ".join(a.get("name", "") for a in data.get("authors", [])),
        "annee": m_annee.group(0) if m_annee else "",
        "editeur": ", ".join(p.get("name", "") for p in data.get("publishers", [])),
        "nb_pages": data.get("number_of_pages"),
        "isbn": isbn,
        "langue": None,
        "synopsis": None,
        "couverture_url": cover.get("large") or cover.get("medium"),
    }


def isbn13_vers_10(isbn13):
    """978XXXXXXXXXC -> ISBN-10 équivalent (None si ce n'est pas un ISBN-13 en 978)."""
    if len(isbn13) != 13 or not isbn13.startswith("978") or not isbn13.isdigit():
        return None
    base = isbn13[3:12]
    total = sum(int(c) * (10 - n) for n, c in enumerate(base))
    reste = (11 - total % 11) % 11
    return base + ("X" if reste == 10 else str(reste))


def chercher_isbn_secours(isbn):
    """Appelée quand Google Books ne trouve rien : BnF (ISBN-13 puis ISBN-10), puis Open Library."""
    isbn_net = re.sub(r"[^0-9Xx]", "", isbn)
    if not isbn_net:
        return None

    resultat = chercher_isbn_bnf(isbn_net)
    if not resultat:
        isbn10 = isbn13_vers_10(isbn_net)
        if isbn10:
            resultat = chercher_isbn_bnf(isbn10)
    if not resultat:
        resultat = chercher_isbn_openlibrary(isbn_net)

    if resultat:
        resultat["isbn"] = isbn_net  # on garde l'ISBN saisi ou scanné
    return resultat
