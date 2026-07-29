"""
Mistral Vibe (Le Chat) Native Agent Creator.

Creates a native Agent for Mistral Vibe (chat.mistral.ai / Le Chat) by:
1. Exporting and uploading the ACPR data catalog (acpr_data.json) to Mistral AI Studio via client.files.upload()
2. Creating an Agent on AI Studio configured with the native Code Interpreter tool ({"type": "code_interpreter"})

Once created, any user on Mistral Vibe (Le Chat) can select this Agent and chat with it directly.
Mistral Vibe will execute Python code in its sandbox to query acpr_data.json and return exact financial values and Solvency II QRT coordinates.
"""

import os
import json
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any

import config  # Ensures sys.path is set for client-python SDK

from mistralai.client import Mistral

DB_PATH = Path(config.DB_PATH)
JSON_DATA_PATH = Path("acpr_data.json")


def export_db_to_json():
    """Exports SQLite database tables into acpr_data.json for Code Interpreter."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    tables = ["entities", "s2301_own_funds", "s0201_balance_sheet", "data_dictionary"]
    data = {}
    for t in tables:
        cursor.execute(f"SELECT * FROM {t}")
        cols = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        data[t] = [dict(zip(cols, r)) for r in rows]

    with open(JSON_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"   ✅ Exporté '{DB_PATH.name}' vers '{JSON_DATA_PATH.name}'")


def setup_vibe_agent(api_key: Optional[str] = None) -> Dict[str, Any]:
    """Uploads acpr_data.json to AI Studio and creates a Mistral Vibe Code Interpreter Agent."""
    key = api_key or config.MISTRAL_API_KEY
    if not key:
        print("⚠️ MISTRAL_API_KEY absente dans le fichier .env")
        return {}

    client = config.get_mistral_client(api_key=key)

    if not DB_PATH.exists():
        print(f"❌ Base de données introuvable à {DB_PATH}")
        return {}

    print(f"\n1. Export et téléversement des données prudentielles vers Mistral AI Studio...")
    export_db_to_json()

    with open(JSON_DATA_PATH, "rb") as f:
        file_obj = client.files.upload(
            file={
                "file_name": JSON_DATA_PATH.name,
                "content": f,
            },
            purpose="code_interpreter",
        )

    file_id = file_obj.id
    print(f"   ✅ Fichier téléversé sur AI Studio ! File ID : {file_id}")

    instructions = f"""Tu es l'agent officiel ACPR (Solvabilité II / SURFI) sur Mistral Vibe.
Tu as accès aux données prudentielles dans le fichier `{JSON_DATA_PATH.name}` via l'outil Code Interpreter.

Pour chaque question utilisateur :
1. Utilise le Code Interpreter pour charger et analyser `{JSON_DATA_PATH.name}` en Python.
2. Le fichier contient les tables :
   - `entities` : liste des assureurs (id, lei_code, name, short_code, country, sector)
   - `s2301_own_funds` : QRT S.23.01 (Fonds propres éligibles SCR, MCR, Tier 1, Tier 2, Tier 3)
   - `s0201_balance_sheet` : QRT S.02.01 (Bilan prudentiel : Total actif, placements, provisions)
   - `data_dictionary` : dictionnaire des métadonnées et coordonnées QRT (tableau, ligne, colonne)
3. Exécute le script Python approprié pour extraire la valeur exacte et le LEI.
4. Récupère les coordonnées QRT (Tableau QRT, Code Ligne, Code Colonne) depuis `data_dictionary`.
5. Renvoie une réponse professionnelle claire contenant :
   - Nom de l'entité & Code LEI
   - Valeur exacte et formatée (ex: 52,45 Mds EUR)
   - Coordonnées QRT (Tableau, Ligne, Colonne)
   - Le code Python exécuté

Ne jamais inventer de chiffre ni de code QRT."""

    print("\n2. Création de l'Agent Mistral Vibe (Code Interpreter) sur AI Studio...")
    agent = client.beta.agents.create(
        model=config.MODEL_LARGE,
        name="acpr-text-to-data-vibe",
        description="Agent prudentiel ACPR Solvabilité II pour Mistral Vibe (Le Chat) avec Code Interpreter et données JSON intégrées.",
        instructions=instructions,
        tools=[{"type": "code_interpreter"}],
    )

    print(f"\n🎉 AGENT MISTRAL VIBE (LE CHAT) CRÉÉ AVEC SUCCÈS !")
    print(f"   Agent ID    : {agent.id}")
    print(f"   Nom         : {agent.name}")
    print(f"   Outil Native: Code Interpreter (Sandbox Python AI Studio)")
    print(f"   Fichier     : {JSON_DATA_PATH.name} (File ID: {file_id})\n")
    print(f"💡 Dans Mistral Vibe (chat.mistral.ai) :")
    print(f"   1. Ouvrez la liste des Agents dans Le Chat")
    print(f"   2. Sélectionnez 'acpr-text-to-data-vibe' (id: {agent.id})")
    print(f"   3. Posez directement votre question : 'peux tu me fournir le montant des fonds propres d'axa'\n")

    return {
        "agent_id": agent.id,
        "name": agent.name,
        "file_id": file_id,
    }


if __name__ == "__main__":
    setup_vibe_agent()
