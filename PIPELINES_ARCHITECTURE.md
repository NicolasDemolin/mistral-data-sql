# Architecture des Pipelines d'IA – Projet ACPR Text-to-Data

Ce projet implémente trois méthodes distinctes (pipelines) pour interroger la base de données prudentielle (Solvabilité II / DPM) en utilisant l'Intelligence Artificielle de Mistral.

Ce document décrit comment et pourquoi utiliser chacune de ces approches.

---

## 1. Pipeline MCP (Model Context Protocol)

**Fichier principal :** `mcp_server.py`

Le **Model Context Protocol (MCP)** est un standard open-source permettant de connecter des assistants IA (comme Cursor, Claude Desktop, ou un agent local) à des sources de données externes via des "Tools" (Outils) standardisés.

- **Fonctionnement :** Le fichier `mcp_server.py` utilise la librairie `FastMCP` pour exposer les fonctions de `tools.py` (`query_database`, `get_entity_info`, etc.) sous forme d'outils MCP.
- **Cas d'usage :** Idéal pour un développeur ou un analyste utilisant un IDE comme Cursor. L'IA de l'éditeur de code peut directement "lire" la base de données, faire ses propres requêtes SQL, et vous aider à coder ou à analyser en temps réel sans quitter l'éditeur.
- **Avantage :** Intégration native avec les meilleurs outils de l'écosystème IA actuel. Exécution locale sécurisée via le transport `stdio`.

---

## 2. Pipeline Agent Mistral (Mistral Vibe / Le Chat)

**Fichier principal :** `vibe_agent_setup.py`

Ce pipeline repose sur la création d'un **Agent autonome hébergé sur Mistral AI Studio** et utilisable via l'interface conversationnelle *Le Chat* (chat.mistral.ai).

- **Fonctionnement :** 
  1. Le script exporte la base de données locale (`DPM_lite.db`) vers un fichier plat `acpr_data.json`.
  2. Il upload ce fichier sur le cloud de Mistral via l'API.
  3. Il crée un Agent doté de l'outil natif **"Code Interpreter"** et de directives précises (Instructions).
- **Cas d'usage :** Idéal pour des utilisateurs finaux (métiers) qui n'ont aucune compétence technique. Ils ouvrent *Le Chat*, sélectionnent l'Agent ACPR, et posent leurs questions en langage naturel.
- **Avantage :** L'agent écrit et exécute son propre code Python dans une sandbox cloud (Mistral) pour parcourir le JSON et trouver la réponse. Aucune infrastructure serveur n'est requise de votre côté une fois l'Agent créé.

---

## 3. Pipeline Mistral Workflow (Orchestration Durable)

**Dossier principal :** `workflow/` (anciennement `mistral_studio_workflow.py`) & `worker.py`

Le SDK **Mistral Workflows** permet de créer des processus asynchrones, déterministes et hautement résilients. Contrairement à l'Agent qui improvise du Python, le Workflow suit un graphe d'activités précis.

- **Fonctionnement :**
  1. **discover_schema :** Analyse sémantique de la question pour trouver le contexte.
  2. **generate_sql :** Le LLM (ex: Codestral) écrit la requête SQL.
  3. **execute_query :** Le code exécute la requête sur la base locale en lecture seule.
  4. **evaluate_result (Juge LLM) :** Une boucle d'auto-correction innovante. Un LLM évalue si le résultat SQL a bien répondu à la question. Si ce n'est pas le cas, le workflow recommence à l'étape 2 en lui donnant le motif de l'erreur.
  5. **synthesize_result :** Formate la réponse JSON finale.
- **Cas d'usage :** Idéal pour être appelé de manière programmatique via API par d'autres applications métier (ex: un Dashboard React). L'infrastructure "Mistral Control Plane" orchestre le processus, mais l'exécution (le `worker.py`) se fait sur **vos** serveurs (ex: Droplet DigitalOcean), garantissant que la base de données ne fuite pas sur internet.
- **Avantage :** Robustesse absolue. Gestion des retries, auto-correction par l'IA, format de sortie strict (JSON), et données conservées en local.
