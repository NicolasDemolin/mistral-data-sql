"""
ACPR Text-to-Data Workflow Engine.
Delegates to EnterpriseTextToDataWorkflow in mistral_workflow.py.
Handles arbitrary scale enterprise databases (Snowflake, Postgres, BigQuery, Oracle) without dumping data.
"""

import asyncio
from typing import Dict, Any

from mistral_workflow import EnterpriseTextToDataWorkflow


class ACPRWorkflow:
    """
    ACPR Text-to-Data Workflow orchestrator.
    Powered by EnterpriseTextToDataWorkflow and Codestral SQL synthesis.
    """

    def __init__(self, api_key: str = None):
        self.engine = EnterpriseTextToDataWorkflow(api_key=api_key)

    async def process_query_async(self, query: str) -> dict:
        """Process query asynchronously via Enterprise Workflow engine."""
        return self.engine.run(query)

    def process_query(self, query: str) -> dict:
        """Process query synchronously via Enterprise Workflow engine."""
        return self.engine.run(query)

    def cleanup(self):
        """Cleanup workflow engine resources."""
        pass
