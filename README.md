# Labo IA - Flask Ticket Carburant

Cette application Flask permet d'uploader une photo et d'envoyer un prompt via un serveur Ollama local ou distant (modèle LLM multimodal).

## Sommaire
- [Labo IA - Flask Ticket Carburant](#labo-ia---flask-ticket-carburant)
  - [Sommaire](#sommaire)
  - [Architecture](#architecture)
  - [Authentification et sécurité](#authentification-et-sécurité)
    - [Premier démarrage](#premier-démarrage)
    - [Connexion](#connexion)
    - [Gestion des utilisateurs](#gestion-des-utilisateurs)
    - [Gestion des serveurs et modèles Ollama](#gestion-des-serveurs-et-modèles-ollama)
      - [**`/settings/servers`** — Serveurs Ollama](#settingsservers--serveurs-ollama)
      - [**`/settings/models`** — Modèles Ollama](#settingsmodels--modèles-ollama)
    - [Protection des routes](#protection-des-routes)
    - [Configuration](#configuration)
    - [Mode debug](#mode-debug)
    - [✅ Système testé et opérationnel](#-système-testé-et-opérationnel)
  - [Nouveautés](#nouveautés)
    - [2026-05 — Authentification JWT et gestion des utilisateurs](#2026-05--authentification-jwt-et-gestion-des-utilisateurs)
    - [2026-05 — Gestion dynamique des serveurs et modèles Ollama](#2026-05--gestion-dynamique-des-serveurs-et-modèles-ollama)
    - [Autres évolutions récentes](#autres-évolutions-récentes)
  - [Fonctionnalités](#fonctionnalités)
  - [Installation](#installation)
  - [Utilisation](#utilisation)
    - [Premier démarrage](#premier-démarrage-1)
    - [Utilisation courante](#utilisation-courante)
  - [Configuration](#configuration-1)
  - [Historique des tests](#historique-des-tests)
  - [Dépendances](#dépendances)
  - [Remarques](#remarques)
  - [Auteur](#auteur)

## Architecture

L'application est découpée en modules Flask (Blueprints) pour séparer les deux grandes fonctionnalités :

```
flask_ticket/
│
├── app.py                  ← Point d'entrée : création de l'app Flask,
│                              enregistrement des blueprints, page d'accueil
│
├── config.py               ← Configuration partagée :
│                              serveurs Ollama, modèles, get_db_connection()
│
├── auth.py                 ← Authentification JWT :
│                              /login  /logout  /welcome  /settings
│                              @jwt_required  @web_login_required
│
├── routes_ollama.py        ← Blueprint « Ollama » (expérimentations IA)
│   │                          /ask  /history
│   │                          /api_ollama  /api_list_models
│   └──────────────────────    /api_history_list  /api_history_detail  /api_history_delete
│
├── routes_tickets.py       ← Blueprint « Tickets » (traitement des tickets de caisse)
│   │                          /upload_ticket  /check_tickets
│   │                          /delete_ticket  /process_ticket
│   └──────────────────────    /api_ticket_image  /pictbyid  /upload_error
│
├── auth.py                 ← (voir ci-dessus)
├── image_utils.py          ← Prétraitement image (contraste, N&B, etc.)
├── sql_create_users_table.sql        ← Script SQL pour créer la table users
├── sql_create_ollama_servers_table.sql ← Script SQL pour créer la table ollama.servers
├── sql_create_ollama_models_table.sql  ← Script SQL pour créer la table ollama.models
├── templates/
│   ├── index.html          ← Interface IA (Ollama)
│   ├── history.html        ← Historique des tests
│   ├── login.html          ← Formulaire de connexion
│   ├── welcome.html        ← Page de premier démarrage (création du 1er utilisateur)
│   ├── settings.html       ← Gestion des utilisateurs
│   ├── settings_servers.html ← Gestion des serveurs Ollama
│   └── settings_models.html  ← Gestion des modèles Ollama
│
├── .env                    ← Variables d'environnement (ne pas versionner)
├── .env_exemple            ← Modèle de configuration
└── requirements.txt
```

```
 Navigateur
     │
     ▼
 ┌─────────────────────────────────────────────┐
 │               app.py (Flask)                │
 │  secret_key · auth · blueprints · /         │
 └────────────┬──────────────┬─────────────────┘
              │              │
   ┌──────────▼──────┐  ┌───▼──────────────┐
   │ routes_ollama   │  │  routes_tickets  │
   │  /ask           │  │  /upload_ticket  │
   │  /history       │  │  /check_tickets  │
   │  /api_ollama    │  │  /delete_ticket  │
   │  /api_history_* │  │  /pictbyid       │
   └──────────┬──────┘  └───┬──────────────┘
              │              │
   ┌──────────▼──────────────▼──────────────┐
   │             config.py                  │
   │   get_db_connection()  ·  OLLAMA_*     │
   └──────────┬──────────────┬──────────────┘
              │              │
   ┌──────────▼──┐    ┌──────▼────────┐
   │ PostgreSQL  │    │ Serveur Ollama │
   │  (tickets,  │    │  (LLM local)  │
   │ model_tests)│    └───────────────┘
   └─────────────┘
```

## Authentification et sécurité

L'application intègre un **système d'authentification JWT** complet pour sécuriser l'accès aux routes web et API.

### Premier démarrage

Au premier lancement, l'application détecte automatiquement l'absence d'utilisateurs et vous guide vers la page **`/welcome`** pour créer votre premier compte administrateur :

1. Accédez à `/login`
2. Redirection automatique vers `/welcome` si la table `users` est vide
3. Créez votre compte avec identifiant, mot de passe (min. 6 caractères) et email optionnel
4. Le mot de passe est automatiquement hashé avec **bcrypt**

### Connexion

- **Route web** : `/login` — Formulaire de connexion avec session Flask
- **API JSON** : `POST /login` — Retourne un token JWT (durée : 30 jours par défaut)
- **Déconnexion** : `/logout` — Supprime la session et redirige vers `/login`

### Gestion des utilisateurs

La page **`/settings`** (accessible via le menu "⚙️ Paramètres" présent sur toutes les pages) permet de :
- **Visualiser** tous les utilisateurs (tableau avec ID, identifiant, email, statut actif/inactif, dates de création et dernière connexion)
- **Créer** de nouveaux comptes via une fenêtre modale (bouton ➕)
- **Modifier** un utilisateur existant : clic sur la ligne du tableau → modale d'édition
  - Changement d'identifiant, email
  - Réinitialisation du mot de passe (optionnel)
  - Activation/désactivation du compte
- **Supprimer** un utilisateur via le bouton 🗑️ dans la modale d'édition (avec confirmation)

Interface moderne avec **fenêtres modales** pour toutes les opérations, fermeture par clic extérieur ou touche Échap.

### Gestion des serveurs et modèles Ollama

Depuis la page **`/settings`**, accédez aux pages de configuration Ollama :

#### **`/settings/servers`** — Serveurs Ollama
- **Visualiser** tous les serveurs (nom, IP, port, statut actif/inactif, ordre d'affichage)
- **Créer** un nouveau serveur via modale (nom, IP, port, ordre)
- **Modifier** un serveur : clic sur la ligne → modale d'édition
  - Nom, adresse IP, port (défaut 11434)
  - Activation/désactivation
  - Ordre d'affichage (0 = premier dans la liste)
- **Supprimer** un serveur avec confirmation

#### **`/settings/models`** — Modèles Ollama
- **Visualiser** tous les modèles (nom, libellé, prompt requis, image requise, statut, ordre)
- **Créer** un nouveau modèle via modale
  - Nom du modèle (ex: `gemma4:e4b`)
  - Libellé d'affichage
  - Prompt requis (checkbox)
  - Image obligatoire (checkbox)
  - Description (optionnel)
  - Ordre d'affichage
- **Modifier** un modèle : clic sur la ligne → modale d'édition
- **Supprimer** un modèle avec confirmation

**Avantages** :
- ✅ Configuration dynamique sans modifier le code
- ✅ Lecture automatique depuis la base de données au démarrage
- ✅ Fallback sur valeurs par défaut si les tables n'existent pas
- ✅ Ordre personnalisable pour contrôler l'affichage
- ✅ Activation/désactivation temporaire sans suppression

### Protection des routes

Deux décorateurs sont disponibles pour protéger vos routes :

```python
@web_login_required       # Routes web → redirige vers /login si non connecté
@jwt_required            # Routes API → vérifie le header Authorization: Bearer <token>
```

**Routes protégées** :
- `/` (accueil), `/upload_ticket`, `/check_tickets` : authentification web
- `/pictbyid/<id>` : authentification JWT (pour les webhooks n8n)
- `/settings` : authentification web (gestion utilisateurs)

### Configuration

Créez les tables nécessaires en exécutant les scripts SQL fournis :

**1. Table des utilisateurs** (schéma `pictures`) :

```bash
psql -h 192.168.1.50 -U postgres -d ia_workflows -f flask_ticket/sql_create_users_table.sql
```

**2. Table des serveurs Ollama** (schéma `ollama`) :

```bash
psql -h 192.168.1.50 -U postgres -d ia_workflows -f flask_ticket/sql_create_ollama_servers_table.sql
```

**3. Table des modèles Ollama** (schéma `ollama`) :

```bash
psql -h 192.168.1.50 -U postgres -d ia_workflows -f flask_ticket/sql_create_ollama_models_table.sql
```

Les tables `ollama.servers` et `ollama.models` contiennent les données initiales migrées depuis l'ancien `config.py` (Raspberry Pi 5, Serveur Ollama, modèles ticket_carburant, gemma, etc.).

Variables d'environnement à ne pas oublier de changer dans `.env` :

```env
JWT_SECRET_KEY=votre-cle-secrete-aleatoire-longue-et-robuste
JWT_EXPIRY_DAYS=30
FLASK_SECRET_KEY=une-autre-cle-secrete-differente-pour-les-sessions
DEBUG_AUTH=False  # Mettre True pour activer les logs de débogage
```

### Mode debug

Le module d'authentification intègre un **système de logs détaillés** activable via la variable `DEBUG_AUTH` :

- **`DEBUG_AUTH=True`** : affiche dans la console Flask tous les détails de l'authentification (recherche utilisateur, vérification mot de passe, génération/décodage JWT, état des sessions)
- **`DEBUG_AUTH=False`** : mode production, aucun log d'authentification

Utile pour diagnostiquer les problèmes de connexion ou de session. Les logs incluent :
- Recherche utilisateur en base de données
- Vérification bcrypt des mots de passe
- Génération et décodage des tokens JWT
- Contenu des sessions Flask
- Raisons d'échec de connexion

### ✅ Système testé et opérationnel

L'authentification JWT a été **testée avec succès** en mai 2026 :
- ✅ Création de compte via `/welcome`
- ✅ Connexion/déconnexion web
- ✅ Persistance des sessions Flask
- ✅ Validation des tokens JWT (format conforme RFC 7519)
- ✅ Protection des routes sensibles
- ✅ Gestion multi-utilisateurs via `/settings`

Le système gère correctement les claims JWT (notamment `sub` en string selon la spec) et les timestamps Unix pour `iat`/`exp`.

## Nouveautés

### 2026-05 — Authentification JWT et gestion des utilisateurs

- **Système d'authentification complet** : JWT (API) + sessions Flask (web)
- **Page de premier démarrage** (`/welcome`) : création automatique du premier utilisateur
- **Gestion des utilisateurs** (`/settings`) : création, modification, suppression via modales
- **Protection des routes** : décorateurs `@web_login_required` et `@jwt_required`
- **Sécurité renforcée** : mots de passe hashés avec bcrypt, tokens longue durée (30 jours)
- **Workflow fluide** : détection automatique de l'absence d'utilisateurs au démarrage

### 2026-05 — Gestion dynamique des serveurs et modèles Ollama

- **Configuration en base de données** : serveurs et modèles Ollama stockés dans PostgreSQL (schéma `ollama`)
- **Pages de gestion dédiées** : `/settings/servers` et `/settings/models` avec interface modale
- **CRUD complet** : création, modification, suppression via interface web
- **Lecture dynamique** : `config.py` charge automatiquement depuis la BDD au démarrage
- **Paramètres avancés** : ordre d'affichage, activation/désactivation, description des modèles
- **Migration automatique** : scripts SQL avec données initiales pré-remplies
- **Fallback intelligent** : valeurs par défaut si les tables n'existent pas encore


### Autres évolutions récentes
- Amélioration du workflow d'upload et de rognage côté client (plus fluide sur mobile et desktop).
- Affichage enrichi des métadonnées images dans l'historique.
- Correction de bugs mineurs sur la suppression et le reload des tests.

## Fonctionnalités
- **Authentification sécurisée** : système JWT + sessions, gestion des utilisateurs, page de premier démarrage
- **Gestion dynamique Ollama** : configuration des serveurs et modèles via interface web (`/settings/servers`, `/settings/models`)
- **Paramétrage avancé** : ordre d'affichage, activation/désactivation, lecture automatique depuis PostgreSQL
- Sélection du serveur Ollama (chargé dynamiquement depuis la base de données)
- Choix du modèle (chargé dynamiquement depuis la base de données)
- Zone de prompt si nécessaire (selon configuration du modèle)
- Upload d'image (obligatoire ou optionnel selon le modèle)
- **Rognage/crop côté client** avant envoi (Croppr.js, mobile/desktop, workflow fluide)
- Affichage du résultat
- Feedback asynchrone ("Veuillez patienter...")
- **Historique des tests** : visualisation, suppression, détails, reload, zoom image, copie, affichage des métadonnées (prétraitement, résolution...)
- **Prévisualisation et zoom 1:1** des images uploadées ou rognées, y compris dans la liste des tickets
- **Nommage intelligent** des fichiers rognés : nom original + _cropped + extension

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

4. Configurer l'environnement :
   - Copier `.env_exemple` vers `.env`
   - Renseigner les paramètres PostgreSQL (`POSTGRES_HOST`, `POSTGRES_USER`, etc.)
   - Générer et définir `JWT_SECRET_KEY` et `FLASK_SECRET_KEY` (clés aléatoires longues)

5. Créer les tables en base de données :
   
   ```bash
   # Table des utilisateurs (schéma pictures)
   psql -h 192.168.1.50 -U postgres -d ia_workflows -f flask_ticket/sql_create_users_table.sql
   
   # Tables de configuration Ollama (schéma ollama)
   psql -h 192.168.1.50 -U postgres -d ia_workflows -f flask_ticket/sql_create_ollama_servers_table.sql
   psql -h 192.168.1.50 -U postgres -d ia_workflows -f flask_ticket/sql_create_ollama_models_table.sql
   ```

## Utilisation

### Premier démarrage
1. Lancer le serveur Flask :
   
   ```bash
   source .venv/bin/activate
   python flask_ticket/app.py
   ```

   ```powershell
   .venv\Scripts\activate 
   python flask_ticket/app.py
   ```

2. Ouvrir votre navigateur à l'adresse : http://localhost:5000
3. Vous serez redirigé vers `/welcome` pour créer votre premier compte administrateur
4. Une fois le compte créé, connectez-vous via `/login`

### Utilisation courante
1. Sélectionner le serveur, le modèle, ajouter un prompt si besoin, et uploader une image.
2. Cliquer sur "Analyser" pour obtenir le résultat JSON.
3. Accéder à l'historique via le menu ou `/history`
4. Gérer les utilisateurs via "⚙️ Paramètres" (`/settings`)

## Configuration
- **Serveurs et modèles Ollama** : configurés via les pages web `/settings/servers` et `/settings/models` (stockés en base de données)
- **Lecture dynamique** : `config.py` charge automatiquement les serveurs et modèles depuis PostgreSQL au démarrage
- **Fallback** : si les tables n'existent pas, utilise les valeurs par défaut codées en dur dans `config.py`
- **Variables d'environnement** : connexion à la base de données et clés secrètes dans `.env` (voir `.env_exemple`)

## Historique des tests

L'application conserve un historique complet de chaque test effectué (requête envoyée à Ollama) :

- **Tableau interactif** listant tous les tests passés
- **Suppression** d'un test à la volée (AJAX)
- **Détail complet** d'un test via une fenêtre modale (prompt, options, résultat, image, métadonnées...)
- **Zoom image** : agrandissement 100% ou ajusté, navigation fluide
- **Copie** du résultat JSON ou du prompt en un clic
- **Reload** : relancer un test à partir de l'historique
- **Affichage des métadonnées image** : résolution, prétraitement appliqué ou non
- **Persistance** : l'historique est stocké en base PostgreSQL (table `model_tests`)

Accès : [http://localhost:5000/history](http://localhost:5000/history)

## Dépendances
- Flask
- requests
- psycopg2-binary (PostgreSQL)
- python-dotenv
- bcrypt (hachage des mots de passe)
- PyJWT (authentification JWT)
- Pillow (traitement d'images)

## Remarques
- **Configuration Ollama** : Les serveurs et modèles sont configurés via l'interface web (`/settings/servers`, `/settings/models`) et stockés en base de données PostgreSQL (schéma `ollama`).
- Le serveur Ollama doit être accessible sur le réseau local et disposer des modèles nécessaires.
- Le port utilisé par défaut est 11434 (configurable via l'interface web).
- **Sécurité** : Toutes les routes sont protégées par authentification (web ou JWT). Générez des clés secrètes robustes pour la production.
- La route `/pictbyid/<id>` utilise l'authentification JWT pour permettre l'accès depuis des webhooks externes (n8n).
- **Migration** : Si vous avez déjà une installation existante, exécutez les scripts SQL pour créer les tables `ollama.servers` et `ollama.models`. Les données par défaut seront insérées automatiquement.
- Projet expérimental pour laboratoire IA local.

## Auteur
Nicolas ELIE et 
Github Copilot