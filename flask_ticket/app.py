from flask import Flask, request, render_template_string, jsonify
import requests as req
import os


import base64
from dotenv import load_dotenv
import psycopg2
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__)

# API : suppression d'un test
@app.route('/api_history_delete/<int:test_id>', methods=['DELETE'])
def api_history_delete(test_id):
    try:
        conn = psycopg2.connect(
            host=os.environ.get('POSTGRES_HOST'),
            user=os.environ.get('POSTGRES_USER'),
            password=os.environ.get('POSTGRES_PASSWORD'),
            dbname=os.environ.get('POSTGRES_DB'),
            options='-c search_path=ollama'
        )
        cur = conn.cursor()
        cur.execute('DELETE FROM model_tests WHERE id = %s', (test_id,))
        conn.commit()
        cur.close()
        conn.close()
        return '', 204
    except Exception as e:
        return str(e), 500
    
# Connexion PostgreSQL
def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get('POSTGRES_HOST'),
        user=os.environ.get('POSTGRES_USER'),
        password=os.environ.get('POSTGRES_PASSWORD'),
        dbname=os.environ.get('POSTGRES_DB'),
        options=f"-c search_path={os.environ.get('POSTGRES_SCHEMA','public')}"
    )
    return conn



# Liste des serveurs : (nom affiché, IP)

# Ajout d'un serveur factice pour forcer la sélection
OLLAMA_SERVERS = [
    ("Sélectionnez un serveur", "")
]
OLLAMA_SERVERS += [
    ("Raspberry Pi 5", "192.168.1.52"),
    ("Serveur Ollama", "192.168.1.18")
]

# Par défaut, aucun serveur sélectionné (valeur vide)
DEFAULT_SERVER_IP = ""
OLLAMA_PORT = 11434
OLLAMA_API_PATH = "/api/generate"
def get_ollama_url(ip):
    return f"http://{ip}:{OLLAMA_PORT}{OLLAMA_API_PATH}"
# Liste des modèles : paramètres : (nom interne, affichage, besoin_prompt)
OLLAMA_MODELS = [
    ("ticket_carburant:latest", "Ticket Carburant (pas de prompt, image obligatoire)", False, True),
    ("gemma3:4b", "Gemma3-4b (prompt requis, image optionnelle)", True, False),
    ("gemma4:e2b", "Gemma4-e2b (prompt requis, image optionnelle)", True, False),
    ("gemma4:e4b", "Gemma4-e4b (prompt requis, image optionnelle)", True, False)
]

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)



# Page principale (GET seulement)
from flask import render_template
import requests as pyrequests


# Page d'accueil mobile-friendly avec navigation
@app.route('/', methods=['GET'])
def index():
    return '''
    <html lang="fr"><head><meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="Content-Language" content="fr">
    <title>Accueil IA Tickets</title>
    <style>
    body { font-family: sans-serif; margin: 2em; text-align: center; }
    h1 { font-size: 2em; margin-bottom: 1.5em; }
    .btn {
        display: block;
        width: 90%;
        max-width: 400px;
        margin: 1em auto;
        padding: 1.2em;
        font-size: 1.3em;
        background: #1976d2;
        color: #fff;
        border: none;
        border-radius: 0.7em;
        text-decoration: none;
        font-weight: bold;
        box-shadow: 0 2px 8px #0002;
        transition: background 0.2s;
    }
    .btn:hover { background: #125ea2; }
    </style></head><body>
    <h1>Assistant IA Tickets</h1>
    <a class="btn" href="/ask">🧠 Demander à l'IA</a>
    <a class="btn" href="/upload_ticket">📷 Envoyer un ticket</a>
    <a class="btn" href="/check_tickets">📋 Liste des tickets</a>
    </body></html>
    '''


# Route /ask : interface IA (ajout du lien historique)
@app.route('/ask', methods=['GET'])
def ask():
    selected_server = DEFAULT_SERVER_IP
    if selected_server:
        models = OLLAMA_MODELS
        selected_model = OLLAMA_MODELS[0][0]
        need_prompt = OLLAMA_MODELS[0][2]
    else:
        models = []
        selected_model = ""
        need_prompt = False
    prompt = ""
    # Ajout du lien en haut de page via une variable
    return render_template(
        "index.html",
        result=None,
        models=models,
        selected_model=selected_model,
        need_prompt=need_prompt,
        prompt=prompt,
        servers=OLLAMA_SERVERS,
        selected_server=selected_server,
        show_history_link=True
    )

# Route page historique
@app.route('/history', methods=['GET'])
def history():
    return render_template("history.html")

# API : liste des tests (récents)
@app.route('/api_history_list', methods=['GET'])
def api_history_list():
    try:
        conn = psycopg2.connect(
            host=os.environ.get('POSTGRES_HOST'),
            user=os.environ.get('POSTGRES_USER'),
            password=os.environ.get('POSTGRES_PASSWORD'),
            dbname=os.environ.get('POSTGRES_DB'),
            options='-c search_path=ollama'
        )
        cur = conn.cursor()
        cur.execute('''
            SELECT id, created_at, finished_at, duration_seconds, server_ip, model, prompt, options, result, error
            FROM model_tests
            ORDER BY created_at DESC
            LIMIT 100
        ''')
        rows = cur.fetchall()
        cur.close()
        conn.close()
        # On ne renvoie pas l'image ni le résultat complet
        result = []
        for r in rows:
            result.append({
                'id': r[0],
                'created_at': r[1].strftime('%Y-%m-%d %H:%M:%S'),
                'finished_at': r[2].strftime('%Y-%m-%d %H:%M:%S') if r[2] else None,
                'duration_seconds': float(r[3]) if r[3] else None,
                'server_ip': r[4],
                'model': r[5],
                'prompt': r[6],
                'options': r[7],
                'result': r[8],
                'error': r[9]
            })
        return jsonify(result)
    except Exception as e:
        return jsonify([]), 500

# API : détail d'un test
@app.route('/api_history_detail/<int:test_id>', methods=['GET'])
def api_history_detail(test_id):
    try:
        conn = psycopg2.connect(
            host=os.environ.get('POSTGRES_HOST'),
            user=os.environ.get('POSTGRES_USER'),
            password=os.environ.get('POSTGRES_PASSWORD'),
            dbname=os.environ.get('POSTGRES_DB'),
            options='-c search_path=ollama'
        )
        cur = conn.cursor()
        cur.execute('''
            SELECT id, created_at, finished_at, duration_seconds, server_ip, model, prompt, options, image_base64, result, error
            FROM model_tests WHERE id = %s
        ''', (test_id,))
        r = cur.fetchone()
        cur.close()
        conn.close()
        if not r:
            return jsonify({}), 404
        return jsonify({
            'id': r[0],
            'created_at': r[1].strftime('%Y-%m-%d %H:%M:%S'),
            'finished_at': r[2].strftime('%Y-%m-%d %H:%M:%S') if r[2] else None,
            'duration_seconds': float(r[3]) if r[3] else None,
            'server_ip': r[4],
            'model': r[5],
            'prompt': r[6],
            'options': r[7],
            'image_base64': r[8],
            'result': r[9],
            'error': r[10]
        })
    except Exception as e:
        return jsonify({}), 500

# Route /check_tickets : liste des tickets
@app.route('/check_tickets', methods=['GET'])
def check_tickets():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT id, filename, is_processed, created_at, type, status
            FROM tickets
            ORDER BY created_at DESC
            LIMIT 50;
        ''')
        tickets = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        tickets = []
    html = """
    <html lang='fr'><head><meta name='viewport' content='width=device-width, initial-scale=1'>
    <meta http-equiv='Content-Language' content='fr'>
    <title>Liste des tickets</title>
    <style>
    body { font-family: sans-serif; margin: 1em; }
    .header { display: flex; gap: 1em; align-items: center; margin-bottom: 1em; }
    .header a { text-decoration: none; color: #1976d2; font-weight: bold; font-size: 1.1em; }
    .ticket { border-bottom: 1px solid #ccc; padding: 0.5em 0; display: flex; align-items: center; justify-content: space-between; }
    .ticket-info { flex: 1; }
    .status-ok { color: green; font-weight: bold; }
    .status-ko { color: red; font-weight: bold; }
    .del-btn { background: #e53935; color: #fff; border: none; border-radius: 0.4em; padding: 0.3em 0.8em; font-size: 1em; cursor: pointer; margin-left: 1em; }
    .del-btn:hover { background: #b71c1c; }
    </style></head><body>
    <div class='header'>
      <a href='/'>🏠 Accueil</a>
      <a href='/upload_ticket'>📷 Envoyer</a>
      <a href='/ask'>🧠 IA</a>
    </div>
    <h2>50 derniers tickets</h2>
    <div>
    """
    for t in tickets:
        id, filename, is_processed, created_at, ticket_type, status = t
        # Affichage dynamique du statut
        if status == 'en attente':
            status_html = "<span style='color:orange;font-weight:bold;'>🕓 en attente</span>"
        elif status == 'en cours':
            status_html = "<span style='color:blue;font-weight:bold;'>⏳ en cours</span>"
        elif status == 'traité':
            status_html = "<span style='color:green;font-weight:bold;'>✔ traité</span>"
        elif status == 'erreur':
            status_html = "<span style='color:red;font-weight:bold;'>❌ erreur</span>"
        else:
            status_html = f"<span style='color:gray;'>{status or '-'}</span>"
        html += f"<div class='ticket'><div class='ticket-info'><b>{filename or 'ticket_' + str(id)}</b> [{ticket_type or '-'}] - {status_html}<br><small>{created_at}</small></div>"
        html += f"<form method='post' action='/delete_ticket' style='margin:0;display:inline;'><input type='hidden' name='id' value='{id}' /><button class='del-btn' type='submit' onclick=\"return confirm('Supprimer ce ticket ?');\">🗑️</button></form>"
        # Ajout du bouton Traiter si statut = en attente
        if status == 'en attente':
            html += f"<form method='post' action='/process_ticket' style='margin:0;display:inline;'><input type='hidden' name='id' value='{id}' /><button class='del-btn' style='background:#1976d2;margin-left:1em;' type='submit'>🚀 Traiter</button></form>"
        html += "</div>"
    html += """
    </div>
    </body></html>
    """
    return html

# Route pour supprimer un ticket
@app.route('/delete_ticket', methods=['POST'])
def delete_ticket():
    ticket_id = request.form.get('id')
    if not ticket_id:
        return "<html><body><h2>Erreur</h2><p>ID manquant</p></body></html>", 400
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM tickets WHERE id = %s;', (ticket_id,))
        conn.commit()
        cur.close()
        conn.close()
        return """
        <html lang='fr'><head><meta name='viewport' content='width=device-width, initial-scale=1'>
        <meta http-equiv='Content-Language' content='fr'>
        <title>Ticket supprimé</title>
        <style>
        body { font-family: sans-serif; margin: 1em; text-align: center; }
        .header { display: flex; gap: 1em; align-items: center; justify-content: center; margin-bottom: 1em; }
        .header a { text-decoration: none; color: #1976d2; font-weight: bold; font-size: 1.1em; }
        .btn { display: inline-block; margin-top: 2em; padding: 1em 2em; background: #1976d2; color: #fff; border: none; border-radius: 0.7em; font-size: 1.1em; text-decoration: none; font-weight: bold; }
        .btn:hover { background: #125ea2; }
        </style></head><body>
        <div class='header'>
            <a href='/'>🏠 Accueil</a>
            <a href='/upload_ticket'>📷 Envoyer</a>
            <a href='/check_tickets'>📋 Liste</a>
            <a href='/ask'>🧠 IA</a>
        </div>
        <h2>Ticket supprimé</h2>
        <a class='btn' href='/check_tickets'>Retour à la liste</a>
        </body></html>
        """
    except Exception as e:
        return f"<html><body><h2>Erreur</h2><p>{str(e)}</p></body></html>", 500
        cur.close()
        conn.close()
    except Exception as e:
        tickets = []
    # Génération HTML simple, mobile friendly
    html = """
    <html><head><meta name='viewport' content='width=device-width, initial-scale=1'>
    <title>Liste des tickets</title>
    <style>
    body { font-family: sans-serif; margin: 1em; }
    .ticket { border-bottom: 1px solid #ccc; padding: 0.5em 0; }
    .status-ok { color: green; font-weight: bold; }
    .status-ko { color: red; font-weight: bold; }
    </style></head><body>
    <h2>erniers tickets</h2>
    <div>
    """
    for t in tickets:
        id, filename, is_processed, created_at = t
        status = "<span class='status-ok'>✔ traité</span>" if is_processed else "<span class='status-ko'>⏳ en attente</span>"
        html += f"<div class='ticket'><b>{filename or 'ticket_' + str(id)}</b> - {status}<br><small>{created_at}</small></div>"
    html += """
    </div>
    </body></html>
    """
    return html

# Endpoint pour lister dynamiquement les modèles d'un serveur Ollama
@app.route('/api_list_models', methods=['POST'])
def api_list_models():
    data = request.get_json()
    server_ip = data.get('server_ip', DEFAULT_SERVER_IP)
    try:
        url = f"http://{server_ip}:{OLLAMA_PORT}/api/tags"
        r = req.get(url, timeout=10)
        r.raise_for_status()
        tags = r.json().get('models', [])
        # On superpose la logique métier de OLLAMA_MODELS si le nom correspond
        models = []
        for tag in tags:
            name = tag['name']
            # Cherche dans OLLAMA_MODELS un tuple dont le nom interne correspond
            found = next((m for m in OLLAMA_MODELS if m[0] == name), None)
            if found:
                # Utilise le libellé, besoin_prompt, image_obligatoire définis dans OLLAMA_MODELS
                models.append((found[0], found[1], found[2], found[3]))
            else:
                # Sinon, valeurs par défaut (nom, nom, False, False)
                models.append((name, name, False, False))
        return jsonify(models)
    except Exception as e:
        return jsonify([]), 500


# Fonction pour reconstituer le texte à partir des lignes JSON
import json as _json
import time
def assemble_ollama_response(raw_text):
    lines = raw_text.strip().splitlines()
    responses = []
    for line in lines:
        try:
            obj = _json.loads(line)
            if 'response' in obj:
                responses.append(obj['response'])
        except Exception:
            continue
    return ''.join(responses)

# Endpoint AJAX pour traitement Ollama
@app.route('/api_ollama', methods=['POST'])
def api_ollama():
    data = request.get_json()
    selected_model = data.get('model', OLLAMA_MODELS[0][0])
    prompt = data.get('prompt', "")
    img_b64 = data.get('image', "")
    server_ip = data.get('server', DEFAULT_SERVER_IP)
    options = data.get('options', None)
    preprocess = data.get('preprocess', False)
    # LOGS détaillés
    print("--- Nouvelle soumission utilisateur (AJAX) ---")
    print(f"Modèle sélectionné : {selected_model}")
    print(f"Prompt fourni : '{prompt}'")
    print(f"Image base64 reçue : {len(img_b64)} caractères")
    print(f"Serveur sélectionné : {server_ip}")
    print(f"Options reçues : {options}")
    print(f"Prétraitement image demandé : {preprocess}")
    print("----------------------------------------------")
    # Si prétraitement demandé et image présente, appliquer le traitement
    image_width, image_height = None, None
    if img_b64:
        try:
            import base64
            import numpy as np
            import cv2
            img_bytes = base64.b64decode(img_b64)
            arr = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if preprocess:
                from flask_ticket.image_utils import preprocess as img_preprocess
                processed = img_preprocess(img)
                # On réencode en PNG base64
                _, buf = cv2.imencode('.png', processed)
                img_b64 = base64.b64encode(buf).decode('utf-8')
                image_height, image_width = processed.shape[:2]
            else:
                image_height, image_width = img.shape[:2]
        except Exception as e:
            print(f"Erreur prétraitement image : {e}")
            # On continue avec l'image d'origine
    # Historique : insertion dans ollama.model_tests
    test_id = None
    try:
        conn = psycopg2.connect(
            host=os.environ.get('POSTGRES_HOST'),
            user=os.environ.get('POSTGRES_USER'),
            password=os.environ.get('POSTGRES_PASSWORD'),
            dbname=os.environ.get('POSTGRES_DB'),
            options='-c search_path=ollama'
        )
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO model_tests (server_ip, model, prompt, options, image_base64, image_preprocessed, image_width, image_height)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        ''', (
            server_ip,
            selected_model,
            prompt,
            _json.dumps(options) if options else None,
            img_b64 if img_b64 else None,
            bool(preprocess) if img_b64 else None,
            image_width,
            image_height
        ))
        test_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[Historique] Erreur insertion : {e}")
    # Toujours envoyer l'image dans 'images' (liste), pour compatibilité multimodale
    payload = {
        "model": selected_model,
        "prompt": prompt,
        "images": [img_b64] if img_b64 else []
    }
    if options is not None:
        payload["options"] = options
    headers = {'Content-Type': 'application/json'}
    ollama_url = get_ollama_url(server_ip)
    try:
        t0 = time.time()
        response = req.post(ollama_url, json=payload, headers=headers, timeout=400)
        t1 = time.time()
        response.raise_for_status() 
        raw = response.text
        assembled = assemble_ollama_response(raw)
        elapsed = t1 - t0
        # Historique : update avec résultat, date de fin, durée
        if test_id is not None:
            try:
                conn = psycopg2.connect(
                    host=os.environ.get('POSTGRES_HOST'),
                    user=os.environ.get('POSTGRES_USER'),
                    password=os.environ.get('POSTGRES_PASSWORD'),
                    dbname=os.environ.get('POSTGRES_DB'),
                    options='-c search_path=ollama'
                )
                cur = conn.cursor()
                cur.execute('''
                    UPDATE model_tests
                    SET finished_at = NOW(), duration_seconds = %s, result = %s
                    WHERE id = %s;
                ''', (elapsed, assembled, test_id))
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print(f"[Historique] Erreur update : {e}")
        # On retourne le résultat brut + le texte reconstitué + temps
        return (
            f"\n\n---\nTemps de génération : {elapsed:.2f} secondes" +
            "\n---\nTexte reconstitué :\n" + assembled
        )
    except Exception as e:
        # Historique : update avec erreur
        if test_id is not None:
            try:
                conn = psycopg2.connect(
                    host=os.environ.get('POSTGRES_HOST'),
                    user=os.environ.get('POSTGRES_USER'),
                    password=os.environ.get('POSTGRES_PASSWORD'),
                    dbname=os.environ.get('POSTGRES_DB'),
                    options='-c search_path=ollama'
                )
                cur = conn.cursor()
                cur.execute('''
                    UPDATE model_tests
                    SET finished_at = NOW(), error = %s
                    WHERE id = %s;
                ''', (str(e), test_id))
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e2:
                print(f"[Historique] Erreur update (erreur) : {e2}")
        return f"Erreur lors de l'appel à Ollama : {e}", 500

@app.route('/upload_ticket', methods=['GET', 'POST'])
def upload_ticket():
    types = [
        ("Supermarché", "superm"),
        ("Carburant", "carbu"),
        ("Pain", "pain"),
        ("Nico midi", "nicomidi"),
        ("Audrey midi", "audreymidi"),
        ("Divers", "divers"),
        ("Loisir", "loisirs")
    ]
    if request.method == 'GET':
        # Formulaire HTML mobile-friendly pour upload avec menu déroulant et header
        select_html = '<select name="type" required>'
        for label, value in types:
            select_html += f'<option value="{value}">{label}</option>'
        select_html += '</select>'
        return f'''
        <html><head><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Envoyer un ticket</title>
        <style>
        body {{ font-family: sans-serif; margin: 1em; }}
        .header {{ display: flex; gap: 1em; align-items: center; margin-bottom: 1em; }}
        .header a {{ text-decoration: none; color: #1976d2; font-weight: bold; font-size: 1.1em; }}
        .form {{ display: flex; flex-direction: column; gap: 1em; max-width: 400px; margin: auto; }}
        input[type=file] {{ font-size: 1.2em; }}
        button {{ font-size: 1.2em; padding: 0.5em; }}
        select {{ font-size: 1.2em; padding: 0.3em; }}
        </style></head><body>
        <div class='header'>
          <a href='/'>🏠 Accueil</a>
          <a href='/check_tickets'>📋 Liste</a>
          <a href='/ask'>🧠 IA</a>
        </div>
        <h2>Envoyer un ticket</h2>
        <form class="form" method="post" enctype="multipart/form-data">
            <input type="file" name="image" accept="image/*" capture="environment" required />
            {select_html}
            <button type="submit">Envoyer</button>
        </form>
        </body></html>
        '''
    # POST : logique d'enregistrement existante
    ticket_type = request.form.get('type') if request.form else None
    if 'image' in request.files:
        file = request.files['image']
        image_bytes = file.read()
        filename = file.filename
    else:
        data = request.get_json()
        img_b64 = data.get('image', '')
        filename = data.get('filename', None)
        ticket_type = data.get('type', None)
        if not img_b64:
            return jsonify({'error': 'Aucune image reçue'}), 400
        image_bytes = base64.b64decode(img_b64)

    # Vérification doublon (nom + taille)
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''SELECT id FROM tickets WHERE filename = %s AND octet_length(image) = %s LIMIT 1;''', (filename, len(image_bytes)))
        doublon = cur.fetchone()
        cur.close()
        conn.close()
        if doublon:
            # Redirige vers une page d'erreur d'upload
            from flask import redirect, url_for
            return redirect(url_for('upload_error', msg="Une image du même nom et de la même taille existe déjà dans la base de données."))
    except Exception as e:
        # En cas d'erreur de vérification, on continue l'insert (fail-safe)
        pass

    # Insertion du ticket en base et retour HTML de succès
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO tickets (image, is_processed, filename, type, status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, created_at;
        ''', (psycopg2.Binary(image_bytes), False, filename, ticket_type, 'en attente'))
        ticket_id, created_at = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        # Retour mobile-friendly avec header
        return f"""
        <html lang='fr'><head><meta name='viewport' content='width=device-width, initial-scale=1'>
        <meta http-equiv='Content-Language' content='fr'>
        <title>Ticket reçu</title>
        <style>
        body {{ font-family: sans-serif; margin: 1em; text-align: center; }}
        .header {{ display: flex; gap: 1em; align-items: center; justify-content: center; margin-bottom: 1em; }}
        .header a {{ text-decoration: none; color: #1976d2; font-weight: bold; font-size: 1.1em; }}
        .btn {{ display: inline-block; margin-top: 2em; padding: 1em 2em; background: #1976d2; color: #fff; border: none; border-radius: 0.7em; font-size: 1.1em; text-decoration: none; font-weight: bold; }}
        .btn:hover {{ background: #125ea2; }}
        </style></head><body>
        <div class='header'>
            <a href='/'>🏠 Accueil</a>
            <a href='/upload_ticket'>📷 Envoyer</a>
            <a href='/check_tickets'>📋 Liste</a>
            <a href='/ask'>🧠 IA</a>
        </div>
        <h2>Ticket reçu !</h2>
        <p>Ticket n° {ticket_id} enregistré le {created_at}.</p>
        <a class='btn' href='/upload_ticket'>Envoyer un autre ticket</a>
        <a class='btn' href='/check_tickets'>Voir la liste</a>
        </body></html>
        """
    except Exception as e:
        return f"<html><body><h2>Erreur</h2><p>{str(e)}</p></body></html>", 500
# Route pour traiter un ticket (mise à jour du statut + déclenchement n8n)
@app.route('/process_ticket', methods=['POST'])
def process_ticket():
    import requests
    ticket_id = request.form.get('id')
    if not ticket_id:
        return "<html><body><h2>Erreur</h2><p>ID manquant</p></body></html>", 400
    # Met à jour le statut en base (en cours de traitement)
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE tickets SET status = 'en cours' WHERE id = %s;", (ticket_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        return f"<html><body><h2>Erreur</h2><p>Impossible de mettre à jour le statut : {str(e)}</p></body></html>", 500
    # Déclenche le workflow n8n (webhook-test)
    try:
        n8n_url = "http://192.168.1.50:5678/webhook-test/ticket-webhook"
        resp = requests.post(n8n_url, json={"ticket_id": int(ticket_id)})
        if not resp.ok:
            return f"<html><body><h2>Erreur</h2><p>Appel n8n échoué : {resp.status_code} {resp.text}</p></body></html>", 500
    except Exception as e:
        return f"<html><body><h2>Erreur</h2><p>Erreur lors de l'appel n8n : {str(e)}</p></body></html>", 500
    # Redirige vers la liste
    from flask import redirect, url_for
    return redirect(url_for('check_tickets'))

# Route d'erreur d'upload (doit être au niveau global)
@app.route('/upload_error')
def upload_error():
    from flask import request as flask_request
    msg = flask_request.args.get('msg', "Erreur inconnue lors de l'upload.")
    return f"""
    <html lang='fr'><head><meta name='viewport' content='width=device-width, initial-scale=1'>
    <meta http-equiv='Content-Language' content='fr'>
    <title>Erreur upload</title>
    <style>
    body {{ font-family: sans-serif; margin: 1em; text-align: center; }}
    .header {{ display: flex; gap: 1em; align-items: center; justify-content: center; margin-bottom: 1em; }}
    .header a {{ text-decoration: none; color: #1976d2; font-weight: bold; font-size: 1.1em; }}
    .btn {{ display: inline-block; margin-top: 2em; padding: 1em 2em; background: #1976d2; color: #fff; border: none; border-radius: 0.7em; font-size: 1.1em; text-decoration: none; font-weight: bold; }}
    .btn:hover {{ background: #125ea2; }}
    </style></head><body>
    <div class='header'>
        <a href='/'>🏠 Accueil</a>
        <a href='/upload_ticket'>📷 Envoyer</a>
        <a href='/check_tickets'>📋 Liste</a>
        <a href='/ask'>🧠 IA</a>
    </div>
    <h2>Erreur lors de l'upload</h2>
    <p style='color:red;font-size:1.2em;'>{msg}</p>
    <a class='btn' href='/upload_ticket'>Réessayer</a>
    <a class='btn' href='/check_tickets'>Voir la liste</a>
    </body></html>
    """

if __name__ == '__main__':
    app.run(debug=True, port=5000)
