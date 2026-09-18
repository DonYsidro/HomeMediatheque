from flask import Flask, render_template, request, redirect, url_for, make_response
from database import get_db
from translations import TRANSLATIONS

app = Flask(__name__)


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
    reponse.set_cookie("lang", code, max_age=60 * 60 * 24 * 365)
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


from routes.films import films_bp
from routes.cds import cds_bp
from routes.livres import livres_bp
from routes.bd_mangas import bd_bp
from routes.api_externes import api_bp
from routes.sauvegarde import sauvegarde_bp

app.register_blueprint(films_bp)
app.register_blueprint(cds_bp)
app.register_blueprint(livres_bp)
app.register_blueprint(bd_bp)
app.register_blueprint(api_bp)
app.register_blueprint(sauvegarde_bp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
