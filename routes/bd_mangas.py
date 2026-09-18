from flask import Blueprint, render_template, request, redirect, url_for
from database import get_db
from utils import valeur_image

bd_bp = Blueprint("bd_mangas", __name__, url_prefix="/bd-mangas")


@bd_bp.route("")
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


@bd_bp.route("/serie")
def bd_serie_detail():
    serie = request.args.get("serie", "")
    conn = get_db()
    tomes = conn.execute(
        "SELECT * FROM bd_mangas WHERE COALESCE(serie, titre) = ? ORDER BY numero_tome", (serie,)
    ).fetchall()
    conn.close()
    return render_template("bd_serie_detail.html", tomes=tomes, serie=serie)


@bd_bp.route("/ajouter", methods=["GET", "POST"])
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
        return redirect(url_for(".bd_mangas"))
    conn.close()
    return render_template("ajouter_bd.html")


@bd_bp.route("/modifier/<int:item_id>", methods=["GET", "POST"])
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
        return redirect(url_for(".bd_mangas"))
    item = conn.execute("SELECT * FROM bd_mangas WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    return render_template("modifier_bd.html", item=item)


@bd_bp.route("/supprimer/<int:item_id>", methods=["POST"])
def supprimer_bd(item_id):
    conn = get_db()
    conn.execute("DELETE FROM bd_mangas WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for(".bd_mangas"))


@bd_bp.route("/voir/<int:item_id>")
def voir_bd(item_id):
    conn = get_db()
    item = conn.execute("SELECT * FROM bd_mangas WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    return render_template("voir_bd.html", item=item)
