from flask import Flask, request, render_template_string, jsonify
import requests as req
import os
import base64

app = Flask(__name__)


# Liste des serveurs : (nom affiché, IP)
OLLAMA_SERVERS = [
    ("Raspberry Pi 5", "192.168.1.52"),
    ("Serveur Ollama", "192.168.1.18")
]

# Par défaut, utiliser le premier serveur
DEFAULT_SERVER_IP = OLLAMA_SERVERS[0][1]
OLLAMA_PORT = 11434
OLLAMA_API_PATH = "/api/generate"
def get_ollama_url(ip):
    return f"http://{ip}:{OLLAMA_PORT}{OLLAMA_API_PATH}"
# Liste des modèles : (nom interne, affichage, besoin_prompt)
OLLAMA_MODELS = [
    ("ticket_carburant:latest", "Ticket Carburant (pas de prompt, image obligatoire)", False, True),
    ("gemma4:e4b", "Gemma4 (prompt requis, image optionnelle)", True, False)
]

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HTML_FORM = '''
<!doctype html>
<title>Labo_IA</title>
<h2>Laboratoire IA local</h2>
<form enctype=multipart/form-data id="formulaire">
    <label for="server">Choisir le serveur :</label>
    <select name="server" id="server">
        {% for name, ip in servers %}
            <option value="{{ ip }}" {% if ip == selected_server %}selected{% endif %}>{{ name }} ({{ ip }})</option>
        {% endfor %}
    </select><br><br>
    <label for="model">Choisir le modèle :</label>
    <select name="model" id="model" onchange="togglePrompt();toggleImageRequired();">
        {% for value, label, need_prompt, image_required in models %}
            <option value="{{ value }}" data-needprompt="{{ 'true' if need_prompt else 'false' }}" data-imagerequired="{{ 'true' if image_required else 'false' }}" {% if value == selected_model %}selected{% endif %}>{{ label }}</option>
        {% endfor %}
    </select><br><br>
    <div id="promptDiv" style="display: {% if need_prompt %}block{% else %}none{% endif %};">
        <label for="prompt">Prompt :</label>
        <input type="text" name="prompt" id="prompt" value="{{ prompt|default('') }}" style="width:400px;">
    </div><br>
    <input type=file name=ticket id="ticketInput" accept="image/*"><br><br>
    <input type=submit value=Analyser>
</form>
<div id="waitMsg" style="display:none; color:blue; font-weight:bold;">Veuillez patienter, traitement en cours...</div>
<div id="resultDiv"></div>
<script>
function togglePrompt() {
    var select = document.getElementById('model');
    var needPrompt = select.options[select.selectedIndex].getAttribute('data-needprompt') === 'true';
    document.getElementById('promptDiv').style.display = needPrompt ? 'block' : 'none';
}
function toggleImageRequired() {
    var select = document.getElementById('model');
    var imageRequired = select.options[select.selectedIndex].getAttribute('data-imagerequired') === 'true';
    var ticketInput = document.getElementById('ticketInput');
    ticketInput.required = imageRequired;
}
window.onload = function() {
    togglePrompt();
    toggleImageRequired();
    document.getElementById('waitMsg').style.display = 'none';
    document.getElementById('resultDiv').innerHTML = '';
};
document.getElementById('formulaire').onsubmit = async function(e) {
    e.preventDefault();
    document.getElementById('waitMsg').style.display = 'block';
    document.getElementById('resultDiv').innerHTML = '';
    const form = document.getElementById('formulaire');
    const formData = new FormData(form);
    // Construction du payload côté JS (comme côté Flask)
    const model = formData.get('model');
    const prompt = formData.get('prompt') || "";
    const file = formData.get('ticket');
    const server = formData.get('server');
    // Vérifie si l'image est obligatoire pour le modèle sélectionné
    var select = document.getElementById('model');
    var imageRequired = select.options[select.selectedIndex].getAttribute('data-imagerequired') === 'true';
    if (imageRequired && (!file || !file.name)) {
        document.getElementById('waitMsg').style.display = 'none';
        document.getElementById('resultDiv').innerHTML = '<span style="color:red">Veuillez sélectionner une image (obligatoire pour ce modèle).</span>';
        return;
    }
    // Lecture du fichier image en base64
    const reader = new FileReader();
    reader.onload = async function() {
        const img_b64 = reader.result.split(',')[1];
        const payload = {
            model: model,
            prompt: prompt,
            image: img_b64,
            server: server
        };
        try {
            const response = await fetch("/api_ollama", {
                method: "POST",
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const text = await response.text();
            document.getElementById('waitMsg').style.display = 'none';
            document.getElementById('resultDiv').innerHTML = '<h3>Résultat JSON :</h3><pre>' + text + '</pre>';
        } catch (err) {
            document.getElementById('waitMsg').style.display = 'none';
            document.getElementById('resultDiv').innerHTML = '<span style="color:red">Erreur lors de la requête.</span>';
        }
    };
    if (file && file.name) {
        reader.readAsDataURL(file);
    } else {
        // Pas d'image, mais image optionnelle (ex: Gemma)
        const payload = {
            model: model,
            prompt: prompt,
            image: "",
            server: server
        };
        try {
            const response = await fetch("/api_ollama", {
                method: "POST",
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const text = await response.text();
            document.getElementById('waitMsg').style.display = 'none';
            document.getElementById('resultDiv').innerHTML = '<h3>Résultat JSON :</h3><pre>' + text + '</pre>';
        } catch (err) {
            document.getElementById('waitMsg').style.display = 'none';
            document.getElementById('resultDiv').innerHTML = '<span style="color:red">Erreur lors de la requête.</span>';
        }
    }
};
</script>
'''



# Page principale (GET seulement)
@app.route('/', methods=['GET'])
def index():
    selected_model = OLLAMA_MODELS[0][0]
    need_prompt = OLLAMA_MODELS[0][2]
    prompt = ""
    selected_server = DEFAULT_SERVER_IP
    return render_template_string(
        HTML_FORM,
        result=None,
        models=OLLAMA_MODELS,
        selected_model=selected_model,
        need_prompt=need_prompt,
        prompt=prompt,
        servers=OLLAMA_SERVERS,
        selected_server=selected_server
    )


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
