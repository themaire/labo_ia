-- Création de la table des modèles Ollama
-- Schéma : ollama
-- Usage : stockage des modèles Ollama disponibles et leurs configurations

CREATE TABLE IF NOT EXISTS ollama.models (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL UNIQUE,
    display_label VARCHAR(255) NOT NULL,
    need_prompt BOOLEAN DEFAULT TRUE,
    image_required BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    display_order INT DEFAULT 0,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index pour accélérer les requêtes
CREATE INDEX IF NOT EXISTS idx_models_active ON ollama.models(is_active);
CREATE INDEX IF NOT EXISTS idx_models_order ON ollama.models(display_order);
CREATE UNIQUE INDEX IF NOT EXISTS idx_models_name ON ollama.models(model_name);

-- Commentaires
COMMENT ON TABLE ollama.models IS 'Liste des modèles Ollama disponibles et leurs paramètres';
COMMENT ON COLUMN ollama.models.model_name IS 'Nom interne du modèle (ex: ticket_carburant:latest)';
COMMENT ON COLUMN ollama.models.display_label IS 'Libellé d''affichage du modèle';
COMMENT ON COLUMN ollama.models.need_prompt IS 'Le modèle nécessite-t-il un prompt ?';
COMMENT ON COLUMN ollama.models.image_required IS 'Une image est-elle obligatoire pour ce modèle ?';
COMMENT ON COLUMN ollama.models.is_active IS 'Modèle actif ou désactivé';
COMMENT ON COLUMN ollama.models.display_order IS 'Ordre d''affichage dans la liste (0 = premier)';
COMMENT ON COLUMN ollama.models.description IS 'Description détaillée du modèle';

-- Données initiales (migration depuis config.py)
INSERT INTO ollama.models (model_name, display_label, need_prompt, image_required, display_order, is_active) VALUES
    ('ticket_carburant:latest', 'Ticket Carburant (pas de prompt, image obligatoire)', FALSE, TRUE, 1, TRUE),
    ('ti_carbu_gemma4_e4b:latest', 'Ticket Carburant gemma4:e4b (pas de prompt, image obligatoire)', FALSE, TRUE, 2, TRUE),
    ('gemma3:4b', 'Gemma3-4b (prompt requis, image optionnelle)', TRUE, FALSE, 3, TRUE),
    ('gemma4:e2b', 'Gemma4-e2b (prompt requis, image optionnelle)', TRUE, FALSE, 4, TRUE),
    ('gemma4:e4b', 'Gemma4-e4b (prompt requis, image optionnelle)', TRUE, FALSE, 5, TRUE)
ON CONFLICT (model_name) DO NOTHING;
