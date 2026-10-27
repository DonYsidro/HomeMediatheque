from flask import Blueprint, render_template, request, redirect, url_for, session

from admin_auth import (
    verifier_pin,
    blocage_actif,
    enregistrer_echec,
    reinitialiser_echecs,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/connexion", methods=["GET", "POST"])
def connexion():
    if session.get("admin_connecte"):
        return redirect(url_for("index"))

    if request.method == "POST":
        if blocage_actif():
            return render_template(
                "admin_connexion.html",
                erreur="L'accès administrateur est temporairement bloqué. Réessayez plus tard.",
            ), 429

        pin = request.form.get("pin", "")

        if verifier_pin(pin):
            reinitialiser_echecs()
            session.clear()
            session["admin_connecte"] = True
            session["admin_derniere_activite"] = __import__("time").time()
            session.permanent = True
            return redirect(url_for("index"))

        resultat = enregistrer_echec()

        if resultat["blocked"]:
            erreur = (
                f"Trop de tentatives incorrectes. "
                f"Réessayez dans {resultat['minutes']} minute(s)."
            )
        else:
            erreur = "PIN incorrect."

        return render_template(
            "admin_connexion.html",
            erreur=erreur,
        ), 401

    return render_template("admin_connexion.html")


@admin_bp.route("/deconnexion", methods=["POST"])
def deconnexion():
    session.clear()
    return redirect(url_for("index"))
