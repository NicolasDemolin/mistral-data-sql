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
