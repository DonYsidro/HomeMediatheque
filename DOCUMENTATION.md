# Documentation complète — HomeMediatheque

Document de référence pour comprendre, reconstruire ou faire évoluer le projet. Complète le `README.md` (notice d'installation rapide) avec le détail technique et les décisions prises au fil du développement.

---

## 1. Vue d'ensemble

Application web familiale (Flask + SQLite, dockerisée) permettant de cataloguer une collection physique de films/séries, CD, livres et BD/manga, consultable depuis n'importe quel appareil du réseau local (PC, smartphone, tablette).

**Objectifs de conception** :
- Rester simple à comprendre et modifier (pas de framework lourd type Django)
- Fonctionner entièrement en local, sans dépendance cloud pour les données
- S'enrichir automatiquement via des APIs externes gratuites plutôt que tout saisir à la main

---

## 2. Architecture technique

### Stack
- **Backend** : Python 3.11 / Flask, servi par Gunicorn (2 workers)
- **Base de données** : SQLite (fichier unique `mediatheque.db`)
- **Frontend** : templates Jinja2 (HTML/CSS/JS), pas de framework JS
- **Conteneurisation** : Docker + Docker Compose
- **HTTPS** : certificat auto-signé (nécessaire pour l'accès caméra sur mobile)

### Structure des fichiers (après réorganisation en blueprints)
mediatheque/
├── app.py # Point d'entrée : création de l'app, traductions, route d'accueil, enregistrement des blueprints
├── config.py # Chargement des clés API depuis .env
├── utils.py # Fonctions partagées (upload photo, résolution image url/fichier)
├── database.py # Connexion SQLite (get_db)
├── translations.py # Dictionnaire de traductions FR/EN
├── schema.sql # Définition des tables
├── requirements.txt # Dépendances Python
├── Dockerfile
├── docker-compose.yml
├── .env # Clés API (jamais commité, voir .gitignore)
├── .env.example # Modèle sans vraies clés
├── routes/
│ ├── films.py # /films, /ajouter, /modifier, /supprimer, /recherche, /voir
│ ├── cds.py # /cds, /cds/artiste, /cds/ajouter, /cds/modifier, /cds/supprimer, /cds/voir
│ ├── livres.py # /livres, /livres/serie, /livres/ajouter, /livres/modifier, /livres/supprimer, /livres/voir
│ ├── bd_mangas.py # /bd-mangas, /bd-mangas/serie, /bd-mangas/ajouter, /bd-mangas/modifier, /bd-mangas/supprimer, /bd-mangas/voir
│ ├── api_externes.py # /api/tmdb_, /api/discogs_, /api/googlebooks_*
│ └── sauvegarde.py # /sauvegarde, /sauvegarde/export., /sauvegarde/importer
├── templates/ # Un couple ajouter_X.html / modifier_X.html / voir_X.html par catégorie
├── static/
│ ├── style.css
│ └── uploads/ # Photos prises/importées par l'utilisateur (jamais commité)
└── certs/ # Certificat HTTPS auto-signé (jamais commité)


### Pourquoi des Blueprints Flask

`app.py` dépassait 1100 lignes en mélangeant toutes les catégories. Les Blueprints permettent de séparer chaque catégorie dans son propre fichier, avec ses propres routes, tout en partageant les utilitaires communs (`get_db`, `valeur_image`). Chaque blueprint est enregistré dans `app.py` via `app.register_blueprint(...)`. Les URLs n'ont pas changé lors de cette réorganisation — c'est un déplacement de code, pas un changement de comportement.

---

## 3. Base de données

### Tables principales

- **`medias`** : films, séries, coffrets. Un coffret est une entrée `type='coffret'` ; les films qu'il contient pointent vers lui via `coffret_id`.
- **`genres`** / **`medias_genres`** : relation many-to-many (un film peut avoir plusieurs genres)
- **`personnes`** / **`medias_personnes`** : réalisateurs/acteurs/compositeurs, avec un rôle par ligne de liaison
- **`cds`** : albums, avec regroupement par `artiste` calculé à l'affichage (pas de table séparée)
- **`livres`** : romans/collections/cuisine/éducatif, avec `serie` + `numero_tome` optionnels pour le regroupement
- **`bd_mangas`** : BD et mangas, `serie` obligatoire (distincte du `titre` du tome pour permettre le regroupement même si le titre du tome varie)

### Champs communs à toutes les catégories de médias
`lieu_stockage`, `est_prete`, `prete_a`, `date_pret` (suivi des prêts), `date_ajout`.

### Modifier le schéma plus tard
Toujours utiliser `ALTER TABLE ... ADD COLUMN` sur la base existante (`docker compose exec mediatheque python3 -c "..."`), **et** reporter le changement dans `schema.sql` pour qu'une réinstallation from scratch inclue la colonne dès le départ. Les deux étapes sont nécessaires — l'une ne remplace pas l'autre.

---

## 4. APIs externes utilisées

| Service | Usage | Clé requise | Limite connue |
|---|---|---|---|
| **TMDB** | Films/séries : métadonnées + affiches | Oui (gratuite) | Généreuse, peu de soucis observés |
| **Discogs** | CD : métadonnées, pistes, pochettes, recherche par code-barre | Oui (token personnel gratuit) | ~60 req/min avec token |
| **Google Books** | Livres/BD/Manga : métadonnées, couvertures, recherche par ISBN | Oui (gratuite, mais **doit être activée** dans Google Cloud Console sinon quota à 0) | Généreuse |
| ~~MusicBrainz~~ | *Abandonné* — remplacé par Discogs | — | 1 requête/seconde, trop restrictif, causait des échecs fréquents |

### Où récupérer chaque clé
- TMDB : https://www.themoviedb.org/settings/api
- Discogs : https://www.discogs.com/settings/developers → "Generate new token"
- Google Books : console Google Cloud → activer "Books API" → créer une clé API dans Identifiants (**l'activation explicite de l'API est indispensable**, sinon la clé a un quota de 0 requête/jour)

### Toujours utiliser un `timeout`
Chaque appel `requests.get(...)` vers une API externe **doit** avoir un `timeout=10`. Sans ça, un appel qui traîne peut faire dépasser la limite interne de Gunicorn et tuer le worker (`SystemExit`), ce qui coupe l'appli pour tout le monde jusqu'au redémarrage automatique.

---

## 5. Variables d'environnement (`.env`)
TMDB_API_KEY=...
GOOGLEBOOKS_API_KEY=...
DISCOGS_TOKEN=...

Le fichier `.env.example` sert de modèle (sans vraies valeurs) pour toute réinstallation ou publication.

---

## 6. Docker

### Fichiers clés
- **`Dockerfile`** : image `python:3.11-slim`, installe `requirements.txt`, copie le code, lance Gunicorn avec HTTPS.
- **`docker-compose.yml`** : monte en volumes `mediatheque.db`, `static/uploads/`, `certs/` — ces trois éléments **survivent** à une reconstruction de l'image (`docker compose up -d --build`), car ils ne sont jamais copiés dans l'image elle-même (exclus via `.dockerignore`).

### Cycle de mise à jour du code
```bash
# après avoir modifié app.py, un template, etc.
docker compose up -d --build
```

### Déplacer l'application vers un autre serveur
1. Copier tout le dossier du projet **avec** `mediatheque.db`, `static/uploads/`, `certs/`, `.env` (ces 4 éléments ne sont pas dans Git, il faut les transférer à la main — `scp` ou via le NAS)
2. Régénérer le certificat HTTPS avec la nouvelle IP (voir section 7)
3. `docker compose up -d --build` sur la nouvelle machine

---

## 7. HTTPS (certificat auto-signé)

Nécessaire uniquement pour que la caméra du téléphone soit autorisée par le navigateur (contrainte de sécurité des navigateurs, pas de l'application elle-même).

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
  -keyout certs/key.pem -out certs/cert.pem \
  -subj "/CN=mediatheque" -addext "subjectAltName=IP:TON_IP_LOCALE"
chmod 600 certs/key.pem
```
**Le certificat est lié à une IP précise.** Si l'IP du serveur change, il faut le régénérer, sinon le navigateur refusera la connexion.

Chaque appareil de la famille doit accepter l'avertissement de sécurité **une seule fois** (certificat non reconnu par une autorité officielle, normal pour un usage local).

---

## 8. Reconstruction complète depuis zéro

1. Cloner le dépôt : `git clone git@github.com:DonYsidro/HomeMediatheque.git`
2. Créer `.env` à partir de `.env.example`, renseigner les 3 clés API
3. Générer le certificat HTTPS (section 7)
4. Créer le dossier des uploads : `mkdir -p static/uploads`
5. Lancer : `docker compose up -d --build`
6. Accéder via `https://IP_DU_SERVEUR:5000`, accepter le certificat

**Si tu as une sauvegarde JSON** (section 9), tu peux restaurer toutes les données immédiatement après l'étape 5, avant même d'utiliser l'appli, via la page `/sauvegarde`.

---

## 9. Sauvegarde et restauration

Tout se passe depuis la page **Sauvegarde**, accessible en permanence dans le bandeau :

- **Export JSON** : sauvegarde complète (toutes les tables + toutes les photos uploadées, zippées ensemble). C'est LE fichier à garder précieusement et à utiliser pour tout reconstruire.
- **Export CSV** : une table = un fichier CSV dans un zip, pour consultation/modification en masse dans Excel/LibreOffice.
- **Restauration JSON** : remplace **entièrement** les données actuelles par celles du fichier importé (irréversible, une confirmation est demandée).
- **Mise à jour en masse (CSV)** : met à jour uniquement les lignes dont l'`id` existe déjà dans le CSV réimporté — n'ajoute ni ne supprime rien. Pratique pour corriger un champ en masse (ex: renommer un éditeur partout) sans tout réexporter/réimporter.

---

## 10. Fonctionnalités par catégorie

### Films & Séries
Recherche auto via TMDB, genres/réalisateurs/acteurs/compositeurs en relations many-to-many, gestion de coffrets (un coffret = une entrée, les films qu'il contient y sont rattachés individuellement), recherche multi-critères dédiée (`/recherche`).

### CD Audio
Recherche auto via Discogs (titre+artiste, ou code-barre), scan caméra du code-barre, liste des pistes, regroupement automatique par artiste sur la page principale.

### Livres
4 sous-types (roman / collection / cuisine / éducatif), recherche auto via Google Books (titre ou ISBN), scan caméra ISBN, regroupement optionnel par série (champ `serie` + `numero_tome`) — un livre sans série renseignée reste affiché comme livre indépendant.

### BD & Manga
Même logique que Livres (Google Books, scan ISBN), mais le regroupement par série est **obligatoire** — le champ `serie` est distinct du `titre` du tome pour permettre un titre de tome différent à chaque numéro tout en gardant le regroupement cohérent.

### Toutes catégories
- Pages de consultation en lecture seule (`/voir`, `/cds/voir`, etc.) — cliquer sur une carte n'ouvre plus directement le formulaire de modification, un bouton "Modifier" dédié y accède.
- Champ photo : possibilité de prendre/importer une photo personnelle en plus (ou à la place) d'une image trouvée en ligne — stockée dans `static/uploads/`.
- Suivi des prêts (à qui, depuis quand).
- Interface bilingue FR/EN (sélecteur dans le bandeau, préférence retenue via cookie).

---

## 11. Système de traduction

`translations.py` contient un dictionnaire `TRANSLATIONS = {'fr': {...}, 'en': {...}}`. La fonction `t(cle)` est injectée automatiquement dans tous les templates via un `@app.context_processor` — pas besoin de la repasser à chaque `render_template()`.

**Piège rencontré** : les valeurs stockées en base (`type='manga'`, `sous_type='roman'`...) sont utilisées comme clés de traduction via `t('type_' + valeur)`. Si une clé `type_xxx` est absente du dictionnaire, `t()` affiche la clé brute au lieu du texte traduit (ex: "type_manga" au lieu de "Manga"). Toujours vérifier que chaque valeur possible d'un champ a sa clé `type_<valeur>` dans les deux langues après l'ajout d'un nouveau type/sous-type.

Le contenu de la collection elle-même (titres, synopsis, noms) n'est **jamais** traduit — seule l'interface (libellés, boutons) l'est.

---

## 12. Licence

Projet sous licence **MIT** (voir `LICENSE`) — libre réutilisation, modification, redistribution, y compris commerciale, à condition de conserver la mention de copyright.
