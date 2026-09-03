CREATE TABLE IF NOT EXISTS medias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titre TEXT NOT NULL,
    type TEXT NOT NULL,
    annee INTEGER,
    age_classification TEXT,
    duree_minutes INTEGER,
    nb_episodes INTEGER,
    nb_saisons INTEGER,
    synopsis TEXT,
    affiche_url TEXT,
    code_barre TEXT,
    lieu_stockage TEXT NOT NULL,
    support TEXT,
    coffret_id INTEGER REFERENCES medias(id) ON DELETE SET NULL,
    est_prete INTEGER DEFAULT 0,
    prete_a TEXT,
    date_pret TEXT,
    date_ajout TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS genres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS medias_genres (
    media_id INTEGER REFERENCES medias(id) ON DELETE CASCADE,
    genre_id INTEGER REFERENCES genres(id) ON DELETE CASCADE,
    PRIMARY KEY (media_id, genre_id)
);

CREATE TABLE IF NOT EXISTS personnes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS medias_personnes (
    media_id INTEGER REFERENCES medias(id) ON DELETE CASCADE,
    personne_id INTEGER REFERENCES personnes(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    PRIMARY KEY (media_id, personne_id, role)
);

CREATE INDEX IF NOT EXISTS idx_medias_titre ON medias(titre);
CREATE INDEX IF NOT EXISTS idx_personnes_nom ON personnes(nom);

CREATE TABLE IF NOT EXISTS cds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titre TEXT NOT NULL,
    artiste TEXT,
    annee INTEGER,
    nb_pistes INTEGER,
    pistes TEXT,
    duree_minutes INTEGER,
    genre TEXT,
    pochette_url TEXT,
    code_barre TEXT,
    lieu_stockage TEXT NOT NULL,
    est_prete INTEGER DEFAULT 0,
    prete_a TEXT,
    date_pret TEXT,
    date_ajout TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS livres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titre TEXT NOT NULL,
    serie TEXT,
    numlero_tome INTEGER,
    auteur TEXT,
    sous_type TEXT NOT NULL,
    annee INTEGER,
    editeur TEXT,
    nb_pages INTEGER,
    isbn TEXT,
    langue TEXT,
    synopsis TEXT,
    couverture_url TEXT,
    lieu_stockage TEXT NOT NULL,
    est_prete INTEGER DEFAULT 0,
    prete_a TEXT,
    date_pret TEXT,
    date_ajout TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bd_mangas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titre TEXT NOT NULL,
    serie TEXT,
    auteur TEXT,
    type TEXT,
    numero_tome INTEGER,
    nb_tomes_serie INTEGER,
    annee INTEGER,
    editeur TEXT,
    isbn TEXT,
    langue TEXT,
    synopsis TEXT,
    couverture_url TEXT,
    lieu_stockage TEXT NOT NULL,
    est_prete INTEGER DEFAULT 0,
    prete_a TEXT,
    date_pret TEXT,
    date_ajout TEXT DEFAULT CURRENT_TIMESTAMP
);
