# Labo IA - Flask Ticket Carburant

Cette application Flask permet d'uploader une photo et d'envoyer un prompt via un serveur Ollama local ou distant (modèle LLM multimodal).

## Fonctionnalités
- Sélection du serveur Ollama (depuis une liste dans le script)
- Choix du modèle
- Zone de prompt si nécessaire
- Upload d'image (obligatoire ou optionnel selon le modèle)
- Affichage du résultat
- Feedback asynchrone ("Veuillez patienter...")

## Installation
1. Cloner ce dépôt ou copier les fichiers dans un dossier.
2. Créer un environnement virtuel Python :
   
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # ou
   source venv/bin/activate  # Linux/Mac
   ```
3. Installer les dépendances :
   
   ```bash
   pip install -r requirements.txt
   ```

## Utilisation
1. Lancer le serveur Flask :
   
   ```bash
   source .venv/bin/activate
   python flask_ticket/app.py
   ```

   ```powershell
   venv\Scripts\activate 
   python flask_ticket/app.py
   ```

2. Ouvrir votre navigateur à l'adresse : http://localhost:5000
3. Sélectionner le serveur, le modèle, ajouter un prompt si besoin, et uploader une image.
4. Cliquer sur "Analyser" pour obtenir le résultat JSON.

## Configuration
- Les adresses IP des serveurs Ollama sont configurées dans `app.py` (variable `OLLAMA_SERVERS`).
- Les modèles disponibles sont listés dans `OLLAMA_MODELS`.

## Dépendances
- Flask
- requests

## Remarques
- Le serveur Ollama doit être accessible sur le réseau local et disposer des modèles nécessaires.
- Le port utilisé par défaut est 11434.
- Projet expérimental pour laboratoire IA local.

## Auteur
Nicolas ELIE
Github Copilot