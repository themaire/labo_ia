-- Création du schéma ollama
CREATE SCHEMA IF NOT EXISTS ollama;

-- Table d'historique des tests de modèles
CREATE TABLE IF NOT EXISTS ollama.model_tests (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    duration_seconds REAL,
    server_ip TEXT,
    model TEXT,
    prompt TEXT,
    options JSONB,
    image_base64 TEXT,
    result TEXT,
    error TEXT
);

-- Index pour les recherches rapides
CREATE INDEX IF NOT EXISTS idx_model_tests_model ON ollama.model_tests(model);
CREATE INDEX IF NOT EXISTS idx_model_tests_created_at ON ollama.model_tests(created_at);
