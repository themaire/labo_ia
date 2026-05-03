"""
Point d'entrée principal de l'application Flask — IA Tickets.

Structure :
  app.py            — création de l'app, auth, blueprints, page d'accueil
  config.py         — configuration partagée (serveurs, modèles, BDD)
  auth.py           — authentification JWT (login, logout, décorateurs)
  routes_ollama.py  — Blueprint expérimentations Ollama
  routes_tickets.py — Blueprint traitement des tickets de caisse
"""

import os

from dotenv import load_dotenv
from flask import Flask, render_template

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "changez-cette-cle-flask")

# Configuration de la session
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# En développement local (HTTP), ne pas forcer HTTPS
app.config['SESSION_COOKIE_SECURE'] = False

# ------------------------------------------------------------------
# Authentification (routes /login et /logout + décorateurs)
# ------------------------------------------------------------------
try:
    from .auth import register_auth_routes, web_login_required  # python -m flask_ticket.app
except ImportError:
    from auth import register_auth_routes, web_login_required   # python flask_ticket/app.py

register_auth_routes(app)

# ------------------------------------------------------------------
# Blueprints
# ------------------------------------------------------------------
try:
    from .routes_ollama import ollama_bp
    from .routes_tickets import tickets_bp
except ImportError:
    from routes_ollama import ollama_bp
    from routes_tickets import tickets_bp

app.register_blueprint(ollama_bp)
app.register_blueprint(tickets_bp)

# ------------------------------------------------------------------
# Page d'accueil
# ------------------------------------------------------------------

@app.route("/", methods=["GET"])
@web_login_required
def index():
    return """
    <html lang="fr"><head><meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="Content-Language" content="fr">
    <title>Accueil IA Tickets</title>
    <style>
    body { font-family: sans-serif; margin: 2em; text-align: center; }
    h1 { font-size: 2em; margin-bottom: 1.5em; }
    .btn {
        display: block; width: 90%; max-width: 400px; margin: 1em auto;
        padding: 1.2em; font-size: 1.3em; background: #1976d2; color: #fff;
        border: none; border-radius: 0.7em; text-decoration: none;
        font-weight: bold; box-shadow: 0 2px 8px #0002; transition: background 0.2s;
    }
    .btn:hover { background: #125ea2; }
    </style></head><body>
    <h1>Assistant IA Tickets</h1>
    <a class="btn" href="/ask">🧠 Demander à l'IA</a>
    <a class="btn" href="/upload_ticket">📷 Envoyer un ticket</a>
    <a class="btn" href="/check_tickets">📋 Liste des tickets</a>
    <a class="btn" href="/settings">⚙️ Réglages</a>
    <a class="btn" href="/logout" style="background:#e53935;">🔒 Se déconnecter</a>
    </body></html>
    """


if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
