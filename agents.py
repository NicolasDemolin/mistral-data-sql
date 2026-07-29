"""
Direct SDK usage module for individual Mistral AI capabilities.
Uses:
  - client.chat.parse() with response_format=Pydantic → Structured Outputs
  - client.embeddings.create() → Vector embeddings for Schema RAG
  - client.agents.complete() → Direct agent completion
  - Tool/Function models from SDK → Function calling
"""

import json
import numpy as np
from typing import List, Dict, Any, Optional

import config

from mistralai.client import Mistral
from mistralai.client.models import (
    UserMessage,
    AssistantMessage,
    ToolMessage,
    Tool,
    Function,
)

from schemas import ParsedIntent, DataCoordinate
from si_connector import SQLiteSIConnector


class MistralDirectAPI:
    """
    Provides direct access to individual Mistral AI SDK features
    for cases where the full RunContext pipeline is not needed.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.MISTRAL_API_KEY
        self.client = config.get_mistral_client(api_key=self.api_key) if self.api_key else None
        self.connector = SQLiteSIConnector()

    # ── Structured Outputs via client.chat.parse ─────────────────────────

    def parse_intent(self, query: str) -> ParsedIntent:
        """
        Uses client.chat.parse() with response_format=ParsedIntent
        to extract structured intent from a natural language query.
        """
        response = self.client.chat.parse(
            model=config.MODEL_LARGE,
            response_format=ParsedIntent,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Tu es un expert réglementaire ACPR et Solvabilité II. "
                        "Analyse la demande et extrait l'intention structurée."
                    ),
                },
                {"role": "user", "content": f"Demande réglementaire : '{query}'"},
            ],
        )
        return response.choices[0].message.parsed

    # ── Embeddings via client.embeddings.create ──────────────────────────

    def compute_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Uses client.embeddings.create() with mistral-embed model.
        Returns list of embedding vectors.
        """
        response = self.client.embeddings.create(
            model=config.MODEL_EMBED,
            inputs=texts,
        )
        return [item.embedding for item in response.data]

    def semantic_schema_search(self, concept: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Uses Mistral Embeddings to find the most semantically similar
        metadata entries in the ACPR data dictionary.
        """
        # Load all metadata catalog entries
        cols, rows = self.connector.execute_query(
            "SELECT table_name, column_name, qrt_table_code, qrt_row_code, "
            "qrt_col_code, concept_fr, concept_en, unit, description "
            "FROM data_dictionary"
        )
        catalog = []
        catalog_texts = []
        for r in rows:
            entry = {
                "table_name": r[0], "column_name": r[1],
                "qrt_table_code": r[2], "qrt_row_code": r[3], "qrt_col_code": r[4],
                "concept_fr": r[5], "concept_en": r[6], "unit": r[7], "description": r[8],
            }
            catalog.append(entry)
            catalog_texts.append(f"{r[5]} {r[8]} {r[6]}")

        # Embed concept + all catalog entries in a single API call
        all_texts = [concept] + catalog_texts
        embeddings = self.compute_embeddings(all_texts)

        query_vec = np.array(embeddings[0])
        results = []
        for i, entry in enumerate(catalog):
            cat_vec = np.array(embeddings[i + 1])
            similarity = float(np.dot(query_vec, cat_vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(cat_vec)
            ))
            results.append({**entry, "similarity": round(similarity, 4)})

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    # ── Function Calling via client.chat.complete with tools ─────────────

    def generate_sql_with_tools(self, intent: ParsedIntent, schema_context: str) -> str:
        """
        Uses client.chat.complete() with Tool/Function models
        for explicit function calling to generate SQL.
        """
        sql_tool = Tool(
            function=Function(
                name="execute_sql_query",
                description="Execute a SQL SELECT query against the ACPR database",
                parameters={
                    "type": "object",
                    "required": ["sql_query"],
                    "properties": {
                        "sql_query": {
                            "type": "string",
                            "description": "The SQL SELECT query to execute",
                        }
                    },
                },
            )
        )

        response = self.client.chat.complete(
            model=config.MODEL_CODE,
            messages=[
                UserMessage(
                    content=(
                        f"Schema context:\n{schema_context}\n\n"
                        f"Generate a SQL SELECT query to find '{intent.concept_fr}' "
                        f"for entity '{intent.entity_name}' at period '{intent.period}'. "
                        f"Call the execute_sql_query tool with the query."
                    )
                )
            ],
            tools=[sql_tool],
            tool_choice="any",
            temperature=0,
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            args = json.loads(str(tool_call.function.arguments))
            return args.get("sql_query", "")
        return ""

    # ── Agent Completion via client.agents.complete ──────────────────────

    def agent_complete(self, agent_id: str, query: str) -> str:
        """
        Uses client.agents.complete() for a single-shot agent response.
        """
        response = self.client.agents.complete(
            agent_id=agent_id,
            messages=[UserMessage(content=query)],
        )
        return response.choices[0].message.content
