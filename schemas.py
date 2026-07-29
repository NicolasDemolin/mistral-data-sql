"""
Pydantic Schemas for Mistral AI Structured Outputs.
These models are used as:
  - response_format in client.chat.parse()
  - output_format in RunContext()
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class ParsedIntent(BaseModel):
    """Structured intent extracted from a natural language ACPR query."""
    entity_name: str = Field(description="Nom de l'entité (ex: AXA SA, ALLIANZ SE)")
    concept_fr: str = Field(description="Concept réglementaire en français (ex: fonds propres éligibles)")
    period: str = Field(default="2023-Q4", description="Période de reporting (ex: 2023-Q4)")
    regulatory_framework: str = Field(default="Solvabilité II", description="Cadre réglementaire")
    reasoning: str = Field(description="Raisonnement étape par étape")


class DataCoordinate(BaseModel):
    """Exact ACPR/EIOPA QRT cell coordinates + provenance data."""
    entity_name: str = Field(description="Nom officiel de l'entité")
    lei_code: str = Field(description="Code LEI")
    qrt_table_code: str = Field(description="Code tableau QRT (ex: S.23.01.01)")
    qrt_row_code: str = Field(description="Code ligne QRT (ex: R0010)")
    qrt_col_code: str = Field(description="Code colonne QRT (ex: C0010)")
    concept_description: str = Field(description="Libellé réglementaire exact")
    raw_value: float = Field(description="Valeur numérique brute")
    formatted_value: str = Field(description="Valeur formatée (ex: 52,45 Mds EUR)")
    unit: str = Field(description="Unité (EUR, %, Ratio)")
    currency: str = Field(description="Devise")
    reporting_period: str = Field(description="Période de reporting")


class TextToDataResponse(BaseModel):
    """Final structured output for the complete Text-to-Data workflow."""
    original_query: str = Field(description="Requête utilisateur originale")
    entity_name: str = Field(description="Nom de l'entité identifiée")
    concept: str = Field(description="Concept réglementaire identifié")
    value: float = Field(description="Valeur numérique extraite")
    formatted_value: str = Field(description="Valeur formatée lisible")
    currency: str = Field(default="EUR", description="Devise")
    period: str = Field(description="Période de reporting")
    lei_code: str = Field(description="Code LEI de l'entité")
    qrt_table: str = Field(description="Code tableau QRT")
    qrt_row: str = Field(description="Code ligne QRT")
    qrt_col: str = Field(description="Code colonne QRT")
    sql_query: str = Field(description="Requête SQL exécutée")
    reasoning: str = Field(description="Explication complète du raisonnement")
    confidence: float = Field(default=1.0, description="Score de confiance 0-1")
