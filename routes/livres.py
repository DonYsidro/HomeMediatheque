from flask import Blueprint, render_template, request, redirect, url_for
from database import get_db
from utils import valeur_image

livres_bp = Blueprint("livres", __name__, url_prefix="/livres")


@livres_bp.route("")
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


@livres_bp.route("/serie")
def livres_serie_detail():
    serie = request.args.get("serie", "")
    conn = get_db()
    tomes = conn.execute(
        "SELECT * FROM livres WHERE serie = ? ORDER BY numero_tome", (serie,)
    ).fetchall()
    conn.close()
    return render_template("livres_serie_detail.html", tomes=tomes, serie=serie)


@livres_bp.route("/ajouter", methods=["GET", "POST"])
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
        return redirect(url_for(".livres"))
    conn.close()
    return render_template("ajouter_livre.html")


@livres_bp.route("/modifier/<int:livre_id>", methods=["GET", "POST"])
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
        return redirect(url_for(".livres"))
    livre = conn.execute("SELECT * FROM livres WHERE id = ?", (livre_id,)).fetchone()
    conn.close()
    return render_template("modifier_livre.html", livre=livre)


@livres_bp.route("/supprimer/<int:livre_id>", methods=["POST"])
def supprimer_livre(livre_id):
    conn = get_db()
    conn.execute("DELETE FROM livres WHERE id = ?", (livre_id,))
    conn.commit()
    conn.close()
    return redirect(url_for(".livres"))


@livres_bp.route("/voir/<int:livre_id>")
def voir_livre(livre_id):
    conn = get_db()
    livre = conn.execute("SELECT * FROM livres WHERE id = ?", (livre_id,)).fetchone()
    conn.close()
    return render_template("voir_livre.html", livre=livre)
