"""
Mistral AI Studio Agent & Workflow Registration Module.

Registers the ACPR Text-to-Data Agent persistently on the Mistral AI Studio platform
using client.beta.agents.create() with full tool definitions (Function tools, Code Interpreter).

Once registered, any Vibe user or external application can call the agent directly using:
    client.agents.complete(agent_id=AGENT_ID, messages=[...])
or:
    client.beta.conversations.start(agent_id=AGENT_ID, inputs=...)
"""

import os
import sys
import json
from typing import Dict, Any, List, Optional

import config  # Ensures client-python SDK is in sys.path

from mistralai.client import Mistral
from mistralai.client.models import Function, Tool

AGENT_NAME = "acpr-text-to-data-agent"
AGENT_DESCRIPTION = "Agent réglementaire ACPR / Solvabilité II pour l'extraction de données financières et coordonnées QRT."

# ── Function Tool Definitions for AI Studio Registration ────────────────

TOOLS_DECLARATIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_entity_info",
            "description": "Obtient les informations (code LEI, nom complet, pays, secteur) d'un assureur par son nom.",
            "parameters": {
                "type": "object",
                "required": ["entity_name"],
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "Nom ou extrait de nom de l'assureur (ex: 'AXA', 'ALLIANZ', 'GENERALI')"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_schema_metadata",
            "description": "Cherche dans le dictionnaire réglementaire ACPR les correspondances pour un concept financier.",
            "parameters": {
                "type": "object",
                "required": ["concept"],
                "properties": {
                    "concept": {
                        "type": "string",
                        "description": "Concept financier en français (ex: 'fonds propres', 'total actif', 'ratio solvabilité')"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_qrt_coordinates",
            "description": "Extrait les coordonnées QRT Solvabilité II exactes (tableau, ligne, colonne) pour une table et colonne.",
            "parameters": {
                "type": "object",
                "required": ["table_name", "column_name"],
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Nom de la table (ex: 's2301_own_funds', 's0201_balance_sheet')"
                    },
                    "column_name": {
                        "type": "string",
                        "description": "Nom de la colonne (ex: 'total_eligible_own_funds_scr', 'total_assets')"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": "Exécute une requête SQL SELECT sécurisée sur la base réglementaire ACPR.",
            "parameters": {
                "type": "object",
                "required": ["sql_query"],
                "properties": {
                    "sql_query": {
                        "type": "string",
                        "description": "Requête SQL SELECT valide"
                    }
                }
            }
        }
    }
]

INSTRUCTIONS = """Tu es l'agent officiel ACPR Text-to-Data sur Mistral AI Studio.
Ton rôle est de répondre aux requêtes financières réglementaires (Solvabilité II / SURFI) avec une précision absolue.

Pour toute question utilisateur :
1. Appelle get_entity_info() pour obtenir le LEI et le nom officiel.
2. Appelle get_schema_metadata() pour identifier la table SQL et le code QRT.
3. Appelle query_database() pour exécuter la requête SQL SELECT.
4. Appelle lookup_qrt_coordinates() pour extraire les coordonnées cellulaires QRT.
5. Renvoie la valeur exacte, le code LEI, le SQL et les coordonnées QRT (tableau, ligne, colonne).

Ne jamais halluciner de chiffre ni de code réglementaire. Utilise exclusivement les outils enregistrés."""


class AIStudioAgentRegistry:
    """Manages AI Studio persistent Agent registration and updates."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.MISTRAL_API_KEY
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY obligatoire pour la gestion des agents AI Studio.")
        self.client = config.get_mistral_client(api_key=self.api_key)

    def register_or_get_agent(self) -> Dict[str, Any]:
        """
        Creates or retrieves the persistent ACPR Agent on Mistral AI Studio platform.
        """
        agent = self.client.beta.agents.create(
            model=config.MODEL_LARGE,
            name=AGENT_NAME,
            description=AGENT_DESCRIPTION,
            instructions=INSTRUCTIONS,
            tools=TOOLS_DECLARATIONS,
        )
        return {"agent_id": agent.id, "name": agent.name, "model": agent.model}


def register_agent(api_key: str = None) -> str:
    """CLI / Function helper to register the Agent on AI Studio."""
    key = api_key or config.MISTRAL_API_KEY
    if not key:
        print("⚠️ MISTRAL_API_KEY absente. Définissez MISTRAL_API_KEY dans votre fichier .env")
        return ""

    client = config.get_mistral_client(api_key=key)

    try:
        agent = client.beta.agents.create(
            model=config.MODEL_LARGE,
            name=AGENT_NAME,
            description=AGENT_DESCRIPTION,
            instructions=INSTRUCTIONS,
            tools=TOOLS_DECLARATIONS,
        )
        print(f"\n✅ Agent ACPR enregistré avec succès sur Mistral AI Studio !")
        print(f"   Agent ID   : {agent.id}")
        print(f"   Nom        : {agent.name}")
        print(f"   Modèle     : {agent.model}")
        print(f"   Outils     : {len(TOOLS_DECLARATIONS)} fonctions déclarées\n")
        print(f"💡 N'importe quel utilisateur Vibe Coding ou client SDK peut maintenant appeler :")
        print(f"   client.agents.complete(agent_id='{agent.id}', messages=[...])\n")
        return agent.id
    except Exception as e:
        print(f"❌ Erreur lors de l'enregistrement de l'agent sur AI Studio : {e}")
        return ""

if __name__ == "__main__":
    register_agent()
