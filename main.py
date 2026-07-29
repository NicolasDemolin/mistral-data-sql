#!/usr/bin/env python3
"""
Main CLI Entry Point for ACPR Mistral AI Text-to-Data Studio.

Usage:
  python main.py --query "peux tu me fournir le montant des fonds propres d'axa"
  python main.py --serve
  python main.py --demo           (run all sample queries)
  python main.py --register-agent (register persistent Agent on Mistral AI Studio)
  python main.py --vibe-agent     (create native Mistral Vibe / Le Chat Code Interpreter Agent)
  python main.py --mcp            (run Model Context Protocol MCP Server for Vibe Coding / Cursor)
"""

import argparse
import json
import sys

import config  # triggers sys.path for SDK
from studio_register import register_agent
from vibe_agent_setup import setup_vibe_agent


def print_banner():
    print(f"\n{'='*70}")
    print(f"  ACPR Mistral AI Studio - Text-to-Data Pipeline")
    print(f"  SDK: client-python | beta.agents + RunContext + register_func + MCP")
    if config.MISTRAL_API_KEY:
        print(f"  Mode : Live AI Studio (MISTRAL_API_KEY configurée)")
        if config.MISTRAL_SERVER_URL:
            print(f"  Server URL           : {config.MISTRAL_SERVER_URL}")
        if config.MISTRAL_AGENT_ID:
            print(f"  Agent ID enregistré : {config.MISTRAL_AGENT_ID}")
    else:
        print(f"  Mode : Démonstration Locale (Clé MISTRAL_API_KEY non configurée)")
    print(f"{'='*70}\n")


def run_query(query: str):
    """Run a single query through the full Mistral AI SDK pipeline."""
    from workflow import ACPRWorkflow

    print_banner()
    print(f"  Requête : \"{query}\"\n")
    if config.MISTRAL_API_KEY:
        print(f"  Connexion à Mistral AI Studio...")
    else:
        print(f"  Exécution via RunContext (fonctions locales enregistrées)...")

    workflow = ACPRWorkflow()
    try:
        result = workflow.process_query(query)

        print(f"\n{'─'*70}")
        print(f"  RÉSULTAT RÉGLEMENTAIRE ACPR")
        print(f"{'─'*70}")

        if "entity_name" in result:
            print(f"  Entité              : {result.get('entity_name', 'N/A')}")
            print(f"  LEI                 : {result.get('lei_code', 'N/A')}")
            print(f"  Concept             : {result.get('concept', 'N/A')}")
            print(f"  Valeur              : {result.get('formatted_value', 'N/A')}")
            print(f"  Valeur brute        : {result.get('value', 'N/A')} {result.get('currency', 'EUR')}")
            print(f"  Période             : {result.get('period', 'N/A')}")
            print(f"  QRT Tableau         : {result.get('qrt_table', 'N/A')}")
            print(f"  QRT Ligne           : {result.get('qrt_row', 'N/A')}")
            print(f"  QRT Colonne         : {result.get('qrt_col', 'N/A')}")
            print(f"  Confiance           : {result.get('confidence', 'N/A')}")
            if result.get("sql_query"):
                print(f"\n  SQL exécuté :")
                for line in result["sql_query"].split("\n"):
                    print(f"    {line}")
            if result.get("reasoning"):
                print(f"\n  Raisonnement :")
                for line in result["reasoning"].split("\n"):
                    print(f"    {line}")
        else:
            print(f"  Sortie brute :")
            print(json.dumps(result, indent=2, ensure_ascii=False))

        print(f"\n  Temps d'exécution   : {result.get('execution_time_ms', 'N/A')} ms")

        if result.get("audit_trail"):
            print(f"\n{'─'*70}")
            print(f"  AUDIT TRAIL (entries du RunContext)")
            print(f"{'─'*70}")
            for i, entry in enumerate(result["audit_trail"], 1):
                display = entry[:200] + "..." if len(entry) > 200 else entry
                print(f"  [{i}] {display}")

        if not config.MISTRAL_API_KEY:
            print(f"\n💡 Pour connecter en direct à votre compte AI Studio :")
            print(f"   export MISTRAL_API_KEY='votre_clé_api_mistral'")

        print(f"\n{'='*70}\n")
    finally:
        workflow.cleanup()


def run_demo():
    """Run all sample queries."""
    samples = [
        "peux tu me fournir le montant des fonds propres d'axa",
        "donne moi le montant du total de l'actif du bilan d'axa",
        "quel est le montant des fonds propres tier 1 d'allianz",
    ]
    for query in samples:
        run_query(query)


def serve(port: int):
    """Launch the web studio server."""
    import uvicorn
    print_banner()
    print(f"🚀 Lancement du serveur Web Studio sur http://localhost:{port}\n")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)


def run_mcp():
    """Launch the Model Context Protocol (MCP) server for Vibe Coding / Cursor."""
    from mcp_server import mcp
    print_banner()
    print("🔌 Lancement du serveur MCP (Model Context Protocol) pour Vibe Coding...")
    mcp.run(transport="stdio")


def main():
    parser = argparse.ArgumentParser(description="ACPR Mistral AI Text-to-Data Studio")
    parser.add_argument("--query", "-q", type=str, help="Requête en langage naturel")
    parser.add_argument("--serve", "-s", action="store_true", help="Lancer le serveur Web")
    parser.add_argument("--demo", "-d", action="store_true", help="Exécuter les requêtes de démonstration")
    parser.add_argument("--register-agent", action="store_true", help="Enregistrer l'agent persistant sur AI Studio")
    parser.add_argument("--server-url", type=str, default=None, help="URL du serveur Mistral personnalisé (ex: https://api.mistral.ai)")
    parser.add_argument("--vibe-agent", action="store_true", help="Créer un agent natif Mistral Vibe (Le Chat) avec Code Interpreter")
    parser.add_argument("--mcp", action="store_true", help="Lancer le serveur MCP (Model Context Protocol) pour Vibe Coding")
    parser.add_argument("--port", type=int, default=8000, help="Port du serveur (défaut: 8000)")
    args = parser.parse_args()

    if args.server_url:
        config.MISTRAL_SERVER_URL = args.server_url.strip()

    if args.vibe_agent:
        setup_vibe_agent()
    elif args.register_agent:
        register_agent(server_url=args.server_url)
    elif args.mcp:
        run_mcp()
    elif args.query:
        run_query(args.query)
    elif args.demo:
        run_demo()
    elif args.serve:
        serve(args.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
