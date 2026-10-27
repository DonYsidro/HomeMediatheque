# 🎬 HomeMediatheque

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

Application web familiale basée sur Flask et SQLite, conteneurisée avec Docker, pour cataloguer une collection de films, séries, CD audio, livres et BD/manga.

*A Dockerized Flask/SQLite family web application for cataloguing movies, TV shows, music CDs, books, and comics/manga.*

---

## 🇫🇷 Français

### Fonctionnalités

- Quatre catégories : Films & Séries, CD Audio, Livres, BD & Manga.
- Recherche multicritère : âge, genre, type, durée, lieu de stockage, etc.
- Remplissage automatique des fiches grâce à TMDB, Discogs et Google Books.
- Lecture des codes-barres via la caméra : ISBN pour les livres et BD/manga, code-barres produit pour les CD.
- Classification des films et séries : films, séries, animation et animés japonais.
- Regroupement par série pour les films, livres et BD/manga, et par artiste pour les CD.
- Suivi des prêts : emprunteur et date du prêt.
- Ajout de photos personnalisées par prise de vue ou import.
- Export et import JSON avec photos, ainsi qu'export et import CSV.
- Interface bilingue français/anglais.
- Connexion administrateur protégée par PIN.
- Limitation progressive des tentatives de connexion incorrectes.
- HTTPS avec certificat auto-signé pour permettre notamment l'accès à la caméra depuis un mobile sur le réseau local.

### Prérequis

- Linux ou un autre système compatible avec Docker.
- Docker Engine et Docker Compose v2.
- Python 3 pour les commandes locales de génération des secrets.
- OpenSSL pour générer le certificat HTTPS.
- Des clés API pour les fonctions de recherche externe :
  - [TMDB](https://www.themoviedb.org/settings/api) pour les films et séries.
  - [Google Books](https://console.cloud.google.com/) pour les livres et BD/manga.
  - [Discogs](https://www.discogs.com/settings/developers) pour les CD audio.

Les clés API doivent être obtenues auprès des services concernés. Leur disponibilité peut conditionner les fonctions de recherche automatique correspondantes.

### Installation

#### 1. Cloner le dépôt

```bash
git clone git@github.com:DonYsidro/HomeMediatheque.git
cd HomeMediatheque
```

Le clonage SSH nécessite que ta clé SSH soit configurée sur GitHub. Tu peux également utiliser l'URL HTTPS du dépôt.

#### 2. Créer et configurer le fichier d'environnement

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Renseigne les variables suivantes :

| Variable | Description |
| --- | --- |
| `TMDB_API_KEY` | Clé API TMDB |
| `GOOGLEBOOKS_API_KEY` | Clé API Google Books |
| `DISCOGS_TOKEN` | Jeton Discogs |
| `SECRET_KEY` | Clé secrète Flask propre à cette installation |
| `ADMIN_PIN_HASH` | Hash scrypt du PIN administrateur |
| `ADMIN_SESSION_MINUTES` | Durée de validité de la session administrateur, en minutes |
| `SESSION_COOKIE_SECURE` | `true` si l'application est utilisée en HTTPS |

Génère une clé Flask aléatoire :

```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

Copie le résultat dans `SECRET_KEY` dans `.env`. Génère une nouvelle clé pour chaque installation et ne la publie pas.

#### 3. Créer le PIN administrateur

Le dépôt contient le script `generer_hash_pin.py`. Il demande le PIN deux fois et affiche son hash scrypt, sans enregistrer le PIN en clair.

```bash
python3 generer_hash_pin.py
```

Copie la valeur complète produite par le script dans `ADMIN_PIN_HASH` dans `.env`. Ne remplace pas cette valeur par le PIN lui-même.

Le hash est un secret de configuration : ne le publie pas et ne le communique pas. Le PIN ne doit jamais être inscrit dans le code source.

#### 4. Générer le certificat HTTPS

Crée un certificat auto-signé adapté à l'adresse IP locale de ton serveur :

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
  -keyout certs/key.pem \
  -out certs/cert.pem \
  -subj "/CN=mediatheque" \
  -addext "subjectAltName=IP:TON_IP_LOCALE"
chmod 600 certs/key.pem
```

Remplace `TON_IP_LOCALE` par l'adresse IP locale du serveur, par exemple `192.168.1.50`. Utilise l'adresse correspondant à ton réseau.

Un certificat auto-signé déclenche un avertissement du navigateur car il n'est pas signé par une autorité de certification reconnue. Il est destiné à un usage local ou de test, pas à exposer directement l'application sur Internet.

#### 5. Préparer les dossiers persistants

```bash
mkdir -p data static/uploads certs
```

Les dossiers `data/` et `static/uploads/` contiennent respectivement la base SQLite et les photos importées ou ajoutées. Le dossier `certs/` contient les fichiers du certificat HTTPS.

#### 6. Démarrer l'application

Depuis le répertoire du projet, lance :

```bash
docker compose up -d --build
```

Vérifie l'état du conteneur :

```bash
docker compose ps
docker compose logs --tail 50
```

#### 7. Accéder à l'application

Dans un navigateur, ouvre :

```text
https://TON_IP_LOCALE:5000
```

Utilise la même adresse IP que celle indiquée dans le certificat. Selon le navigateur, tu devras accepter l'avertissement lié au certificat auto-signé.

### Administration et sécurité

- La page de connexion administrateur est accessible à `/admin/connexion`.
- La déconnexion est effectuée via `/admin/deconnexion`.
- Les fonctions de modification et les opérations sensibles protégées par l'application nécessitent une session administrateur.
- Le PIN est vérifié à partir de son hash scrypt ; il n'est pas nécessaire de stocker le PIN en clair.
- Après plusieurs tentatives incorrectes, des blocages progressifs sont appliqués : 30 minutes, puis 2 heures, puis 24 heures aux paliers suivants.
- `ADMIN_SESSION_MINUTES` définit la durée de validité de la session administrateur.
- `SESSION_COOKIE_SECURE=true` doit être utilisé lorsque l'application est servie en HTTPS. En HTTP, ce paramètre empêche le navigateur d'envoyer le cookie de session.

Bonnes pratiques :

- Ne partage jamais `.env`, le PIN administrateur, `SECRET_KEY`, `ADMIN_PIN_HASH` ou la clé privée `certs/key.pem`.
- Ne publie pas la base de données, les sauvegardes ou les photos personnelles dans le dépôt Git.
- N'expose pas directement le port de l'application sur Internet sans protection adaptée. Pour un accès public, configure notamment un reverse proxy avec un certificat TLS reconnu, un pare-feu et des règles d'accès appropriées.
- Conserve une sauvegarde indépendante des données avant toute opération de maintenance importante.

### Sauvegarde et restauration

La page **Sauvegarde** de l'interface permet les opérations d'export et d'import disponibles dans l'application :

- **JSON** : export et import des données avec les photos.
- **CSV** : export et import pour consulter ou modifier des données dans un tableur compatible, selon les fonctions prises en charge par l'application.

Conserve les fichiers exportés dans un emplacement sûr, en dehors du dépôt Git. Avant une restauration, vérifie le fichier choisi et garde une sauvegarde récente de la base et des photos.

### Mise à jour de l'application

Après avoir récupéré ou modifié le code, place-toi dans le répertoire du projet puis exécute :

```bash
docker compose up -d --build
```

Cette commande reconstruit l'image et recrée les services si nécessaire. Elle peut interrompre brièvement l'accès à l'application.

Les répertoires `data/`, `static/uploads/` et `certs/` sont montés dans le conteneur par le fichier Compose ; ils sont conservés lors d'une reconstruction normale. Cela ne remplace pas une sauvegarde. Vérifie toujours le fichier Compose et l'état des volumes avant une opération de maintenance.

### Stack technique

Python, Flask, SQLite, Gunicorn, Docker Compose, TMDB, Discogs et Google Books.

---

## 🇬🇧 English

### Features

- Four categories: Movies & TV Shows, Music CDs, Books, Comics & Manga.
- Multi-criteria search: age rating, genre, type, duration, storage location, and more.
- Automatic metadata lookup through TMDB, Discogs, and Google Books.
- Camera barcode scanning: ISBN for books and comics/manga, product barcodes for CDs.
- Movie and TV classification: movies, TV shows, animation, and Japanese anime.
- Grouping by series for movies, books, and comics/manga, and by artist for CDs.
- Loan tracking: borrower and loan date.
- Custom photos captured with a camera or uploaded.
- JSON export/import with photos, plus CSV export/import.
- French and English interface.
- PIN-protected administrator login.
- Progressive lockouts after repeated incorrect login attempts.
- HTTPS with a self-signed certificate, including for camera access from a mobile device on the local network.

### Requirements

- Linux or another operating system supported by Docker.
- Docker Engine and Docker Compose v2.
- Python 3 for local secret-generation commands.
- OpenSSL to create the HTTPS certificate.
- API credentials for external metadata lookups:
  - [TMDB](https://www.themoviedb.org/settings/api) for movies and TV shows.
  - [Google Books](https://console.cloud.google.com/) for books and comics/manga.
  - [Discogs](https://www.discogs.com/settings/developers) for music CDs.

Obtain API credentials from the relevant providers. Availability of these credentials may affect the corresponding metadata lookup features.

### Installation

#### 1. Clone the repository

```bash
git clone git@github.com:DonYsidro/HomeMediatheque.git
cd HomeMediatheque
```

SSH cloning requires an SSH key configured with GitHub. You can also use the repository's HTTPS clone URL.

#### 2. Create and configure the environment file

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Configure these variables:

| Variable | Description |
| --- | --- |
| `TMDB_API_KEY` | TMDB API key |
| `GOOGLEBOOKS_API_KEY` | Google Books API key |
| `DISCOGS_TOKEN` | Discogs token |
| `SECRET_KEY` | Flask secret key unique to this installation |
| `ADMIN_PIN_HASH` | scrypt hash of the administrator PIN |
| `ADMIN_SESSION_MINUTES` | Administrator session lifetime, in minutes |
| `SESSION_COOKIE_SECURE` | Set to `true` when the application uses HTTPS |

Generate a random Flask secret key:

```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

Copy the output into `SECRET_KEY` in `.env`. Generate a unique key for each installation and do not publish it.

#### 3. Create the administrator PIN hash

The repository includes `generer_hash_pin.py`. It prompts for the PIN twice and prints a scrypt hash without storing the PIN in plaintext.

```bash
python3 generer_hash_pin.py
```

Copy the complete output into `ADMIN_PIN_HASH` in `.env`. Do not put the PIN itself in this variable.

Treat the hash as a secret configuration value. Never publish or share it, and never put the PIN in the source code.

#### 4. Generate an HTTPS certificate

Create a self-signed certificate for your server's local IP address:

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
  -keyout certs/key.pem \
  -out certs/cert.pem \
  -subj "/CN=mediatheque" \
  -addext "subjectAltName=IP:YOUR_LOCAL_IP"
chmod 600 certs/key.pem
```

Replace `YOUR_LOCAL_IP` with the server's local IP address, for example `192.168.1.50`, using the address appropriate for your network.

A self-signed certificate triggers a browser warning because it is not issued by a trusted certificate authority. It is intended for local or test use, not for directly exposing the application to the Internet.

#### 5. Prepare persistent directories

```bash
mkdir -p data static/uploads certs
```

`data/` contains the SQLite database, `static/uploads/` contains added or imported photos, and `certs/` contains the HTTPS certificate files.

#### 6. Start the application

From the project directory, run:

```bash
docker compose up -d --build
```

Check the container status:

```bash
docker compose ps
docker compose logs --tail 50
```

#### 7. Access the application

Open the following address in a browser:

```text
https://YOUR_LOCAL_IP:5000
```

Use the same IP address included in the certificate. Depending on the browser, you will need to accept the warning for the self-signed certificate.

### Administration and security

- The administrator login page is available at `/admin/connexion`.
- Log out through `/admin/deconnexion`.
- Protected editing functions and sensitive operations require an administrator session.
- The PIN is checked against a scrypt hash; storing the PIN in plaintext is not required.
- Repeated incorrect attempts trigger progressive lockouts: 30 minutes, then 2 hours, then 24 hours at subsequent levels.
- `ADMIN_SESSION_MINUTES` sets the administrator session lifetime.
- Set `SESSION_COOKIE_SECURE=true` when the application is served over HTTPS. Over HTTP, this setting prevents the browser from sending the session cookie.

Best practices:

- Never share `.env`, the administrator PIN, `SECRET_KEY`, `ADMIN_PIN_HASH`, or the private key `certs/key.pem`.
- Do not commit the database, backups, or personal photos to Git.
- Do not expose the application port directly to the Internet without appropriate safeguards. Public access requires suitable protection, including a reverse proxy with a trusted TLS certificate, a firewall, and appropriate access rules.
- Keep an independent backup of your data before significant maintenance.

### Backup and restore

The application's **Backup** page provides the available export and import operations:

- **JSON**: export and import data with photos.
- **CSV**: export and import for spreadsheet viewing or editing, subject to the application's supported functionality.

Keep exported files in a safe location outside the Git repository. Before restoring, verify the selected file and retain a recent backup of the database and photos.

### Updating the application

After retrieving or modifying the code, change to the project directory and run:

```bash
docker compose up -d --build
```

This rebuilds the image and recreates services when necessary. Access to the application may be interrupted briefly.

The `data/`, `static/uploads/`, and `certs/` directories are mounted into the container by the Compose file and are preserved during a normal rebuild. This is not a substitute for backups. Always check the Compose configuration and volume status before maintenance.

### Tech stack

Python, Flask, SQLite, Gunicorn, Docker Compose, TMDB, Discogs, and Google Books.

---

## Licence / License

Ce projet est distribué sous licence MIT. Consulte le fichier [LICENSE](LICENSE) pour le texte complet.

This project is distributed under the MIT License. See [LICENSE](LICENSE) for the full license text.
