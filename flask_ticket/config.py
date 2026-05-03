"""
Configuration partagée de l'application Flask.
Importé par app.py et les blueprints.
"""

import os
import psycopg2

# ------------------------------------------------------------------
# Debug
# ------------------------------------------------------------------
DEBUG_AUTH = os.environ.get("DEBUG_AUTH", "False").lower() in ("true", "1", "yes")

# ------------------------------------------------------------------
# Serveurs Ollama disponibles
# ------------------------------------------------------------------

def get_ollama_servers_from_db():
    """
    Retourne la liste des serveurs Ollama depuis la base de données (schéma ollama).
    Format : [(nom, ip_address), ...]
    Seuls les serveurs actifs sont retournés, triés par display_order.
    """
    try:
        conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST"),
            user=os.environ.get("POSTGRES_USER"),
            password=os.environ.get("POSTGRES_PASSWORD"),
            dbname=os.environ.get("POSTGRES_DB"),
            options="-c search_path=ollama",
        )
        cur = conn.cursor()
        cur.execute("SELECT name, ip_address FROM servers WHERE is_active = TRUE ORDER BY display_order, id")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        # Ajouter une option par défaut en tête de liste
        return [("Sélectionnez un serveur", "")] + [(row[0], row[1]) for row in rows]
    except Exception as e:
        # En cas d'erreur (table non créée, etc.), retourner les valeurs par défaut
        print(f"[CONFIG] Erreur lecture serveurs depuis BDD : {e}")
        return [
            ("Sélectionnez un serveur", ""),
            ("Raspberry Pi 5", "192.168.1.52"),
            ("Serveur Ollama", "192.168.1.18"),
        ]


# Charger dynamiquement les serveurs (peut être appelé à chaque requête si nécessaire)
OLLAMA_SERVERS = get_ollama_servers_from_db()

DEFAULT_SERVER_IP = ""
OLLAMA_PORT = 11434
OLLAMA_API_PATH = "/api/generate"


def get_ollama_url(ip):
    return f"http://{ip}:{OLLAMA_PORT}{OLLAMA_API_PATH}"


# ------------------------------------------------------------------
# Modèles Ollama : (nom_interne, libellé, besoin_prompt, image_obligatoire)
# ------------------------------------------------------------------

def get_ollama_models_from_db():
    """
    Retourne la liste des modèles Ollama depuis la base de données (schéma ollama).
    Format : [(model_name, display_label, need_prompt, image_required), ...]
    Seuls les modèles actifs sont retournés, triés par display_order.
    """
    try:
        conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST"),
            user=os.environ.get("POSTGRES_USER"),
            password=os.environ.get("POSTGRES_PASSWORD"),
            dbname=os.environ.get("POSTGRES_DB"),
            options="-c search_path=ollama",
        )
        cur = conn.cursor()
        cur.execute("SELECT model_name, display_label, need_prompt, image_required FROM models WHERE is_active = TRUE ORDER BY display_order, id")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [(row[0], row[1], row[2], row[3]) for row in rows]
    except Exception as e:
        # En cas d'erreur (table non créée, etc.), retourner les valeurs par défaut
        print(f"[CONFIG] Erreur lecture modèles depuis BDD : {e}")
        return [
            ("ticket_carburant:latest",     "Ticket Carburant (pas de prompt, image obligatoire)",          False, True),
            ("ti_carbu_gemma4_e4b:latest",  "Ticket Carburant gemma4:e4b (pas de prompt, image obligatoire)", False, True),
            ("gemma3:4b",                   "Gemma3-4b (prompt requis, image optionnelle)",                  True,  False),
            ("gemma4:e2b",                  "Gemma4-e2b (prompt requis, image optionnelle)",                 True,  False),
            ("gemma4:e4b",                  "Gemma4-e4b (prompt requis, image optionnelle)",                 True,  False),
        ]


# Charger dynamiquement les modèles
OLLAMA_MODELS = get_ollama_models_from_db()

# ------------------------------------------------------------------
# Connexion PostgreSQL (schéma par défaut = POSTGRES_SCHEMA)
# ------------------------------------------------------------------
def get_db_connection(schema=None):
    """
    Retourne une connexion psycopg2.
    Si schema est None, utilise la variable d'env POSTGRES_SCHEMA (défaut : 'public').
    """
    target_schema = schema or os.environ.get("POSTGRES_SCHEMA", "public")
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST"),
        user=os.environ.get("POSTGRES_USER"),
        password=os.environ.get("POSTGRES_PASSWORD"),
        dbname=os.environ.get("POSTGRES_DB"),
        options=f"-c search_path={target_schema}",
    )
