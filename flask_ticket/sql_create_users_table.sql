-- ============================================================
-- Création de la table des utilisateurs pour l'authentification JWT
-- Schéma : pictures (adaptez selon POSTGRES_SCHEMA dans .env)
-- ============================================================

CREATE TABLE IF NOT EXISTS pictures.users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(100) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,           -- hash bcrypt
    email           VARCHAR(255),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login      TIMESTAMP
);

-- Index sur le username pour accélérer les lookups à la connexion
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON pictures.users (username);

-- Exemple d'insertion d'un premier utilisateur (mot de passe à hasher en Python via bcrypt)
-- INSERT INTO pictures.users (username, password_hash, email)
-- VALUES ('admin', '<hash_bcrypt>', 'admin@example.com');
