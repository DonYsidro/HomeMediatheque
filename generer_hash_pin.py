import base64
import getpass
import hashlib
import hmac
import secrets

def encoder(data):
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

pin = getpass.getpass("Nouveau PIN administrateur : ")
confirmation = getpass.getpass("Confirmer le PIN : ")

if not pin:
    raise SystemExit("Erreur : le PIN ne peut pas être vide.")

if not hmac.compare_digest(pin, confirmation):
    raise SystemExit("Erreur : les deux PIN ne correspondent pas.")

sel = secrets.token_bytes(16)
derive = hashlib.scrypt(
    pin.encode("utf-8"),
    salt=sel,
    n=16384,
    r=8,
    p=1,
    dklen=32,
)

print("\nValeur à enregistrer dans ADMIN_PIN_HASH :")
print(f"scrypt$16384$8$1${encoder(sel)}${encoder(derive)}")
