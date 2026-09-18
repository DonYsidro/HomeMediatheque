import os
import uuid
from flask import request


def sauvegarder_photo_upload(fichier):
    if fichier and fichier.filename:
        extension = os.path.splitext(fichier.filename)[1].lower()
        nom_unique = f"{uuid.uuid4().hex}{extension}"
        dossier = os.path.join("static", "uploads")
        os.makedirs(dossier, exist_ok=True)
        fichier.save(os.path.join(dossier, nom_unique))
        return f"/static/uploads/{nom_unique}"
    return None


def valeur_image(champ_nom):
    photo = sauvegarder_photo_upload(request.files.get("photo"))
    if photo:
        return photo
    return request.form.get(champ_nom) or None
