import base64
import hashlib
import hmac
import os


def verifier_pin(pin: str) -> bool:
    """Vérifie un PIN à partir de son hash scrypt stocké dans .env."""
    hash_stocke = os.environ.get("ADMIN_PIN_HASH", "")

    try:
        algorithme, n, r, p, sel_b64, derive_b64 = hash_stocke.split("$")

        if algorithme != "scrypt":
            return False

        n, r, p = int(n), int(r), int(p)

        # Refuse les paramètres inattendus ou excessifs.
        if n != 16384 or r != 8 or p != 1:
            return False

        sel = base64.urlsafe_b64decode(
            (sel_b64 + "=" * (-len(sel_b64) % 4)).encode("ascii")
        )
        derive_attendu = base64.urlsafe_b64decode(
            (derive_b64 + "=" * (-len(derive_b64) % 4)).encode("ascii")
        )

        if len(sel) != 16 or len(derive_attendu) != 32:
            return False

        derive_obtenu = hashlib.scrypt(
            pin.encode("utf-8"),
            salt=sel,
            n=n,
            r=r,
            p=p,
            dklen=len(derive_attendu),
        )

        return hmac.compare_digest(derive_obtenu, derive_attendu)

    except (ValueError, TypeError, UnicodeError):
        return False


import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from database import DATABASE


DELAIS_BLOCAGE = {
    1: 30,       # 30 minutes
    2: 120,      # 2 heures
    3: 1440,     # 24 heures
}


def _date_utc():
    """Retourne la date actuelle en UTC, au format ISO."""
    return datetime.now(timezone.utc)


def _ouvrir_db_securite():
    """Ouvre la base de l'application avec les contraintes activées."""
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def blocage_actif():
    """Indique si un blocage administrateur est toujours en cours."""
    conn = _ouvrir_db_securite()
    try:
        ligne = conn.execute(
            "SELECT locked_until FROM admin_security WHERE id = 1"
        ).fetchone()

        if ligne is None or not ligne["locked_until"]:
            return False

        fin = datetime.fromisoformat(ligne["locked_until"])
        return _date_utc() < fin
    finally:
        conn.close()


def enregistrer_echec():
    """Enregistre un échec et applique les blocages progressifs."""
    conn = _ouvrir_db_securite()
    try:
        conn.execute("BEGIN IMMEDIATE")

        ligne = conn.execute(
            """
            SELECT failed_attempts, lock_level, locked_until
            FROM admin_security
            WHERE id = 1
            """
        ).fetchone()

        if ligne is None:
            raise RuntimeError(
                "La table admin_security n'est pas initialisée."
            )

        maintenant = _date_utc()
        fin_existante = ligne["locked_until"]

        if fin_existante:
            fin = datetime.fromisoformat(fin_existante)
            if maintenant < fin:
                conn.commit()
                return {
                    "blocked": True,
                    "minutes": max(
                        1, int((fin - maintenant).total_seconds() / 60)
                    ),
                }

        echecs = ligne["failed_attempts"] + 1
        niveau = ligne["lock_level"]
        minutes = 0

        if echecs >= 3:
            niveau = min(niveau + 1, 3)
            minutes = DELAIS_BLOCAGE[niveau]
            echecs = 0

        fin_blocage = (
            (maintenant + timedelta(minutes=minutes)).isoformat()
            if minutes
            else None
        )

        conn.execute(
            """
            UPDATE admin_security
            SET failed_attempts = ?,
                lock_level = ?,
                locked_until = ?,
                last_attempt_at = ?
            WHERE id = 1
            """,
            (
                echecs,
                niveau,
                fin_blocage,
                maintenant.isoformat(),
            ),
        )
        conn.commit()

        return {
            "blocked": minutes > 0,
            "minutes": minutes,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reinitialiser_echecs():
    """Réinitialise les échecs et le palier après une connexion réussie."""
    conn = _ouvrir_db_securite()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            UPDATE admin_security
            SET failed_attempts = 0,
                lock_level = 0,
                locked_until = NULL,
                last_attempt_at = ?
            WHERE id = 1
            """,
            (_date_utc().isoformat(),),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
