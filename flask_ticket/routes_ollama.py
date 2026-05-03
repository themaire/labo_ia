"""
Blueprint Flask — Expérimentations Ollama.

Routes :
  GET  /ask                          interface IA principale
  GET  /history                      page historique des tests
  GET  /api_history_list             liste JSON des 100 derniers tests
  GET  /api_history_detail/<id>      détail JSON d'un test
  DELETE /api_history_delete/<id>    suppression d'un test
  POST /api_list_models              liste des modèles d'un serveur Ollama
  POST /api_ollama                   envoi d'une requête à Ollama (AJAX)
"""

import os
import json as _json
import time

import psycopg2
import requests as req
from flask import Blueprint, request, jsonify, render_template

try:
    from .config import (
        OLLAMA_SERVERS, OLLAMA_MODELS, DEFAULT_SERVER_IP,
        OLLAMA_PORT, get_ollama_url,
    )
except ImportError:
    from config import (
        OLLAMA_SERVERS, OLLAMA_MODELS, DEFAULT_SERVER_IP,
        OLLAMA_PORT, get_ollama_url,
    )

ollama_bp = Blueprint("ollama", __name__)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _ollama_db_conn():
    """Connexion PostgreSQL sur le schéma 'ollama' (historique des tests)."""
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST"),
        user=os.environ.get("POSTGRES_USER"),
        password=os.environ.get("POSTGRES_PASSWORD"),
        dbname=os.environ.get("POSTGRES_DB"),
        options="-c search_path=ollama",
    )


def assemble_ollama_response(raw_text: str) -> str:
    """Reconstruit le texte final à partir des lignes JSON de réponse Ollama."""
    responses = []
    for line in raw_text.strip().splitlines():
        try:
            obj = _json.loads(line)
            if "response" in obj:
                responses.append(obj["response"])
        except Exception:
            continue
    return "".join(responses)


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@ollama_bp.route("/ask", methods=["GET"])
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
    return render_template(
        "index.html",
        result=None,
        models=models,
        selected_model=selected_model,
        need_prompt=need_prompt,
        prompt="",
        servers=OLLAMA_SERVERS,
        selected_server=selected_server,
        show_history_link=True,
    )


@ollama_bp.route("/history", methods=["GET"])
def history():
    return render_template("history.html")


@ollama_bp.route("/api_history_list", methods=["GET"])
def api_history_list():
    try:
        conn = _ollama_db_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, created_at, finished_at, duration_seconds,
                   server_ip, model, prompt, options, result, error
            FROM model_tests
            ORDER BY created_at DESC
            LIMIT 100
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        result = []
        for r in rows:
            result.append({
                "id": r[0],
                "created_at": r[1].strftime("%Y-%m-%d %H:%M:%S"),
                "finished_at": r[2].strftime("%Y-%m-%d %H:%M:%S") if r[2] else None,
                "duration_seconds": float(r[3]) if r[3] else None,
                "server_ip": r[4],
                "model": r[5],
                "prompt": r[6],
                "options": r[7],
                "result": r[8],
                "error": r[9],
            })
        return jsonify(result)
    except Exception:
        return jsonify([]), 500


@ollama_bp.route("/api_history_detail/<int:test_id>", methods=["GET"])
def api_history_detail(test_id):
    try:
        conn = _ollama_db_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, created_at, finished_at, duration_seconds,
                   server_ip, model, prompt, options, image_base64, result, error
            FROM model_tests WHERE id = %s
        """, (test_id,))
        r = cur.fetchone()
        cur.close()
        conn.close()
        if not r:
            return jsonify({}), 404
        return jsonify({
            "id": r[0],
            "created_at": r[1].strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": r[2].strftime("%Y-%m-%d %H:%M:%S") if r[2] else None,
            "duration_seconds": float(r[3]) if r[3] else None,
            "server_ip": r[4],
            "model": r[5],
            "prompt": r[6],
            "options": r[7],
            "image_base64": r[8],
            "result": r[9],
            "error": r[10],
        })
    except Exception:
        return jsonify({}), 500


@ollama_bp.route("/api_history_delete/<int:test_id>", methods=["DELETE"])
def api_history_delete(test_id):
    try:
        conn = _ollama_db_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM model_tests WHERE id = %s", (test_id,))
        conn.commit()
        cur.close()
        conn.close()
        return "", 204
    except Exception as e:
        return str(e), 500


@ollama_bp.route("/api_list_models", methods=["POST"])
def api_list_models():
    data = request.get_json() or {}
    server_ip = data.get("server_ip", DEFAULT_SERVER_IP)
    try:
        url = f"http://{server_ip}:{OLLAMA_PORT}/api/tags"
        r = req.get(url, timeout=10)
        r.raise_for_status()
        tags = r.json().get("models", [])
        models = []
        for tag in tags:
            name = tag["name"]
            found = next((m for m in OLLAMA_MODELS if m[0] == name), None)
            if found:
                models.append(found)
            else:
                models.append((name, name, False, False))
        return jsonify(models)
    except Exception:
        return jsonify([]), 500


@ollama_bp.route("/api_ollama", methods=["POST"])
def api_ollama():
    data = request.get_json() or {}
    selected_model = data.get("model", OLLAMA_MODELS[0][0])
    prompt = data.get("prompt", "")
    img_b64 = data.get("image", "")
    server_ip = data.get("server", DEFAULT_SERVER_IP)
    options = data.get("options", None)
    preprocess = data.get("preprocess", False)

    print("--- Nouvelle soumission utilisateur (AJAX) ---")
    print(f"Modèle : {selected_model} | Serveur : {server_ip}")
    print(f"Prompt : '{prompt}' | Image : {len(img_b64)} car. | Prétraitement : {preprocess}")
    print("----------------------------------------------")

    # Prétraitement image
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
                try:
                    from image_utils import preprocess as img_preprocess
                except ImportError:
                    from flask_ticket.image_utils import preprocess as img_preprocess
                processed = img_preprocess(img)
                _, buf = cv2.imencode(".png", processed)
                img_b64 = base64.b64encode(buf).decode("utf-8")
                image_height, image_width = processed.shape[:2]
            else:
                image_height, image_width = img.shape[:2]
        except Exception as e:
            print(f"Erreur prétraitement image : {e}")

    # Insertion historique
    test_id = None
    try:
        conn = _ollama_db_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO model_tests
                (server_ip, model, prompt, options, image_base64, image_preprocessed, image_width, image_height)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (
            server_ip, selected_model, prompt,
            _json.dumps(options) if options else None,
            img_b64 if img_b64 else None,
            bool(preprocess) if img_b64 else None,
            image_width, image_height,
        ))
        test_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[Historique] Erreur insertion : {e}")

    # Appel Ollama
    payload = {
        "model": selected_model,
        "prompt": prompt,
        "images": [img_b64] if img_b64 else [],
    }
    if options is not None:
        payload["options"] = options

    ollama_url = get_ollama_url(server_ip)
    try:
        t0 = time.time()
        response = req.post(ollama_url, json=payload, headers={"Content-Type": "application/json"}, timeout=400)
        t1 = time.time()
        response.raise_for_status()
        assembled = assemble_ollama_response(response.text)
        elapsed = t1 - t0

        # Mise à jour historique (succès)
        if test_id is not None:
            try:
                conn = _ollama_db_conn()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE model_tests
                    SET finished_at = NOW(), duration_seconds = %s, result = %s
                    WHERE id = %s;
                """, (elapsed, assembled, test_id))
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print(f"[Historique] Erreur update : {e}")

        return (
            f"\n\n---\nTemps de génération : {elapsed:.2f} secondes"
            "\n---\nTexte reconstitué :\n" + assembled
        )
    except Exception as e:
        # Mise à jour historique (erreur)
        if test_id is not None:
            try:
                conn = _ollama_db_conn()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE model_tests SET finished_at = NOW(), error = %s WHERE id = %s;
                """, (str(e), test_id))
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e2:
                print(f"[Historique] Erreur update (erreur) : {e2}")
        return f"Erreur lors de l'appel à Ollama : {e}", 500
