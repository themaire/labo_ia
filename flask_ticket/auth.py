"""
Module d'authentification JWT pour l'API Flask.

Routes enregistrées via register_auth_routes(app) :
  - GET  /login                : affiche le formulaire de connexion (web)
                                 redirige vers /welcome si la table users est vide
  - POST /login                : traite le formulaire web OU une requête JSON API
  - GET  /logout               : déconnexion web (supprime la session)
  - GET  /welcome              : page de premier démarrage (création du premier utilisateur)
  - POST /welcome              : traite le formulaire de création du premier utilisateur
  - GET  /settings             : page de gestion des utilisateurs (protégée)
  - POST /settings             : création d'un nouvel utilisateur (protégée)

Décorateurs :
  - @jwt_required              : protège les routes API (header Authorization: Bearer)
  - @web_login_required        : protège les routes web (redirige vers /login si non connecté)

Dépendances :
    bcrypt
    PyJWT
"""

import os
import functools
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from flask import request, jsonify, session, redirect, url_for, render_template
import psycopg2

try:
    from .config import DEBUG_AUTH
except ImportError:
    from config import DEBUG_AUTH

# ------------------------------------------------------------------
# Configuration (depuis les variables d'environnement)
# ------------------------------------------------------------------
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "changez-cette-cle-secrete")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = int(os.environ.get("JWT_EXPIRY_DAYS", 30))  # longue durée


# ------------------------------------------------------------------
# Helper de log
# ------------------------------------------------------------------
def _log(message):
    """Affiche un message de debug si DEBUG_AUTH est activé."""
    if DEBUG_AUTH:
        print(message)


# ------------------------------------------------------------------
# Helpers base de données
# ------------------------------------------------------------------

def _get_db_connection():
    """Ouvre une connexion PostgreSQL (même config que app.py)."""
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST"),
        user=os.environ.get("POSTGRES_USER"),
        password=os.environ.get("POSTGRES_PASSWORD"),
        dbname=os.environ.get("POSTGRES_DB"),
        options=f"-c search_path={os.environ.get('POSTGRES_SCHEMA', 'public')}",
    )


def get_user_by_username(username: str) -> dict | None:
    """Retourne les infos utilisateur depuis la BDD ou None si inexistant/inactif."""
    _log(f"[AUTH DEBUG] Recherche utilisateur : '{username}'")
    conn = _get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, password_hash, is_active FROM users WHERE username = %s",
            (username,),
        )
        row = cur.fetchone()
        cur.close()
    finally:
        conn.close()

    if row is None:
        _log(f"[AUTH DEBUG] ❌ Utilisateur '{username}' non trouvé en base")
        return None
    user_id, uname, password_hash, is_active = row
    _log(f"[AUTH DEBUG] ✅ Utilisateur trouvé : id={user_id}, username={uname}, is_active={is_active}")
    _log(f"[AUTH DEBUG] Hash stocké en base : {password_hash[:20]}...")
    return {
        "id": user_id,
        "username": uname,
        "password_hash": password_hash,
        "is_active": is_active,
    }


def update_last_login(user_id: int) -> None:
    """Met à jour la date de dernière connexion."""
    conn = _get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET last_login = NOW() WHERE id = %s",
            (user_id,),
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()


def get_user_count() -> int:
    """Retourne le nombre total d'utilisateurs dans la table."""
    conn = _get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        cur.close()
        return count
    finally:
        conn.close()


def create_user(username: str, password: str, email: str = None) -> bool:
    """Crée un nouvel utilisateur. Retourne True si succès, False si username existe déjà."""
    conn = _get_db_connection()
    try:
        cur = conn.cursor()
        password_hash = hash_password(password)
        cur.execute(
            "INSERT INTO users (username, password_hash, email) VALUES (%s, %s, %s)",
            (username, password_hash, email),
        )
        conn.commit()
        cur.close()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        return False
    finally:
        conn.close()


def get_all_users() -> list[dict]:
    """Retourne la liste de tous les utilisateurs (sans leur mot de passe)."""
    conn = _get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, email, is_active, created_at, last_login FROM users ORDER BY id"
        )
        rows = cur.fetchall()
        cur.close()
        return [
            {
                "id": row[0],
                "username": row[1],
                "email": row[2],
                "is_active": row[3],
                "created_at": row[4],
                "last_login": row[5],
            }
            for row in rows
        ]
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> dict | None:
    """Retourne les infos d'un utilisateur par son ID (sans le mot de passe)."""
    conn = _get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, email, is_active, created_at, last_login FROM users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        cur.close()
        if row is None:
            return None
        return {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "is_active": row[3],
            "created_at": row[4],
            "last_login": row[5],
        }
    finally:
        conn.close()


def update_user(user_id: int, username: str = None, email: str = None, password: str = None, is_active: bool = None) -> bool:
    """Met à jour les informations d'un utilisateur. Retourne True si succès, False sinon."""
    conn = _get_db_connection()
    try:
        cur = conn.cursor()
        updates = []
        params = []
        
        if username is not None:
            updates.append("username = %s")
            params.append(username)
        
        if email is not None:
            updates.append("email = %s")
            params.append(email)
        
        if password is not None:
            updates.append("password_hash = %s")
            params.append(hash_password(password))
        
        if is_active is not None:
            updates.append("is_active = %s")
            params.append(is_active)
        
        if not updates:
            return True  # Rien à modifier
        
        params.append(user_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
        cur.execute(query, params)
        conn.commit()
        cur.close()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        return False
    finally:
        conn.close()


def delete_user(user_id: int) -> bool:
    """Supprime un utilisateur par son ID. Retourne True si succès, False sinon."""
    conn = _get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        deleted = cur.rowcount > 0
        cur.close()
        return deleted
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


# ------------------------------------------------------------------
# Gestion des mots de passe
# ------------------------------------------------------------------

def hash_password(plain_password: str) -> str:
    """Retourne le hash bcrypt d'un mot de passe en clair."""
    return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()


def check_password(plain_password: str, password_hash: str) -> bool:
    """Vérifie un mot de passe en clair contre son hash bcrypt."""
    _log(f"[AUTH DEBUG] Vérification du mot de passe...")
    _log(f"[AUTH DEBUG] Longueur mot de passe saisi : {len(plain_password)} caractères")
    _log(f"[AUTH DEBUG] Hash attendu : {password_hash[:20]}...")
    result = bcrypt.checkpw(plain_password.encode(), password_hash.encode())
    _log(f"[AUTH DEBUG] Résultat vérification : {'✅ MATCH' if result else '❌ PAS DE MATCH'}")
    return result


# ------------------------------------------------------------------
# Gestion des tokens JWT
# ------------------------------------------------------------------

def generate_token(user_id: int, username: str) -> str:
    """Génère un JWT signé avec une longue durée de validité."""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=JWT_EXPIRY_DAYS)
    
    payload = {
        "sub": str(user_id),  # sub doit être une string selon la spec JWT
        "username": username,
        "iat": int(now.timestamp()),  # Conversion en timestamp numérique
        "exp": int(exp.timestamp()),  # Conversion en timestamp numérique
    }
    _log(f"[AUTH DEBUG] Génération JWT avec clé : {JWT_SECRET_KEY[:20]}...")
    _log(f"[AUTH DEBUG] Payload : {payload}")
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    _log(f"[AUTH DEBUG] Token généré : {token[:50]}...")
    return token


def decode_token(token: str) -> dict | None:
    """
    Décode et valide un JWT.
    Retourne le payload si valide, None sinon.
    """
    _log(f"[AUTH DEBUG] Décodage JWT avec clé : {JWT_SECRET_KEY[:20]}...")
    _log(f"[AUTH DEBUG] Token à décoder : {token[:50]}...")
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        _log(f"[AUTH DEBUG] ✅ Token décodé avec succès : {payload}")
        return payload
    except jwt.ExpiredSignatureError as e:
        _log(f"[AUTH DEBUG] ❌ Token expiré : {e}")
        return None
    except jwt.InvalidTokenError as e:
        _log(f"[AUTH DEBUG] ❌ Token invalide : {type(e).__name__} - {e}")
        return None


# ------------------------------------------------------------------
# Décorateur de protection des routes API (Bearer token)
# ------------------------------------------------------------------

def jwt_required(f):
    """
    Décorateur Flask : vérifie la présence et la validité du JWT
    dans le header Authorization: Bearer <token>.

    Usage :
        @app.route('/pictbyid/<int:pic_id>')
        @jwt_required
        def pictbyid(pic_id):
            ...
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Token manquant ou mal formé"}), 401

        token = auth_header.split(" ", 1)[1]
        payload = decode_token(token)
        if payload is None:
            return jsonify({"error": "Token invalide ou expiré"}), 401

        request.current_user = {
            "id": int(payload["sub"]),  # Reconversion string -> int
            "username": payload["username"],
        }
        return f(*args, **kwargs)

    return decorated


# ------------------------------------------------------------------
# Décorateur de protection des routes web (session)
# ------------------------------------------------------------------

def web_login_required(f):
    """
    Décorateur Flask : vérifie que l'utilisateur est connecté via la session web.
    Redirige vers /login si ce n'est pas le cas.

    Usage :
        @app.route('/')
        @web_login_required
        def index():
            ...
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        _log(f"\n[AUTH DEBUG] ========== VÉRIFICATION WEB LOGIN ==========")
        _log(f"[AUTH DEBUG] Route demandée : {request.path}")
        _log(f"[AUTH DEBUG] Session actuelle : {dict(session)}")
        
        token = session.get("jwt_token")
        if not token:
            _log(f"[AUTH DEBUG] ❌ Aucun token JWT en session → redirection vers /login")
            return redirect(url_for("login", next=request.path))
        
        _log(f"[AUTH DEBUG] ✅ Token trouvé en session : {token[:20]}...")
        payload = decode_token(token)
        
        if payload is None:
            _log(f"[AUTH DEBUG] ❌ Token invalide ou expiré → clear session + redirection")
            session.clear()
            return redirect(url_for("login", next=request.path))
        
        _log(f"[AUTH DEBUG] ✅ Token valide, utilisateur : {payload.get('username')}")
        request.current_user = {
            "id": int(payload["sub"]),  # Reconversion string -> int
            "username": payload["username"],
        }
        _log(f"[AUTH DEBUG] ========== FIN VÉRIFICATION ==========\n")
        return f(*args, **kwargs)

    return decorated


# ------------------------------------------------------------------
# CRUD Serveurs Ollama (schéma ollama)
# ------------------------------------------------------------------

def _get_ollama_db_connection():
    """Connexion PostgreSQL pour le schéma ollama."""
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST"),
        user=os.environ.get("POSTGRES_USER"),
        password=os.environ.get("POSTGRES_PASSWORD"),
        dbname=os.environ.get("POSTGRES_DB"),
        options="-c search_path=ollama",
    )


def get_all_servers() -> list[dict]:
    """Retourne la liste de tous les serveurs Ollama."""
    conn = _get_ollama_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, ip_address, port, is_active, display_order FROM servers ORDER BY display_order, id")
        rows = cur.fetchall()
        cur.close()
        return [
            {
                "id": row[0],
                "name": row[1],
                "ip_address": row[2],
                "port": row[3],
                "is_active": row[4],
                "display_order": row[5],
            }
            for row in rows
        ]
    finally:
        conn.close()


def get_server_by_id(server_id: int) -> dict | None:
    """Retourne un serveur par son ID."""
    conn = _get_ollama_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, ip_address, port, is_active, display_order FROM servers WHERE id = %s", (server_id,))
        row = cur.fetchone()
        cur.close()
        if row is None:
            return None
        return {
            "id": row[0],
            "name": row[1],
            "ip_address": row[2],
            "port": row[3],
            "is_active": row[4],
            "display_order": row[5],
        }
    finally:
        conn.close()


def create_server(name: str, ip_address: str, port: int = 11434, display_order: int = 0) -> bool:
    """Crée un nouveau serveur Ollama."""
    conn = _get_ollama_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO servers (name, ip_address, port, display_order) VALUES (%s, %s, %s, %s)",
            (name, ip_address, port, display_order),
        )
        conn.commit()
        cur.close()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def update_server(server_id: int, name: str = None, ip_address: str = None, port: int = None, is_active: bool = None, display_order: int = None) -> bool:
    """Met à jour un serveur Ollama."""
    conn = _get_ollama_db_connection()
    try:
        cur = conn.cursor()
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = %s")
            params.append(name)
        if ip_address is not None:
            updates.append("ip_address = %s")
            params.append(ip_address)
        if port is not None:
            updates.append("port = %s")
            params.append(port)
        if is_active is not None:
            updates.append("is_active = %s")
            params.append(is_active)
        if display_order is not None:
            updates.append("display_order = %s")
            params.append(display_order)
        
        if not updates:
            return True
        
        params.append(server_id)
        query = f"UPDATE servers SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        cur.execute(query, params)
        conn.commit()
        cur.close()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def delete_server(server_id: int) -> bool:
    """Supprime un serveur Ollama."""
    conn = _get_ollama_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM servers WHERE id = %s", (server_id,))
        conn.commit()
        deleted = cur.rowcount > 0
        cur.close()
        return deleted
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


# ------------------------------------------------------------------
# CRUD Modèles Ollama (schéma ollama)
# ------------------------------------------------------------------

def get_all_models() -> list[dict]:
    """Retourne la liste de tous les modèles Ollama."""
    conn = _get_ollama_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, model_name, display_label, need_prompt, image_required, is_active, display_order, description FROM models ORDER BY display_order, id")
        rows = cur.fetchall()
        cur.close()
        return [
            {
                "id": row[0],
                "model_name": row[1],
                "display_label": row[2],
                "need_prompt": row[3],
                "image_required": row[4],
                "is_active": row[5],
                "display_order": row[6],
                "description": row[7],
            }
            for row in rows
        ]
    finally:
        conn.close()


def get_model_by_id(model_id: int) -> dict | None:
    """Retourne un modèle par son ID."""
    conn = _get_ollama_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, model_name, display_label, need_prompt, image_required, is_active, display_order, description FROM models WHERE id = %s", (model_id,))
        row = cur.fetchone()
        cur.close()
        if row is None:
            return None
        return {
            "id": row[0],
            "model_name": row[1],
            "display_label": row[2],
            "need_prompt": row[3],
            "image_required": row[4],
            "is_active": row[5],
            "display_order": row[6],
            "description": row[7],
        }
    finally:
        conn.close()


def create_model(model_name: str, display_label: str, need_prompt: bool = True, image_required: bool = False, display_order: int = 0, description: str = None) -> bool:
    """Crée un nouveau modèle Ollama."""
    conn = _get_ollama_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO models (model_name, display_label, need_prompt, image_required, display_order, description) VALUES (%s, %s, %s, %s, %s, %s)",
            (model_name, display_label, need_prompt, image_required, display_order, description),
        )
        conn.commit()
        cur.close()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        return False
    finally:
        conn.close()


def update_model(model_id: int, model_name: str = None, display_label: str = None, need_prompt: bool = None, image_required: bool = None, is_active: bool = None, display_order: int = None, description: str = None) -> bool:
    """Met à jour un modèle Ollama."""
    conn = _get_ollama_db_connection()
    try:
        cur = conn.cursor()
        updates = []
        params = []
        
        if model_name is not None:
            updates.append("model_name = %s")
            params.append(model_name)
        if display_label is not None:
            updates.append("display_label = %s")
            params.append(display_label)
        if need_prompt is not None:
            updates.append("need_prompt = %s")
            params.append(need_prompt)
        if image_required is not None:
            updates.append("image_required = %s")
            params.append(image_required)
        if is_active is not None:
            updates.append("is_active = %s")
            params.append(is_active)
        if display_order is not None:
            updates.append("display_order = %s")
            params.append(display_order)
        if description is not None:
            updates.append("description = %s")
            params.append(description)
        
        if not updates:
            return True
        
        params.append(model_id)
        query = f"UPDATE models SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        cur.execute(query, params)
        conn.commit()
        cur.close()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        return False
    finally:
        conn.close()


def delete_model(model_id: int) -> bool:
    """Supprime un modèle Ollama."""
    conn = _get_ollama_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM models WHERE id = %s", (model_id,))
        conn.commit()
        deleted = cur.rowcount > 0
        cur.close()
        return deleted
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


# ------------------------------------------------------------------
# Routes Flask : login (web + API) et logout
# ------------------------------------------------------------------

def register_auth_routes(app):
    """
    Enregistre les routes d'authentification sur l'application Flask.

    Appelez cette fonction dans app.py AVANT les autres routes :
        from auth import register_auth_routes, web_login_required
        register_auth_routes(app)
    """

    @app.route("/login", methods=["GET", "POST"])
    def login():
        """
        GET  → affiche le formulaire de connexion HTML.
        POST → traite :
          - un formulaire web (Content-Type: application/x-www-form-urlencoded)
            → stocke le JWT en session et redirige vers la page demandée.
          - une requête JSON API (Content-Type: application/json)
            → renvoie { "token": "...", "expires_in_days": N }.
        """
        # --- Requête JSON (API) ---
        if request.is_json:
            data = request.get_json(silent=True) or {}
            username = data.get("username", "")
            password = data.get("password", "")
            if not username or not password:
                return jsonify({"error": "username et password requis"}), 400
            user = get_user_by_username(username)
            if user is None or not user["is_active"] or not check_password(password, user["password_hash"]):
                return jsonify({"error": "Identifiants invalides"}), 401
            update_last_login(user["id"])
            token = generate_token(user["id"], user["username"])
            return jsonify({"token": token, "expires_in_days": JWT_EXPIRY_DAYS}), 200

        # --- Formulaire web GET ---
        if request.method == "GET":
            # Vérifier si la table users est vide → rediriger vers /welcome
            if get_user_count() == 0:
                return redirect(url_for("welcome"))
            if session.get("jwt_token") and decode_token(session["jwt_token"]):
                return redirect(request.args.get("next", "/"))
            return render_template("login.html", error=None, next=request.args.get("next", "/"))

        # --- Formulaire web POST ---
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        next_url = request.form.get("next", "/")
        error = None

        _log(f"\n[AUTH DEBUG] ========== TENTATIVE DE CONNEXION ==========")
        _log(f"[AUTH DEBUG] Username saisi : '{username}'")
        _log(f"[AUTH DEBUG] Mot de passe fourni : {'Oui (' + str(len(password)) + ' caractères)' if password else 'Non'}")

        if not username or not password:
            error = "Veuillez renseigner l'identifiant et le mot de passe."
            _log(f"[AUTH DEBUG] ❌ Champs vides détectés")
        else:
            user = get_user_by_username(username)
            if user is None:
                _log(f"[AUTH DEBUG] ❌ Échec : utilisateur non trouvé")
                error = "Identifiants invalides."
            elif not user["is_active"]:
                _log(f"[AUTH DEBUG] ❌ Échec : utilisateur inactif")
                error = "Identifiants invalides."
            elif not check_password(password, user["password_hash"]):
                _log(f"[AUTH DEBUG] ❌ Échec : mot de passe incorrect")
                error = "Identifiants invalides."
            else:
                _log(f"[AUTH DEBUG] ✅ Authentification réussie pour '{username}'")
                update_last_login(user["id"])
                token = generate_token(user["id"], user["username"])
                session["jwt_token"] = token
                session["username"] = user["username"]
                _log(f"[AUTH DEBUG] Token JWT généré : {token[:30]}...")
                _log(f"[AUTH DEBUG] Session après stockage : {dict(session)}")
                _log(f"[AUTH DEBUG] Redirection vers : {next_url}")
                # Sécurité : éviter les redirections ouvertes
                if not next_url.startswith("/"):
                    next_url = "/"
                return redirect(next_url)

        _log(f"[AUTH DEBUG] ========== FIN TENTATIVE ==========\n")
        return render_template("login.html", error=error, next=next_url)

    @app.route("/logout")
    def logout():
        """Déconnexion : supprime la session et redirige vers /login."""
        session.clear()
        return redirect(url_for("login"))

    @app.route("/welcome", methods=["GET", "POST"])
    def welcome():
        """
        Page de premier démarrage : création du premier utilisateur.
        Accessible uniquement si la table users est vide.
        """
        # Rediriger vers /login si des utilisateurs existent déjà
        if get_user_count() > 0:
            return redirect(url_for("login"))

        error = None
        success = False

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            password_confirm = request.form.get("password_confirm", "")
            email = request.form.get("email", "").strip()

            if not username or not password:
                error = "L'identifiant et le mot de passe sont obligatoires."
            elif password != password_confirm:
                error = "Les mots de passe ne correspondent pas."
            elif len(password) < 6:
                error = "Le mot de passe doit contenir au moins 6 caractères."
            else:
                if create_user(username, password, email):
                    success = True
                else:
                    error = "Erreur lors de la création de l'utilisateur."

            if success:
                return redirect(url_for("login"))

        return render_template("welcome.html", error=error)

    @app.route("/settings", methods=["GET", "POST"])
    @web_login_required
    def settings():
        """
        Page de gestion des utilisateurs (liste + création + édition).
        Protégée par authentification web.
        """
        error = None
        success_msg = None

        if request.method == "POST":
            action = request.form.get("action", "create")
            
            if action == "create":
                # Création d'un nouvel utilisateur
                username = request.form.get("username", "").strip()
                password = request.form.get("password", "")
                password_confirm = request.form.get("password_confirm", "")
                email = request.form.get("email", "").strip()

                if not username or not password:
                    error = "L'identifiant et le mot de passe sont obligatoires."
                elif password != password_confirm:
                    error = "Les mots de passe ne correspondent pas."
                elif len(password) < 6:
                    error = "Le mot de passe doit contenir au moins 6 caractères."
                else:
                    if create_user(username, password, email):
                        success_msg = f"Utilisateur '{username}' créé avec succès."
                    else:
                        error = f"L'utilisateur '{username}' existe déjà."
            
            elif action == "edit":
                # Modification d'un utilisateur existant
                user_id = request.form.get("user_id", "")
                username = request.form.get("username", "").strip()
                email = request.form.get("email", "").strip()
                password = request.form.get("password", "")
                password_confirm = request.form.get("password_confirm", "")
                is_active = request.form.get("is_active") == "1"
                
                if not user_id or not username:
                    error = "Identifiant utilisateur requis."
                elif password and password != password_confirm:
                    error = "Les mots de passe ne correspondent pas."
                elif password and len(password) < 6:
                    error = "Le mot de passe doit contenir au moins 6 caractères."
                else:
                    # Mise à jour (mot de passe seulement si fourni)
                    update_password = password if password else None
                    if update_user(int(user_id), username=username, email=email, password=update_password, is_active=is_active):
                        success_msg = f"Utilisateur '{username}' modifié avec succès."
                    else:
                        error = f"Erreur lors de la modification de l'utilisateur '{username}' (peut-être un conflit de nom)."
            
            elif action == "delete":
                # Suppression d'un utilisateur
                user_id = request.form.get("user_id", "")
                if not user_id:
                    error = "Identifiant utilisateur requis pour la suppression."
                else:
                    # Récupérer le username avant suppression pour le message
                    user = get_user_by_id(int(user_id))
                    if user and delete_user(int(user_id)):
                        success_msg = f"Utilisateur '{user['username']}' supprimé avec succès."
                    else:
                        error = "Erreur lors de la suppression de l'utilisateur."

        users = get_all_users()
        return render_template("settings.html", users=users, error=error, success_msg=success_msg)

    @app.route("/settings/servers", methods=["GET", "POST"])
    @web_login_required
    def settings_servers():
        """
        Page de gestion des serveurs Ollama (liste + création + édition + suppression).
        Protégée par authentification web.
        """
        error = None
        success_msg = None

        if request.method == "POST":
            action = request.form.get("action", "create")
            
            if action == "create":
                name = request.form.get("name", "").strip()
                ip_address = request.form.get("ip_address", "").strip()
                port = request.form.get("port", "11434").strip()
                display_order = request.form.get("display_order", "0").strip()
                
                if not name or not ip_address:
                    error = "Le nom et l'adresse IP sont obligatoires."
                else:
                    try:
                        port_int = int(port)
                        order_int = int(display_order)
                        if create_server(name, ip_address, port_int, order_int):
                            success_msg = f"Serveur '{name}' créé avec succès."
                        else:
                            error = "Erreur lors de la création du serveur."
                    except ValueError:
                        error = "Le port et l'ordre doivent être des nombres."
            
            elif action == "edit":
                server_id = request.form.get("server_id", "")
                name = request.form.get("name", "").strip()
                ip_address = request.form.get("ip_address", "").strip()
                port = request.form.get("port", "").strip()
                display_order = request.form.get("display_order", "").strip()
                is_active = request.form.get("is_active") == "1"
                
                if not server_id or not name or not ip_address:
                    error = "Identifiant, nom et adresse IP requis."
                else:
                    try:
                        port_int = int(port) if port else 11434
                        order_int = int(display_order) if display_order else 0
                        if update_server(int(server_id), name=name, ip_address=ip_address, port=port_int, is_active=is_active, display_order=order_int):
                            success_msg = f"Serveur '{name}' modifié avec succès."
                        else:
                            error = f"Erreur lors de la modification du serveur '{name}'."
                    except ValueError:
                        error = "Le port et l'ordre doivent être des nombres."
            
            elif action == "delete":
                server_id = request.form.get("server_id", "")
                if not server_id:
                    error = "Identifiant serveur requis pour la suppression."
                else:
                    server = get_server_by_id(int(server_id))
                    if server and delete_server(int(server_id)):
                        success_msg = f"Serveur '{server['name']}' supprimé avec succès."
                    else:
                        error = "Erreur lors de la suppression du serveur."

        servers = get_all_servers()
        return render_template("settings_servers.html", servers=servers, error=error, success_msg=success_msg)

    @app.route("/settings/models", methods=["GET", "POST"])
    @web_login_required
    def settings_models():
        """
        Page de gestion des modèles Ollama (liste + création + édition + suppression).
        Protégée par authentification web.
        """
        error = None
        success_msg = None

        if request.method == "POST":
            action = request.form.get("action", "create")
            
            if action == "create":
                model_name = request.form.get("model_name", "").strip()
                display_label = request.form.get("display_label", "").strip()
                need_prompt = request.form.get("need_prompt") == "1"
                image_required = request.form.get("image_required") == "1"
                display_order = request.form.get("display_order", "0").strip()
                description = request.form.get("description", "").strip()
                
                if not model_name or not display_label:
                    error = "Le nom du modèle et le libellé sont obligatoires."
                else:
                    try:
                        order_int = int(display_order)
                        if create_model(model_name, display_label, need_prompt, image_required, order_int, description or None):
                            success_msg = f"Modèle '{model_name}' créé avec succès."
                        else:
                            error = f"Erreur lors de la création du modèle (peut-être un doublon du nom '{model_name}')."
                    except ValueError:
                        error = "L'ordre doit être un nombre."
            
            elif action == "edit":
                model_id = request.form.get("model_id", "")
                model_name = request.form.get("model_name", "").strip()
                display_label = request.form.get("display_label", "").strip()
                need_prompt = request.form.get("need_prompt") == "1"
                image_required = request.form.get("image_required") == "1"
                is_active = request.form.get("is_active") == "1"
                display_order = request.form.get("display_order", "").strip()
                description = request.form.get("description", "").strip()
                
                if not model_id or not model_name or not display_label:
                    error = "Identifiant, nom du modèle et libellé requis."
                else:
                    try:
                        order_int = int(display_order) if display_order else 0
                        if update_model(int(model_id), model_name=model_name, display_label=display_label, 
                                       need_prompt=need_prompt, image_required=image_required, 
                                       is_active=is_active, display_order=order_int, description=description or None):
                            success_msg = f"Modèle '{model_name}' modifié avec succès."
                        else:
                            error = f"Erreur lors de la modification du modèle '{model_name}' (peut-être un conflit de nom)."
                    except ValueError:
                        error = "L'ordre doit être un nombre."
            
            elif action == "delete":
                model_id = request.form.get("model_id", "")
                if not model_id:
                    error = "Identifiant modèle requis pour la suppression."
                else:
                    model = get_model_by_id(int(model_id))
                    if model and delete_model(int(model_id)):
                        success_msg = f"Modèle '{model['model_name']}' supprimé avec succès."
                    else:
                        error = "Erreur lors de la suppression du modèle."

        models = get_all_models()
        return render_template("settings_models.html", models=models, error=error, success_msg=success_msg)
