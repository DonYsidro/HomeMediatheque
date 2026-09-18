from flask import Blueprint, render_template, request, redirect, url_for
from database import get_db
from utils import valeur_image

cds_bp = Blueprint("cds", __name__, url_prefix="/cds")


@cds_bp.route("")
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


@cds_bp.route("/artiste")
def cds_artiste_detail():
    artiste = request.args.get("artiste", "")
    conn = get_db()
    albums = conn.execute("SELECT * FROM cds WHERE artiste = ? ORDER BY annee, titre", (artiste,)).fetchall()
    conn.close()
    return render_template("cds_artiste_detail.html", albums=albums, artiste=artiste)


@cds_bp.route("/ajouter", methods=["GET", "POST"])
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
        return redirect(url_for(".cds"))
    conn.close()
    return render_template("ajouter_cd.html")


@cds_bp.route("/modifier/<int:cd_id>", methods=["GET", "POST"])
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
        return redirect(url_for(".cds"))
    cd = conn.execute("SELECT * FROM cds WHERE id = ?", (cd_id,)).fetchone()
    conn.close()
    return render_template("modifier_cd.html", cd=cd)


@cds_bp.route("/supprimer/<int:cd_id>", methods=["POST"])
def supprimer_cd(cd_id):
    conn = get_db()
    conn.execute("DELETE FROM cds WHERE id = ?", (cd_id,))
    conn.commit()
    conn.close()
    return redirect(url_for(".cds"))


@cds_bp.route("/voir/<int:cd_id>")
def voir_cd(cd_id):
    conn = get_db()
    cd = conn.execute("SELECT * FROM cds WHERE id = ?", (cd_id,)).fetchone()
    conn.close()
    return render_template("voir_cd.html", cd=cd)
