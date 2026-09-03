# 🎬 HomeMediatheque

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

Application web familiale (Flask + SQLite, dockerisée) pour cataloguer une collection de films, séries, CD, livres et BD/manga.

*A dockerized Flask/SQLite family web app to catalog a collection of movies, TV shows, CDs, books, and comics/manga.*

---

## 🇫🇷 Français

### Fonctionnalités

- 4 catégories : Films & Séries, CD Audio, Livres, BD & Manga
- Recherche multi-critères (âge, genre, type, durée, lieu de stockage...)
- Remplissage automatique des fiches via TMDB (films/séries), MusicBrainz (CD), Google Books (livres/BD/manga)
- Scan de code-barres (ISBN) via la caméra pour les livres/BD/manga
- Regroupement par coffret (films), série (livres/BD), artiste (CD)
- Suivi des prêts (à qui, depuis quand)
- Photos personnalisées (prise directe ou import) en plus des couvertures/affiches trouvées en ligne
- Export/import complet (JSON + photos) et export CSV pour consultation/modification dans un tableur
- Interface bilingue Français/Anglais
- HTTPS auto-signé (nécessaire pour l'accès caméra depuis un mobile)

### Prérequis

- Docker et Docker Compose installés
- Une clé API [TMDB](https://www.themoviedb.org/settings/api) (gratuite)
- Une clé API [Google Books](https://console.cloud.google.com/) (gratuite — activer "Books API" dans un projet Google Cloud, puis créer une clé dans Identifiants)

### Installation

**1. Cloner le dépôt**
```bash
git clone git@github.com:DonYsidro/HomeMediatheque.git
cd HomeMediatheque
```

**2. Configurer les clés API**
```bash
cp .env.example .env
nano .env
```
Renseigne `TMDB_API_KEY` et `GOOGLEBOOKS_API_KEY` avec tes vraies clés.

**3. Générer un certificat HTTPS auto-signé**
```bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes -keyout certs/key.pem -out certs/cert.pem -subj "/CN=mediatheque" -addext "subjectAltName=IP:TON_IP_LOCALE"
chmod 600 certs/key.pem
```
Remplace `TON_IP_LOCALE` par l'adresse IP locale de la machine qui hébergera l'application (ex: `192.168.1.71`).

**4. Créer le dossier des photos uploadées**
```bash
mkdir -p static/uploads
```

**5. Lancer l'application**
```bash
docker compose up -d --build
```

**6. Accéder à l'application**

Depuis un navigateur, sur la même IP que celle utilisée pour le certificat : https://TON_IP_LOCALE:5000

Le navigateur affichera un avertissement de sécurité (certificat auto-signé) — c'est normal, accepte-le pour continuer.

### Sauvegarde et restauration

Tout se fait depuis l'interface, page **Sauvegarde** (accessible depuis le bandeau) :
- **Export JSON** : sauvegarde complète (données + photos), à utiliser pour tout restaurer.
- **Export CSV** : pour consulter/modifier en masse dans Excel/LibreOffice, puis réimporter les changements.

### Mettre à jour l'application

Après avoir modifié le code :
```bash
docker compose up -d --build
```
Les données (`mediatheque.db`, `static/uploads/`, `certs/`) sont montées en volumes et ne sont jamais perdues lors d'une reconstruction.

### Stack technique

Python / Flask / SQLite / Gunicorn / Docker · APIs externes : TMDB, MusicBrainz, Cover Art Archive, Google Books

---

## 🇬🇧 English

### Features

- 4 categories: Movies & TV Shows, Music CDs, Books, Comics & Manga
- Multi-criteria search (age rating, genre, type, duration, storage location...)
- Auto-fill via TMDB (movies/TV), MusicBrainz (CDs), Google Books (books/comics/manga)
- Barcode (ISBN) scanning via camera for books/comics/manga
- Grouping by box set (movies), series (books/comics), artist (CDs)
- Loan tracking (who, since when)
- Custom photos (camera capture or upload) alongside online covers/posters
- Full export/import (JSON + photos) and CSV export for spreadsheet editing
- Bilingual French/English interface
- Self-signed HTTPS (required for camera access on mobile)

### Requirements

- Docker and Docker Compose installed
- A [TMDB](https://www.themoviedb.org/settings/api) API key (free)
- A [Google Books](https://console.cloud.google.com/) API key (free — enable "Books API" in a Google Cloud project, then create a key under Credentials)

### Installation

**1. Clone the repository**
```bash
git clone git@github.com:DonYsidro/HomeMediatheque.git
cd HomeMediatheque
```

**2. Configure API keys**
```bash
cp .env.example .env
nano .env
```
Fill in `TMDB_API_KEY` and `GOOGLEBOOKS_API_KEY` with your real keys.

**3. Generate a self-signed HTTPS certificate**
```bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes -keyout certs/key.pem -out certs/cert.pem -subj "/CN=mediatheque" -addext "subjectAltName=IP:YOUR_LOCAL_IP"
chmod 600 certs/key.pem
```
Replace `YOUR_LOCAL_IP` with the local IP address of the machine hosting the app (e.g. `192.168.1.71`).

**4. Create the uploads folder**
```bash
mkdir -p static/uploads
```

**5. Run the application**
```bash
docker compose up -d --build
```

**6. Access the application**

From a browser, using the same IP as the certificate: https://YOUR_LOCAL_IP:5000

The browser will show a security warning (self-signed certificate) — this is expected, accept it to continue.

### Backup and restore

Everything is handled from the **Backup** page in the app's header:
- **JSON export**: full backup (data + photos), used to restore everything.
- **CSV export**: for bulk viewing/editing in Excel/LibreOffice, then re-import the changes.

### Updating the application

After modifying the code:
```bash
docker compose up -d --build
```
Data (`mediatheque.db`, `static/uploads/`, `certs/`) is mounted as volumes and is never lost on rebuild.

### Tech stack

Python / Flask / SQLite / Gunicorn / Docker · External APIs: TMDB, MusicBrainz, Cover Art Archive, Google Books

---

## Licence / License

Ce projet est sous licence MIT — voir le fichier [LICENSE](LICENSE) pour le texte complet. En résumé : libre d'utilisation, de modification et de redistribution, y compris à des fins commerciales, à condition de conserver la mention de copyright d'origine.

*This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for the full text. In short: free to use, modify, and redistribute, including for commercial purposes, provided the original copyright notice is retained.*
