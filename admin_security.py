from functools import wraps

from flask import redirect, url_for, session, request


def admin_requis(vue):
    """Réserve une route aux sessions administrateur authentifiées."""
    @wraps(vue)
    def wrapper(*args, **kwargs):
        if not session.get("admin_connecte"):
            return redirect(
                url_for("admin.connexion", next=request.path)
            )
        return vue(*args, **kwargs)

    return wrapper
