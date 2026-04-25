from flask import Flask, request, render_template_string, jsonify
import requests as req
import os

import base64

app = Flask(__name__)


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

@app.route('/', methods=['GET'])
def index():
    # Si aucun serveur sélectionné, la liste des modèles est vide
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
    return render_template(
        "index.html",
        result=None,
        models=models,
        selected_model=selected_model,
        need_prompt=need_prompt,
        prompt=prompt,
        servers=OLLAMA_SERVERS,
        selected_server=selected_server
    )

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
    # LOGS détaillés
    print("--- Nouvelle soumission utilisateur (AJAX) ---")
    print(f"Modèle sélectionné : {selected_model}")
    print(f"Prompt fourni : '{prompt}'")
    print(f"Image base64 reçue : {len(img_b64)} caractères")
    print(f"Serveur sélectionné : {server_ip}")
    print("----------------------------------------------")
    # Toujours envoyer l'image dans 'images' (liste), pour compatibilité multimodale
    payload = {
        "model": selected_model,
        "prompt": prompt,
        "images": [img_b64] if img_b64 else []
    }
    headers = {'Content-Type': 'application/json'}
    ollama_url = get_ollama_url(server_ip)
    try:
        t0 = time.time()
        response = req.post(ollama_url, json=payload, headers=headers, timeout=300)
        t1 = time.time()
        response.raise_for_status()
        raw = response.text
        assembled = assemble_ollama_response(raw)
        elapsed = t1 - t0
        # On retourne le résultat brut + le texte reconstitué + temps
        return (
            f"\n\n---\nTemps de génération : {elapsed:.2f} secondes" +
            "\n---\nTexte reconstitué :\n" + assembled
        )
    except Exception as e:
        return f"Erreur lors de l'appel à Ollama : {e}", 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
