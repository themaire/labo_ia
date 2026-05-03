"""
Blueprint Flask — Traitement des tickets de caisse.

Routes :
  GET/POST /upload_ticket            formulaire d'envoi d'un ticket
  GET      /check_tickets            liste des 50 derniers tickets
  POST     /delete_ticket            suppression d'un ticket
  POST     /process_ticket           déclenchement du traitement (n8n)
  GET      /api_ticket_image/<id>    image d'un ticket en base64 (JSON)
  GET      /pictbyid/<id>            image binaire d'un ticket (usage IA externe)
  GET      /upload_error             page d'erreur générique
"""

import base64
import mimetypes
import os

import psycopg2
import requests
from flask import Blueprint, Response, jsonify, redirect, request, url_for

try:
    from .config import get_db_connection
except ImportError:
    from config import get_db_connection

tickets_bp = Blueprint("tickets", __name__)

# Types de tickets disponibles dans le formulaire
TICKET_TYPES = [
    ("Carburant",   "Carburant"),
    ("Supermarché", "Supermarché"),
    ("Pain",        "Pain"),
    ("Loisirs",     "Loisirs"),
    ("Divers",      "Divers"),
    ("U Express",   "U Express"),
    ("Nico midi",   "Nico midi"),
    ("Audrey midi", "Audrey midi"),
]

# URL du webhook n8n
N8N_WEBHOOK_URL = "http://192.168.1.50:5678/webhook-test/ticket-webhook"

# -------------------------------------------------------
# HTML helpers (modale image partagée entre /check_tickets et /delete_ticket)
# -------------------------------------------------------

_MODAL_STYLES = """
    .img-zoom-fullscreen {
      position: static !important; margin: 0; z-index: 2001; background: #000;
      display: block; border-radius: 0 !important; box-shadow: none; cursor: zoom-out;
      width: auto !important; height: auto !important;
      max-width: none !important; max-height: none !important; object-fit: none !important;
    }
    #img-modal-bg.img-zoom-bg {
      overflow: auto !important; display: flex !important; background: #000 !important;
      z-index: 2000; align-items: center; justify-content: center;
    }
    #img-modal-close.img-zoom-close {
      position: fixed; top: 1.5em; right: 2em; z-index: 2002;
      background: #1976d2; color: #fff; border: none; border-radius: 0.5em;
      padding: 0.5em 1.2em; font-size: 1.2em; cursor: pointer; opacity: 0.95;
    }
    #img-modal-close.img-zoom-close:hover { background: #125ea2; }
"""

_MODAL_HTML = """
    <div id="img-modal-bg" style="display:none;position:fixed;top:0;left:0;width:100vw;height:100vh;
         background:rgba(0,0,0,0.7);z-index:1000;align-items:center;justify-content:center;">
      <div id="img-modal-content" style="background:#fff;padding:1em;border-radius:1em;
           max-width:95vw;max-height:90vh;display:flex;flex-direction:column;align-items:center;">
        <img id="img-modal-img" src="" alt="Ticket"
             style="max-width:90vw;max-height:70vh;border-radius:0.5em;" />
        <button id="img-modal-close"
                style="margin-top:1em;font-size:1.2em;background:#1976d2;color:#fff;
                       border:none;border-radius:0.5em;padding:0.5em 1.2em;cursor:pointer;">
          Fermer
        </button>
      </div>
    </div>
"""

_MODAL_SCRIPT = """
    <script>
    function showTicketImage(ticketId) {
      const modalBg = document.getElementById('img-modal-bg');
      const modalImg = document.getElementById('img-modal-img');
      const modalContent = document.getElementById('img-modal-content');
      const closeBtn = document.getElementById('img-modal-close');
      modalImg.src = ''; modalImg.alt = 'Chargement...';
      modalImg.classList.remove('img-zoom-fullscreen');
      modalBg.classList.remove('img-zoom-bg');
      closeBtn.classList.remove('img-zoom-close');
      modalContent.style.display = 'flex';
      if (modalImg.parentNode !== modalContent) modalContent.insertBefore(modalImg, closeBtn);
      modalBg.style.display = 'flex';
      fetch('/api_ticket_image/' + ticketId)
        .then(r => r.json())
        .then(data => { modalImg.src = data.success ? data.url : ''; modalImg.alt = data.success ? 'Ticket' : 'Erreur'; })
        .catch(() => { modalImg.alt = 'Erreur chargement image'; });
    }
    document.getElementById('img-modal-close').onclick = function() {
      const modalBg = document.getElementById('img-modal-bg');
      const modalImg = document.getElementById('img-modal-img');
      const closeBtn = this;
      const modalContent = document.getElementById('img-modal-content');
      modalBg.style.display = 'none'; modalImg.src = '';
      modalImg.classList.remove('img-zoom-fullscreen');
      modalBg.classList.remove('img-zoom-bg'); closeBtn.classList.remove('img-zoom-close');
      modalContent.style.display = 'flex';
      if (modalImg.parentNode !== modalContent) modalContent.insertBefore(modalImg, closeBtn);
    };
    document.getElementById('img-modal-bg').onclick = function(e) {
      if (e.target !== this) return;
      const modalImg = document.getElementById('img-modal-img');
      const closeBtn = document.getElementById('img-modal-close');
      const modalContent = document.getElementById('img-modal-content');
      this.style.display = 'none'; modalImg.src = '';
      modalImg.classList.remove('img-zoom-fullscreen');
      this.classList.remove('img-zoom-bg'); closeBtn.classList.remove('img-zoom-close');
      modalContent.style.display = 'flex';
      if (modalImg.parentNode !== modalContent) modalContent.insertBefore(modalImg, closeBtn);
    };
    document.getElementById('img-modal-img').onclick = function(e) {
      e.stopPropagation();
      const img = this;
      const modalBg = document.getElementById('img-modal-bg');
      const closeBtn = document.getElementById('img-modal-close');
      const modalContent = document.getElementById('img-modal-content');
      if (!img.classList.contains('img-zoom-fullscreen')) {
        img.classList.add('img-zoom-fullscreen'); modalBg.classList.add('img-zoom-bg');
        closeBtn.classList.add('img-zoom-close'); modalContent.style.display = 'none';
        modalBg.appendChild(img);
      } else {
        img.classList.remove('img-zoom-fullscreen'); modalBg.classList.remove('img-zoom-bg');
        closeBtn.classList.remove('img-zoom-close'); modalContent.style.display = 'flex';
        if (img.parentNode !== modalContent) modalContent.insertBefore(img, closeBtn);
      }
    };
    </script>
"""

_COMMON_STYLES = """
    body { font-family: sans-serif; margin: 1em; }
    .header { display: flex; gap: 1em; align-items: center; margin-bottom: 1em; }
    .header a { text-decoration: none; color: #1976d2; font-weight: bold; font-size: 1.1em; }
    .ticket { border-bottom: 1px solid #ccc; padding: 0.5em 0; display: flex; align-items: center; justify-content: space-between; }
    .ticket-info { flex: 1; }
    .ticket-actions { display: flex; align-items: center; gap: 0.5em; }
    .del-btn { background: #e53935; color: #fff; border: none; border-radius: 0.4em; padding: 0.3em 0.8em; font-size: 1em; cursor: pointer; }
    .del-btn:hover { background: #b71c1c; }
    .img-btn { background: none; border: none; cursor: pointer; font-size: 1.3em; }
    .process-btn { background:#1976d2; color:#fff; border:none; border-radius:0.4em; padding:0.3em 0.8em; font-size:1em; }
    .process-btn:hover { background:#125ea2; }
    #img-modal-bg { display:none; position:fixed; top:0; left:0; width:100vw; height:100vh;
                    background:rgba(0,0,0,0.7); z-index:1000; align-items:center; justify-content:center; }
    #img-modal-content { background:#fff; padding:1em; border-radius:1em; max-width:95vw;
                         max-height:90vh; display:flex; flex-direction:column; align-items:center; }
    #img-modal-content img { max-width:90vw; max-height:70vh; border-radius:0.5em; }
    #img-modal-close { margin-top:1em; font-size:1.2em; background:#1976d2; color:#fff;
                       border:none; border-radius:0.5em; padding:0.5em 1.2em; cursor:pointer; }
    #img-modal-close:hover { background:#125ea2; }
"""

_NAV_HEADER = """
    <div class='header'>
      <a href='/'>🏠 Accueil</a>
      <a href='/upload_ticket'>📷 Envoyer</a>
      <a href='/ask'>🧠 IA</a>
      <a href='/settings'>⚙️ Paramètres</a>
    </div>
"""


def _status_html(status):
    mapping = {
        "en attente": "<span style='color:orange;font-weight:bold;'>🕓 en attente</span>",
        "en cours":   "<span style='color:blue;font-weight:bold;'>⏳ en cours</span>",
        "traité":     "<span style='color:green;font-weight:bold;'>✔ traité</span>",
        "erreur":     "<span style='color:red;font-weight:bold;'>❌ erreur</span>",
    }
    return mapping.get(status, f"<span style='color:gray;'>{status or '-'}</span>")


def _render_ticket_list(tickets, title="50 derniers tickets"):
    html = f"""
    <html lang='fr'><head><meta name='viewport' content='width=device-width, initial-scale=1'>
    <meta http-equiv='Content-Language' content='fr'>
    <title>Liste des tickets</title>
    <style>{_COMMON_STYLES}{_MODAL_STYLES}</style>
    </head><body>
    {_NAV_HEADER}
    <h2>{title}</h2>
    <div>
    """
    for row in tickets:
        tid, filename, is_processed, created_at, ticket_type, status = row
        sh = _status_html(status)
        html += f"""
        <div class='ticket'>
          <div class='ticket-info'>
            <b>{filename or f'ticket_{tid}'}</b> [{ticket_type or '-'}] - {sh}<br>
            <small>{created_at}</small>
          </div>
          <div class='ticket-actions'>
            <button class='img-btn' onclick="showTicketImage({tid});return false;">📷</button>
            <form method='post' action='/delete_ticket' style='margin:0;display:inline;'>
              <input type='hidden' name='id' value='{tid}'>
              <button class='del-btn' type='submit' onclick="return confirm('Supprimer ce ticket ?');">🗑️</button>
            </form>
        """
        if status == "en attente":
            html += f"""
            <form method='post' action='/process_ticket' style='margin:0;display:inline;'>
              <input type='hidden' name='id' value='{tid}'>
              <button class='process-btn' type='submit'>🚀 Traiter</button>
            </form>
            """
        html += "</div></div>"
    html += _MODAL_HTML + _MODAL_SCRIPT + "</div></body></html>"
    return html


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@tickets_bp.route("/check_tickets", methods=["GET"])
def check_tickets():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, filename, is_processed, created_at, type, status
            FROM tickets ORDER BY created_at DESC LIMIT 50;
        """)
        tickets = cur.fetchall()
        cur.close()
        conn.close()
    except Exception:
        tickets = []
    return _render_ticket_list(tickets)


@tickets_bp.route("/upload_ticket", methods=["GET", "POST"])
def upload_ticket():
    if request.method == "GET":
        select_html = "<select name='type' required>"
        for label, value in TICKET_TYPES:
            select_html += f"<option value='{value}'>{label}</option>"
        select_html += "</select>"
        return f"""
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
        #preview {{ max-width:100%; display:none; margin:1em 0; }}
        </style>
        <link rel="stylesheet" href="https://unpkg.com/croppr/dist/croppr.min.css">
        <script src="https://unpkg.com/croppr"></script>
        </head><body>
        <div class='header'>
            <a href='/'>🏠 Accueil</a>
            <a href='/check_tickets'>📋 Liste</a>
            <a href='/ask'>🧠 IA</a>
            <a href='/settings'>⚙️ Paramètres</a>
        </div>
        <h2>Envoyer un ticket</h2>
        <form class="form" id="ticket-form" method="post" enctype="multipart/form-data">
            <input type="file" id="image-input" name="image" accept="image/*" capture="environment" required />
            <img id="preview" style="max-width:100%;display:none;margin:1em 0;">
            <input type="hidden" name="cropped_image" id="cropped-image-field" />
            {select_html}
            <button type="button" id="crop-btn" style="display:none;">Rogner et valider</button>
            <button type="submit" id="submit-btn">Envoyer</button>
        </form>
        <script>
        let croppr = null, cropData = null, imageLoaded = false, img = null;
        const cropBtn = document.getElementById('crop-btn');
        document.getElementById('image-input').addEventListener('change', function(e) {{
            const file = e.target.files[0];
            if (!file) return;
            cropBtn.style.display = 'none'; cropData = null; imageLoaded = false;
            img = document.getElementById('preview');
            const reader = new FileReader();
            reader.onload = function(evt) {{
                img.onload = function() {{
                    imageLoaded = true;
                    if (croppr) croppr.destroy();
                    croppr = new Croppr('#preview', {{
                        onCropEnd: function(data) {{
                            cropData = data;
                            if (imageLoaded && cropData) cropBtn.style.display = 'inline-block';
                        }}
                    }});
                }};
                img.src = evt.target.result;
                img.style.display = 'block';
            }};
            reader.readAsDataURL(file);
        }});
        cropBtn.addEventListener('click', function() {{
            if (!img || !imageLoaded || !img.naturalWidth || !cropData) {{
                alert("Veuillez sélectionner et rogner une image.");
                return;
            }}
            const canvas = document.createElement('canvas');
            const scale = img.naturalWidth / img.width;
            canvas.width = cropData.width * scale;
            canvas.height = cropData.height * scale;
            canvas.getContext('2d').drawImage(
                img,
                cropData.x * scale, cropData.y * scale, cropData.width * scale, cropData.height * scale,
                0, 0, cropData.width * scale, cropData.height * scale
            );
            document.getElementById('cropped-image-field').value = canvas.toDataURL('image/jpeg', 0.8);
            cropBtn.style.display = 'none';
            document.getElementById('ticket-form').submit();
        }});
        </script>
        </body></html>
        """

    # POST
    from base64 import b64decode
    cropped_b64 = request.form.get("cropped_image", "")
    ticket_type = request.form.get("type", None)
    image_bytes = None
    filename = None

    if cropped_b64 and cropped_b64.startswith("data:image/"):
        try:
            _, b64data = cropped_b64.split(",", 1)
            image_bytes = b64decode(b64data)
            orig_file = request.files.get("image")
            if orig_file and orig_file.filename:
                orig_name, orig_ext = os.path.splitext(orig_file.filename)
                filename = f"{orig_name}_cropped{orig_ext or '.jpg'}"
            else:
                filename = "ticket_cropped.jpg"
        except Exception as e:
            return f"<html><body><h2>Erreur</h2><p>Erreur décodage image rognée : {e}</p></body></html>", 400
    elif "image" in request.files:
        file = request.files["image"]
        image_bytes = file.read()
        filename = file.filename
    else:
        return "<html><body><h2>Erreur</h2><p>Aucune image reçue.</p></body></html>", 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO tickets (image, is_processed, filename, type, status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, created_at;
        """, (psycopg2.Binary(image_bytes), False, filename, ticket_type, "en attente"))
        ticket_id, created_at = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return f"""
        <html lang='fr'><head><meta name='viewport' content='width=device-width, initial-scale=1'>
        <meta http-equiv='Content-Language' content='fr'><title>Ticket reçu</title>
        <style>
        body {{ font-family: sans-serif; margin: 1em; text-align: center; }}
        .header {{ display: flex; gap: 1em; align-items: center; justify-content: center; margin-bottom: 1em; }}
        .header a {{ text-decoration: none; color: #1976d2; font-weight: bold; font-size: 1.1em; }}
        .btn {{ display: inline-block; margin-top: 2em; padding: 1em 2em; background: #1976d2; color: #fff;
                border: none; border-radius: 0.7em; font-size: 1.1em; text-decoration: none; font-weight: bold; }}
        .btn:hover {{ background: #125ea2; }}
        </style></head><body>
        <div class='header'><a href='/'>🏠 Accueil</a><a href='/upload_ticket'>📷 Envoyer</a>
        <a href='/check_tickets'>📋 Liste</a><a href='/ask'>🧠 IA</a></div>
        <h2>Ticket reçu !</h2>
        <p>Ticket n° {ticket_id} enregistré le {created_at}.</p>
        <a class='btn' href='/upload_ticket'>Envoyer un autre ticket</a>
        <a class='btn' href='/check_tickets'>Voir la liste</a>
        </body></html>
        """
    except Exception as e:
        return f"<html><body><h2>Erreur</h2><p>{e}</p></body></html>", 500


@tickets_bp.route("/delete_ticket", methods=["POST"])
def delete_ticket():
    ticket_id = request.form.get("id")
    if not ticket_id:
        return "<html><body><h2>Erreur</h2><p>ID manquant</p></body></html>", 400
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM tickets WHERE id = %s;", (ticket_id,))
        conn.commit()
        cur.close()
        conn.close()
        return """
        <html lang='fr'><head><meta name='viewport' content='width=device-width, initial-scale=1'>
        <title>Ticket supprimé</title>
        <style>
        body { font-family: sans-serif; margin: 1em; text-align: center; }
        .header { display: flex; gap: 1em; align-items: center; justify-content: center; margin-bottom: 1em; }
        .header a { text-decoration: none; color: #1976d2; font-weight: bold; font-size: 1.1em; }
        .btn { display: inline-block; margin-top: 2em; padding: 1em 2em; background: #1976d2; color: #fff;
               border: none; border-radius: 0.7em; font-size: 1.1em; text-decoration: none; font-weight: bold; }
        .btn:hover { background: #125ea2; }
        </style></head><body>
        <div class='header'>
            <a href='/'>🏠 Accueil</a><a href='/upload_ticket'>📷 Envoyer</a>
            <a href='/check_tickets'>📋 Liste</a><a href='/ask'>🧠 IA</a>
        </div>
        <h2>Ticket supprimé</h2>
        <a class='btn' href='/check_tickets'>Retour à la liste</a>
        </body></html>
        """
    except Exception as e:
        return f"<html><body><h2>Erreur</h2><p>{e}</p></body></html>", 500


@tickets_bp.route("/process_ticket", methods=["POST"])
def process_ticket():
    ticket_id = request.form.get("id")
    if not ticket_id:
        return "<html><body><h2>Erreur</h2><p>ID manquant</p></body></html>", 400
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE tickets SET status = 'en attente' WHERE id = %s;", (ticket_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        return f"<html><body><h2>Erreur</h2><p>Impossible de mettre à jour le statut : {e}</p></body></html>", 500
    try:
        resp = requests.post(N8N_WEBHOOK_URL, json={"ticket_id": int(ticket_id)})
        if not resp.ok:
            return f"<html><body><h2>Erreur</h2><p>Appel n8n échoué : {resp.status_code}</p></body></html>", 500
    except Exception as e:
        return f"<html><body><h2>Erreur</h2><p>Erreur n8n : {e}</p></body></html>", 500
    return redirect(url_for("tickets.check_tickets"))


@tickets_bp.route("/api_ticket_image/<int:ticket_id>")
def api_ticket_image(ticket_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT image FROM tickets WHERE id = %s", (ticket_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row or row[0] is None:
            return jsonify({"success": False, "error": "Image non trouvée"}), 404
        raw = row[0]
        if isinstance(raw, memoryview):
            img_bytes = raw.tobytes()
        elif isinstance(raw, (bytes, bytearray)):
            img_bytes = bytes(raw)
        else:
            return jsonify({"success": False, "error": "Image invalide"}), 404
        if not img_bytes:
            return jsonify({"success": False, "error": "Image vide"}), 404
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        return jsonify({"success": True, "url": f"data:image/jpeg;base64,{b64}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@tickets_bp.route("/pictbyid/<int:ticket_id>")
def pictbyid(ticket_id):
    conn = cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT image, filename FROM tickets WHERE id = %s", (ticket_id,))
        row = cur.fetchone()
        if not row or row[0] is None:
            return "Image non trouvée", 404
        raw_image, filename = row
        if isinstance(raw_image, memoryview):
            image_bytes = raw_image.tobytes()
        elif isinstance(raw_image, (bytes, bytearray)):
            image_bytes = bytes(raw_image)
        else:
            return "Image invalide", 404
        if not image_bytes:
            return "Image vide", 404
        served_name = filename if filename else f"ticket_{ticket_id}.bin"
        mimetype = mimetypes.guess_type(served_name)[0] or "application/octet-stream"

        def generate():
            for i in range(0, len(image_bytes), 65536):
                yield image_bytes[i:i + 65536]

        return Response(generate(), mimetype=mimetype, headers={
            "Content-Disposition": f'inline; filename="{served_name}"',
            "Cache-Control": "public, max-age=604800, immutable",
        })
    except Exception as e:
        return f"Erreur serveur : {e}", 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@tickets_bp.route("/upload_error")
def upload_error():
    msg = request.args.get("msg", "Erreur inconnue lors de l'upload.")
    return f"""
    <html lang='fr'><head><meta name='viewport' content='width=device-width, initial-scale=1'>
    <meta http-equiv='Content-Language' content='fr'><title>Erreur upload</title>
    <style>
    body {{ font-family: sans-serif; margin: 1em; text-align: center; }}
    .header {{ display: flex; gap: 1em; align-items: center; justify-content: center; margin-bottom: 1em; }}
    .header a {{ text-decoration: none; color: #1976d2; font-weight: bold; font-size: 1.1em; }}
    .btn {{ display: inline-block; margin-top: 2em; padding: 1em 2em; background: #1976d2; color: #fff;
            border: none; border-radius: 0.7em; font-size: 1.1em; text-decoration: none; font-weight: bold; }}
    .btn:hover {{ background: #125ea2; }}
    </style></head><body>
    <div class='header'>
        <a href='/'>🏠 Accueil</a><a href='/upload_ticket'>📷 Envoyer</a>
        <a href='/check_tickets'>📋 Liste</a><a href='/ask'>🧠 IA</a>
    </div>
    <h2>Erreur lors de l'upload</h2>
    <p style='color:red;font-size:1.2em;'>{msg}</p>
    <a class='btn' href='/upload_ticket'>Réessayer</a>
    <a class='btn' href='/check_tickets'>Voir la liste</a>
    </body></html>
    """
