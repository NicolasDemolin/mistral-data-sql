"""
Worker launcher for the ACPR Text-to-Data Mistral AI Studio Workflow.

This script starts a worker process that connects to the Mistral control plane,
registers the ACPRTextToDataWorkflow, and waits for execution requests
triggered from AI Studio, Le Chat, or the SDK API.

Usage:
    python worker.py

The worker runs on YOUR infrastructure (DigitalOcean Droplet).
Your data (DPM_lite.db) never leaves your server.
"""

import asyncio
import os
import sys

# Ensure DATABASE_PATH is set before any config import
os.environ.setdefault("DATABASE_PATH", "DPM_lite.db")

# ── Custom Mistral Server URL (Enterprise / Dedicated / Proxy) ──
# We load the .env to catch MISTRAL_SERVER_URL if it's set
from dotenv import load_dotenv
load_dotenv()

custom_url = os.environ.get("MISTRAL_SERVER_URL", "").strip()
if custom_url:
    # 1. Configurer l'URL pour le SDK Mistral Workflows (le worker)
    os.environ["MISTRAL_WORKFLOWS_WORKER_SERVER_URL"] = custom_url
    # 2. Configurer l'URL pour les appels LLM internes du SDK Workflows
    os.environ["MISTRAL_WORKFLOWS_WORKER_AGENT__MISTRAL_CLIENT_SERVER_URL"] = custom_url

async def main():
    import mistralai.workflows as workflows


    # Import the workflow class so it gets registered via the decorator
    from mistral_studio_workflow import ACPRTextToDataWorkflow  # noqa: F401

    print("🚀 Starting ACPR Text-to-Data Workflow Worker...")
    print(f"📦 Database: {os.environ.get('DATABASE_PATH', 'DPM_lite.db')}")
    print(f"🔗 Connecting to Mistral control plane...")
    print(f"📋 Registered workflow: acpr-text-to-data")
    print()
    print("Worker is now listening for workflow executions.")
    print("Trigger from: AI Studio → Workflows → 'ACPR Text-to-Data'")
    print("Or via SDK:   client.workflows.run('acpr-text-to-data', ...)")
    print()

    await workflows.run_worker(
        workflows=[ACPRTextToDataWorkflow],
    )


if __name__ == "__main__":
    asyncio.run(main())
