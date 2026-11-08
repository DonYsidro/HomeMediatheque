# Documentation complète — HomeMediatheque

Document de référence pour comprendre, reconstruire ou faire évoluer le projet. Complète le `README.md` (notice d'installation rapide) avec le détail technique et les décisions prises au fil du développement.

Quand le README et ce document se recoupent (installation, variables d'environnement, sécurité), le README fait foi pour la procédure rapide ; ce document en garde l'essentiel pour pouvoir tout reconstruire sans autre source.

---

## 1. Vue d'ensemble

Application web familiale (Flask + SQLite, dockerisée) permettant de cataloguer une collection physique de films/séries, CD, livres et BD/manga, consultable depuis n'importe quel appareil du réseau local (PC, smartphone, tablette).

**Objectifs de conception** :
- Rester simple à comprendre et modifier (pas de framework lourd type Django)
- Fonctionner entièrement en local, sans dépendance cloud pour les données
- S'enrichir automatiquement via des APIs externes gratuites plutôt que tout saisir à la main
- Laisser la consultation et la recherche ouvertes à la famille, et réserver les modifications à un administrateur protégé par un PIN

---

## 2. Architecture technique

### Stack
- **Backend** : Python 3.11 / Flask, servi par Gunicorn (2 workers)
- **Base de données** : SQLite (fichier unique `data/mediatheque.db`)
- **Frontend** : templates Jinja2 (HTML/CSS/JS), pas de framework JS
- **Protection des formulaires** : Flask-WTF (jeton CSRF sur tous les formulaires)
- **Conteneurisation** : Docker + Docker Compose
- **HTTPS** : certificat auto-signé (nécessaire pour l'accès caméra sur mobile)

### Structure des fichiers
```
HomeMediatheque/
├── app.py                # Point d'entrée : configuration Flask, session admin, traductions, accueil, blueprints
├── config.py             # Chargement des clés API depuis .env
├── utils.py              # Fonctions partagées (upload photo, résolution image url/fichier)
├── database.py           # Connexion SQLite (get_db), mise à niveau des colonnes, initialisation
├── admin_auth.py         # Vérification du PIN (hash scrypt) et blocages progressifs
├── admin_security.py     # Décorateur @admin_requis qui protège les routes de modification
├── generer_hash_pin.py   # Script local : génère le hash scrypt du PIN pour .env
├── translations.py       # Dictionnaire de traductions FR/EN
├── schema.sql            # Définition des tables
├── entrypoint.sh         # Démarrage du conteneur : initialise / met à niveau la base
├── requirements.txt      # Dépendances Python
├── Dockerfile
├── docker-compose.yml
├── .dockerignore / .gitignore
├── .env                  # Secrets et clés API (jamais commité, voir .gitignore)
├── .env.example          # Modèle sans vraies valeurs
├── README.md             # Notice d'installation rapide
├── DOCUMENTATION.md      # Ce document
├── LICENSE               # Licence MIT
├── routes/
│   ├── films.py          # /films, /films/categorie/<type>, /films/serie, /ajouter, /modifier, /supprimer, /voir
│   ├── cds.py            # /cds, /cds/artiste, /cds/ajouter, /cds/modifier, /cds/supprimer, /cds/voir
│   ├── livres.py         # /livres, /livres/serie, /livres/ajouter, /livres/modifier, /livres/supprimer, /livres/voir
│   ├── bd_mangas.py      # /bd-mangas, /bd-mangas/serie, /bd-mangas/ajouter, /bd-mangas/modifier, /bd-mangas/supprimer, /bd-mangas/voir
│   ├── recherche.py      # /chercher : recherche unique sur toutes les catégories (voir section 12)
│   ├── api_externes.py   # /api/tmdb_*, /api/discogs_*, /api/googlebooks_*
│   ├── isbn_secours.py   # Recherche ISBN de secours (BnF, Open Library) quand Google Books ne trouve rien
│   ├── sauvegarde.py     # /sauvegarde, /sauvegarde/export.*, /sauvegarde/importer
│   └── admin.py          # /admin/connexion, /admin/deconnexion
├── templates/            # Un couple ajouter_X.html / modifier_X.html / voir_X.html par catégorie,
│                         # plus recherche_globale.html et _resultats_recherche.html pour la recherche
├── static/
│   ├── style.css
│   └── uploads/          # Photos prises/importées par l'utilisateur (jamais commité)
├── data/                 # Base SQLite mediatheque.db (jamais commité, montée en volume)
└── certs/                # Certificat HTTPS auto-signé (jamais commité)
```

### Pourquoi des Blueprints Flask

`app.py` dépassait 1100 lignes en mélangeant toutes les catégories. Les Blueprints permettent de séparer chaque catégorie dans son propre fichier, avec ses propres routes, tout en partageant les utilitaires communs (`get_db`, `valeur_image`). Chaque blueprint est enregistré dans `app.py` via `app.register_blueprint(...)`. Les URLs n'ont pas changé lors de cette réorganisation — c'est un déplacement de code, pas un changement de comportement.

---

## 3. Base de données

### Tables principales

- **`medias`** : films, séries, animation et animés japonais (champ `type`). Le regroupement se fait par le champ texte `serie`. La colonne `coffret_id` n'est plus utilisée, mais elle est conservée pour rester compatible avec les anciennes données et sauvegardes.
- **`genres`** / **`medias_genres`** : relation many-to-many (un film peut avoir plusieurs genres)
- **`personnes`** / **`medias_personnes`** : réalisateurs/acteurs/compositeurs, avec un rôle par ligne de liaison
- **`cds`** : albums, avec regroupement par `artiste` calculé à l'affichage (pas de table séparée)
- **`livres`** : romans/collections/cuisine/éducatif, avec `serie` + `numero_tome` optionnels pour le regroupement
- **`bd_mangas`** : BD et mangas, `serie` obligatoire (distincte du `titre` du tome pour permettre le regroupement même si le titre du tome varie)
- **`admin_security`** : table technique à une seule ligne (`id = 1`) qui mémorise l'état des blocages de connexion administrateur (`failed_attempts`, `lock_level`, `locked_until`, `last_attempt_at`). Ce n'est pas une donnée de la collection.

### Champs communs à toutes les catégories de médias
`lieu_stockage`, `est_prete`, `prete_a`, `date_pret` (suivi des prêts), `date_ajout`.

### Initialisation et évolution du schéma
- **À chaque démarrage du conteneur**, `entrypoint.sh` exécute `python database.py`. Sur une installation neuve, la base est créée à partir de `schema.sql` ; sur une base existante, rien n'est supprimé ni écrasé.
- **Ajouter une colonne plus tard** : il suffit de la déclarer dans `schema.sql` (à un seul endroit), puis de reconstruire le conteneur. Au démarrage, `database.py` ajoute automatiquement les colonnes manquantes à la base existante, et une installation neuve les inclut dès le départ.
- Seul l'**ajout** de colonnes est automatique, et seulement si la colonne est facultative ou a une valeur par défaut : sinon un message « Attention : colonne … non ajoutée » apparaît dans `docker compose logs` et la colonne est à ajouter à la main. Renommer ou supprimer une colonne reste une opération manuelle, à faire avec une sauvegarde (export JSON) au préalable.
- Le chemin de la base peut être changé avec la variable facultative `DATABASE_PATH` (par défaut `data/mediatheque.db`).

---

## 4. APIs externes utilisées

| Service | Usage | Clé requise | Limite connue |
|---|---|---|---|
| **TMDB** | Films/séries : métadonnées + affiches | Oui (gratuite) | Généreuse, peu de soucis observés |
| **Discogs** | CD : métadonnées, pistes, pochettes, recherche par code-barre | Oui (token personnel gratuit) | ~60 req/min avec token |
| **Google Books** | Livres/BD/Manga : métadonnées, couvertures, recherche par ISBN | Oui (gratuite, mais **doit être activée** dans Google Cloud Console sinon quota à 0) | Généreuse |
| **BnF** (catalogue SRU) | Secours ISBN : éditions françaises que Google Books ne connaît pas | Non | — |
| **Open Library** | Secours ISBN et couvertures | Non | — |
| ~~MusicBrainz~~ | *Abandonné* — remplacé par Discogs | — | 1 requête/seconde, trop restrictif, causait des échecs fréquents |

### Secours ISBN
Quand Google Books ne trouve rien pour un ISBN, `routes/isbn_secours.py` interroge le catalogue de la BnF (ISBN-13, puis l'équivalent ISBN-10), puis Open Library. Aucune clé n'est nécessaire.

### Où récupérer chaque clé
- TMDB : https://www.themoviedb.org/settings/api
- Discogs : https://www.discogs.com/settings/developers → "Generate new token"
- Google Books : console Google Cloud → activer "Books API" → créer une clé API dans Identifiants (**l'activation explicite de l'API est indispensable**, sinon la clé a un quota de 0 requête/jour)

### Toujours utiliser un `timeout`
Chaque appel `requests.get(...)` vers une API externe **doit** avoir un `timeout=10`. Sans ça, un appel qui traîne peut faire dépasser la limite interne de Gunicorn et tuer le worker (`SystemExit`), ce qui coupe l'appli pour tout le monde jusqu'au redémarrage automatique.

---

## 5. Variables d'environnement (`.env`)

Le fichier `.env.example` sert de modèle (sans vraies valeurs) pour toute réinstallation ou publication.

| Variable | Description |
|---|---|
| `TMDB_API_KEY` | Clé API TMDB |
| `GOOGLEBOOKS_API_KEY` | Clé API Google Books |
| `DISCOGS_TOKEN` | Jeton Discogs |
| `SECRET_KEY` | Clé secrète Flask, propre à chaque installation. **Obligatoire : sans elle l'application ne démarre pas.** |
| `ADMIN_PIN_HASH` | Hash scrypt du PIN administrateur (jamais le PIN lui-même). Vide ou invalide : aucune connexion administrateur n'est possible. |
| `ADMIN_SESSION_MINUTES` | Durée d'inactivité après laquelle la session administrateur expire, en minutes (30 par défaut) |
| `SESSION_COOKIE_SECURE` | `true` si l'application est servie en HTTPS (cas normal ici) ; `false` par défaut |
| `DATABASE_PATH` | Facultatif : chemin personnalisé de la base SQLite |

**Générer `SECRET_KEY`** (une valeur différente par installation, à ne jamais publier) :
```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

**Générer `ADMIN_PIN_HASH`** : le script `generer_hash_pin.py` demande le PIN deux fois et affiche son hash scrypt, sans enregistrer le PIN en clair.
```bash
python3 generer_hash_pin.py
```
Copier la valeur **complète** affichée dans `ADMIN_PIN_HASH`. Le hash est un secret de configuration : ne pas le publier ni le communiquer.

Le fichier `.env.example` sert de modèle (sans vraies valeurs) pour toute réinstallation ou publication.

---

## 6. Administration et sécurité

### Ce qui est protégé
- **Réservé à l'administrateur** (décorateur `@admin_requis`) : l'ajout, la modification et la suppression de fiches dans les quatre catégories, et toute la page **Sauvegarde** (export et import).
- **Ouvert à toute personne ayant accès au réseau local** : les hubs et listes, les pages de consultation `/voir`, et la recherche. C'est voulu : la famille consulte librement, seul l'administrateur modifie.
- **Également ouvertes** : les routes `/api/*` (recherches TMDB, Discogs et Google Books utilisées par les formulaires d'ajout). Elles ne demandent pas le PIN et consomment les quotas de tes clés API : un appareil du réseau pourrait donc les appeler sans être administrateur.
- Une route protégée appelée sans session administrateur renvoie vers `/admin/connexion`.

### Connexion et session
- Connexion sur `/admin/connexion` avec le PIN ; déconnexion par le bouton du bandeau (requête `POST` sur `/admin/deconnexion`).
- Le PIN n'est jamais stocké : il est vérifié contre le hash scrypt de `ADMIN_PIN_HASH` (`admin_auth.py`, comparaison à temps constant, paramètres scrypt imposés).
- La session expire après `ADMIN_SESSION_MINUTES` minutes **d'inactivité** (chaque requête repousse l'échéance).
- Cookie de session : `HttpOnly`, `SameSite=Lax`, et `Secure` si `SESSION_COOKIE_SECURE=true`. En HTTP, `Secure` empêche le navigateur d'envoyer le cookie : la connexion administrateur ne fonctionne alors pas. Garder `true` tant que l'application est servie en HTTPS.
- Tous les formulaires sont protégés par un jeton CSRF (Flask-WTF). Les imports sont limités à 100 Mio.

### Blocages après des PIN incorrects
- Après **3 PIN incorrects**, la connexion est bloquée : **30 minutes** la première fois, **2 heures** la deuxième, **24 heures** à partir de la troisième.
- Pendant un blocage, les tentatives reçoivent une erreur `429`. Une connexion réussie remet tout à zéro.
- L'état est conservé dans la table `admin_security`. **Le blocage est global à l'application, pas par adresse IP** : n'importe quel appareil du réseau qui entre trois mauvais PIN bloque aussi l'administrateur légitime. C'est un compromis acceptable sur un réseau familial, à connaître.

### Débloquer manuellement
Si le blocage gêne, remettre le compteur à zéro depuis le dossier du projet :
```bash
docker compose exec mediatheque python -c "import sqlite3; c=sqlite3.connect('data/mediatheque.db'); c.execute('UPDATE admin_security SET failed_attempts=0, lock_level=0, locked_until=NULL WHERE id=1'); c.commit()"
```

### Changer le PIN
Relancer `python3 generer_hash_pin.py`, remplacer la valeur de `ADMIN_PIN_HASH` dans `.env`, puis recréer le conteneur : `docker compose up -d --force-recreate`.

### Bonnes pratiques
- Ne jamais partager `.env`, le PIN, `SECRET_KEY`, `ADMIN_PIN_HASH` ni la clé privée `certs/key.pem`.
- Ne pas publier dans Git la base de données, les sauvegardes ou les photos personnelles (le `.gitignore` les exclut).
- Ne pas exposer directement le port de l'application sur Internet. Pour un accès public : reverse proxy avec un certificat TLS reconnu, pare-feu et règles d'accès adaptées. Le certificat auto-signé est prévu pour un usage local.
- Garder une sauvegarde indépendante des données avant toute opération de maintenance importante.

---

## 7. Docker

### Fichiers clés
- **`Dockerfile`** : image `python:3.11-slim`, installe `requirements.txt`, copie le code. Le conteneur démarre par `entrypoint.sh` (initialisation de la base, voir section 3), puis lance Gunicorn (2 workers, port 5000, HTTPS avec `certs/cert.pem` et `certs/key.pem`).
- **`docker-compose.yml`** : service `mediatheque` (conteneur `mediatheque-maison`, port `5000:5000`, redémarrage automatique `unless-stopped`), charge `.env` et monte en volumes `data/` (qui contient la base `mediatheque.db`), `static/uploads/` et `certs/`. Ces trois éléments **survivent** à une reconstruction de l'image (`docker compose up -d --build`), car ils ne sont jamais copiés dans l'image elle-même (exclus via `.dockerignore`). Ils ne remplacent pas une sauvegarde.
- Gunicorn est lancé avec `certs/cert.pem` et `certs/key.pem` : ces fichiers doivent exister avant de démarrer le conteneur (voir section 8).

### Cycle de mise à jour du code
```bash
# après avoir modifié app.py, un template, etc.
docker compose up -d --build
```

### Vérifier l'état
```bash
docker compose ps
docker compose logs --tail 50
```

### Déplacer l'application vers un autre serveur
1. Copier tout le dossier du projet **avec** `data/` (qui contient la base), `static/uploads/`, `certs/`, `.env` (ces 4 éléments ne sont pas dans Git, il faut les transférer à la main — `scp` ou via le NAS)
2. Régénérer le certificat HTTPS avec la nouvelle IP (voir section 7)
3. `docker compose up -d --build` sur la nouvelle machine

---

## 8. HTTPS (certificat auto-signé)

Nécessaire uniquement pour que la caméra du téléphone soit autorisée par le navigateur (contrainte de sécurité des navigateurs, pas de l'application elle-même).

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
  -keyout certs/key.pem -out certs/cert.pem \
  -subj "/CN=mediatheque" -addext "subjectAltName=IP:TON_IP_LOCALE"
chmod 600 certs/key.pem
```
Remplacer `TON_IP_LOCALE` par l'adresse IP locale du serveur (exemple : `192.168.1.50`).

**Le certificat est lié à une IP précise.** Si l'IP du serveur change, il faut le régénérer, sinon le navigateur refusera la connexion. L'application est ensuite accessible à `https://TON_IP_LOCALE:5000`, avec la même IP que celle du certificat.

Chaque appareil de la famille doit accepter l'avertissement de sécurité **une seule fois** (certificat non reconnu par une autorité officielle, normal pour un usage local).

---

## 9. Reconstruction complète depuis zéro

1. Cloner le dépôt : `git clone git@github.com:DonYsidro/HomeMediatheque.git`
2. Créer `.env` : `cp .env.example .env`, `chmod 600 .env`, puis renseigner les 3 clés API
3. Générer `SECRET_KEY` et `ADMIN_PIN_HASH` (section 5), vérifier `ADMIN_SESSION_MINUTES` et `SESSION_COOKIE_SECURE=true`
4. Générer le certificat HTTPS (section 8)
5. Créer les dossiers persistants : `mkdir -p data static/uploads certs`
6. Lancer : `docker compose up -d --build` (la base est créée automatiquement au démarrage)
7. Vérifier : `docker compose ps` et `docker compose logs --tail 50`
8. Accéder via `https://IP_DU_SERVEUR:5000`, accepter le certificat

**Si tu as une sauvegarde JSON** (section 10), tu peux restaurer toutes les données immédiatement après l'étape 6, avant même d'utiliser l'appli, en te connectant en administrateur puis via la page `/sauvegarde`.

---

## 10. Sauvegarde et restauration

La page **Sauvegarde** est réservée à l'administrateur : son lien apparaît dans le bandeau une fois connecté.

- **Export JSON** : sauvegarde complète (toutes les tables + toutes les photos uploadées, zippées ensemble). C'est LE fichier à garder précieusement et à utiliser pour tout reconstruire.
- **Export CSV** : une table = un fichier CSV dans un zip, pour consultation/modification en masse dans Excel/LibreOffice.
- **Restauration JSON** : remplace **entièrement** les données actuelles par celles du fichier importé (irréversible, une confirmation est demandée).
- **Mise à jour en masse (CSV)** : met à jour uniquement les lignes dont l'`id` existe déjà dans le CSV réimporté — n'ajoute ni ne supprime rien. Pratique pour corriger un champ en masse (ex: renommer un éditeur partout) sans tout réexporter/réimporter.

---

## 11. Fonctionnalités par catégorie

### Films & Séries
Recherche auto via TMDB, genres/réalisateurs/acteurs/compositeurs en relations many-to-many, 4 catégories (films, séries, animation, animés japonais) avec regroupement par série via un champ texte libre. Le champ « classification d'âge » est un texte libre (« Tous publics », « 12+ », etc.).

### CD Audio
Recherche auto via Discogs (titre+artiste, ou code-barre), scan caméra du code-barre, liste des pistes, regroupement automatique par artiste sur la page principale.

### Livres
4 sous-types (roman / collection / cuisine / éducatif), recherche auto via Google Books (titre ou ISBN), scan caméra ISBN, regroupement optionnel par série (champ `serie` + `numero_tome`) — un livre sans série renseignée reste affiché comme livre indépendant.

### BD & Manga
Même logique que Livres (Google Books, scan ISBN), mais le regroupement par série est **obligatoire** — le champ `serie` est distinct du `titre` du tome pour permettre un titre de tome différent à chaque numéro tout en gardant le regroupement cohérent.

### Toutes catégories
- Recherche unique et instantanée (section 12), avec un champ dans le bandeau de toutes les pages.
- Pages de consultation en lecture seule (`/voir`, `/cds/voir`, etc.) — cliquer sur une carte n'ouvre plus directement le formulaire de modification, un bouton "Modifier" dédié y accède.
- Champ photo : possibilité de prendre/importer une photo personnelle en plus (ou à la place) d'une image trouvée en ligne — stockée dans `static/uploads/`.
- Suivi des prêts (à qui, depuis quand).
- Interface bilingue FR/EN (sélecteur dans le bandeau, préférence retenue via cookie).
- Connexion administrateur par PIN pour les opérations de modification (section 6).

---

## 12. Recherche

Une seule page de recherche, `/chercher`, couvre les quatre catégories. Elle remplace l'ancienne recherche multicritère des films (`/recherche`, avec filtres genre, durée, lieu de stockage...) : cette ancienne adresse redirige vers la nouvelle page.

### Fichiers
- `routes/recherche.py` : toute la logique (requêtes, tri, filtres, adresses des fiches).
- `templates/recherche_globale.html` : la page (formulaire, filtre de catégorie, script de recherche instantanée).
- `templates/_resultats_recherche.html` : la zone des résultats, incluse dans la page et renvoyée seule à chaque recherche instantanée.
- `static/style.css` : badges de catégorie (`.badge-categorie`, `.cat-films`, `.cat-cds`, `.cat-livres`, `.cat-bd_mangas`).

### Comportement
- **Un champ dans le bandeau** de toutes les pages : Entrée ouvre `/chercher`. Sur la page de recherche, les résultats se mettent à jour **350 ms après la dernière frappe**, sans recharger la page (`DELAI_MS` dans le script de `recherche_globale.html`). Sans JavaScript, le bouton « Rechercher » fonctionne toujours.
- Techniquement, le script appelle `/chercher?...&partiel=1`, qui ne renvoie que `_resultats_recherche.html`. Une réponse lente qui arrive après une plus récente est ignorée, et l'adresse du navigateur est mise à jour (`/chercher?q=...`), donc partageable.
- **Champ vide = aucun résultat**, même si une catégorie est choisie : la page invite à saisir un mot.
- **Plusieurs mots** : chacun doit se trouver quelque part dans la fiche (8 mots au maximum pris en compte). La recherche porte sur des morceaux de mots (« nas » trouve aussi « Dynastie »), donc les mots très courts donnent des résultats en trop.
- **Accents et majuscules ignorés** : « ete » trouve « Été », « eric » trouve « Éric ». La comparaison passe par une fonction SQLite `norm()` (minuscules, sans accents, `œ`→`oe`, `æ`→`ae`) enregistrée sur chaque connexion de recherche. Les caractères `%` et `_` saisis sont traités comme du texte ordinaire.

### Champs dans lesquels on cherche

| Catégorie | Champs |
|---|---|
| Films & Séries | titre, série, année, support, code-barres, lieu de stockage, emprunteur (si prêté), genres, personnes (réalisateurs, acteurs, compositeurs) |
| CD Audio | titre, artiste, année, genre, pistes, code-barres, lieu de stockage, emprunteur (si prêté) |
| Livres | titre, série, auteur, éditeur, ISBN, langue, année, lieu de stockage, emprunteur (si prêté) |
| BD & Manga | titre, série, auteur, éditeur, ISBN, langue, année, lieu de stockage, emprunteur (si prêté) |

Le **synopsis n'est volontairement pas inclus** : un mot courant ressortirait dans beaucoup de fiches sans lien avec le titre. L'emprunteur n'est cherché que si la fiche est réellement marquée comme prêtée.

### Filtre de catégorie
Menu facultatif : Films, Séries, Animation, Animés japonais, CD Audio, Livres, BD, Manga. Les anciens « coffrets » sont rangés avec les films, comme ailleurs dans l'application.

### Résultats
- Une **seule grille mélangée**, triée par titre sans tenir compte des accents ni des majuscules.
- **Chaque carte porte un badge de catégorie** (icône + libellé : Film, Série, Animation, Animé japonais, CD Audio, Livre, BD, Manga). Pour un livre, le sous-type (Roman, Cuisine...) est affiché en plus.
- Maximum **300 fiches** : au-delà, un message indique que l'affichage est limité.
- Chaque carte mène à la page de consultation de la fiche. Les adresses sont construites avec `url_for` à partir des noms de routes (`films.voir_media`, `cds.voir_cd`, `livres.voir_livre`, `bd_mangas.voir_bd`), jamais écrites à la main : si une route change de chemin, la recherche suit.
- La connexion SQLite est ouverte avec `with closing(get_db())` pour être refermée même en cas d'erreur.

### Modifier la recherche
- **Chercher dans un champ de plus** : l'ajouter dans la liste `texte_sql(...)` de la catégorie, dans le dictionnaire `TABLES` de `routes/recherche.py`.
- **Ajouter une catégorie** : une entrée dans `TABLES` (requête, champs, nom de route de la fiche), une entrée dans `FILTRES_CATEGORIE`, les clés de traduction `type_<valeur>` dans `translations.py` (FR et EN), et une classe `.cat-<famille>` dans `style.css`.
- **Filtre d'âge (mis de côté)** : le code existe mais est désactivé. Mettre `FILTRE_AGE_ACTIF = True` en haut de `routes/recherche.py` fait apparaître un menu « Convient à un enfant de : tous publics / 6 / 10 / 12 / 16 ans ». Il ne concerne que Films & Séries (seuls à avoir une classification d'âge) et masque les autres catégories quand il est actif. Comme la classification est un texte libre, le nombre y est extrait (`12+`, `-12` et `12 ans` valent 12 ; `Tous publics` et `TP` valent 0) ; une fiche sans âge ou au texte illisible est écartée plutôt que présentée comme adaptée aux enfants. Une évolution plus fiable serait un menu déroulant d'âge dans les formulaires d'ajout et de modification.

---

## 13. Système de traduction

`translations.py` contient un dictionnaire `TRANSLATIONS = {'fr': {...}, 'en': {...}}`. La fonction `t(cle)` est injectée automatiquement dans tous les templates via un `@app.context_processor` — pas besoin de la repasser à chaque `render_template()`.

**Piège rencontré** : les valeurs stockées en base (`type='manga'`, `sous_type='roman'`...) sont utilisées comme clés de traduction via `t('type_' + valeur)`. Si une clé `type_xxx` est absente du dictionnaire, `t()` affiche la clé brute au lieu du texte traduit (ex: "type_manga" au lieu de "Manga"). Toujours vérifier que chaque valeur possible d'un champ a sa clé `type_<valeur>` dans les deux langues après l'ajout d'un nouveau type/sous-type.

Le contenu de la collection elle-même (titres, synopsis, noms) n'est **jamais** traduit — seule l'interface (libellés, boutons) l'est.

---

## 14. Licence

Projet sous licence **MIT** (voir `LICENSE`) — libre réutilisation, modification, redistribution, y compris commerciale, à condition de conserver la mention de copyright.
