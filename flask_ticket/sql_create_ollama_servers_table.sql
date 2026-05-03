-- Création de la table des serveurs Ollama
-- Schéma : ollama
-- Usage : stockage des serveurs Ollama disponibles

CREATE TABLE IF NOT EXISTS ollama.servers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    ip_address VARCHAR(50) NOT NULL,
    port INT DEFAULT 11434,
    is_active BOOLEAN DEFAULT TRUE,
    display_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index pour accélérer les requêtes
CREATE INDEX IF NOT EXISTS idx_servers_active ON ollama.servers(is_active);
CREATE INDEX IF NOT EXISTS idx_servers_order ON ollama.servers(display_order);

-- Commentaires
COMMENT ON TABLE ollama.servers IS 'Liste des serveurs Ollama disponibles pour l''application';
COMMENT ON COLUMN ollama.servers.name IS 'Nom d''affichage du serveur (ex: Raspberry Pi 5)';
COMMENT ON COLUMN ollama.servers.ip_address IS 'Adresse IP du serveur (ex: 192.168.1.52)';
COMMENT ON COLUMN ollama.servers.port IS 'Port du serveur Ollama (défaut: 11434)';
COMMENT ON COLUMN ollama.servers.is_active IS 'Serveur actif ou désactivé';
COMMENT ON COLUMN ollama.servers.display_order IS 'Ordre d''affichage dans la liste (0 = premier)';

-- Données initiales (migration depuis config.py)
INSERT INTO ollama.servers (name, ip_address, display_order, is_active) VALUES
    ('Raspberry Pi 5', '192.168.1.52', 1, TRUE),
    ('Serveur Ollama', '192.168.1.18', 2, TRUE)
ON CONFLICT DO NOTHING;
