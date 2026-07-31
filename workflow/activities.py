"""
Workflow activities (pure functions) for the Text-to-Data pipeline.
"""

import os
import json
import re
from typing import Optional
from datetime import timedelta
import mistralai.workflows as workflows

from .models import (
    TextToDataInput,
    SchemaDiscoveryResult,
    SQLGenerationResult,
    QueryExecutionResult,
    EvaluationResult,
    TextToDataOutput,
)

@workflows.activity(start_to_close_timeout=timedelta(seconds=30))
async def discover_schema(input: TextToDataInput) -> SchemaDiscoveryResult:
    """
    Activity 1: Discover database schema and perform semantic lookup.
    Side-effects: reads DPM_lite.db, calls mistral-embed for vector search.
    """
    os.environ.setdefault("DATABASE_PATH", "DPM_lite.db")
    import config  # noqa: E402
    from si_connector import SQLiteSIConnector
    from dpm_specialist import DPMSchemaSpecialist

    connector = SQLiteSIConnector(db_path=config.DB_PATH)
    available_tables = connector.list_tables()

    db_schemas = {}
    for table in available_tables:
        try:
            db_schemas[table] = connector.get_table_schema(table)
        except Exception:
            pass

    # Deep taxonomy lookup via DPMSchemaSpecialist (semantic vector search)
    dpm_info = None
    try:
        specialist = DPMSchemaSpecialist(db_path=config.DB_PATH)
        dpm_info = specialist.lookup_exact_coordinates(input.query)
    except Exception:
        pass

    return SchemaDiscoveryResult(
        all_tables=available_tables,
        schemas=db_schemas,
        dpm_specialist_info=dpm_info,
    )


@workflows.activity(start_to_close_timeout=timedelta(seconds=60))
async def generate_sql(query: str, schema_info: dict, previous_error: Optional[str] = None) -> SQLGenerationResult:
    """
    Activity 2: Use an LLM to generate an exact SQL SELECT query.
    Side-effects: calls Mistral API.
    """
    os.environ.setdefault("DATABASE_PATH", "DPM_lite.db")
    import config  # noqa: E402

    client = config.get_mistral_client()

    system_prompt = (
        "Tu es un expert SQL universel. Ta mission est de générer une requête SQL SELECT brute "
        "pour répondre à la question de l'utilisateur d'après la structure de la base ci-jointe.\n\n"
        "Règles d'or SQL :\n"
        "1. Ne mets AUCUN commentaire (pas de -- ni de /* */) ni d'explication textuelle. Renvoie SEULEMENT le code SQL SELECT pur.\n"
        "2. Fais les JOIN nécessaires en te basant logiquement sur les clés primaires/étrangères du schéma.\n"
        "3. Limite les résultats (`LIMIT 10`).\n\n"
        f"Structure des tables de la base :\n{json.dumps(schema_info.get('schemas', {}), indent=2, ensure_ascii=False)}\n\n"
    )

    if schema_info.get("dpm_specialist_info"):
        system_prompt += f"Inspection Spécialiste DPM :\n{json.dumps(schema_info['dpm_specialist_info'], ensure_ascii=False)}\n\n"

    if previous_error:
        system_prompt += f"⚠️ ATTENTION : La tentative précédente a échoué avec l'erreur SQL suivante :\n{previous_error}\nCorrige la requête SQL.\n"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Question : '{query}'"},
    ]

    response = client.chat.complete(
        model=config.MODEL_CODE,
        messages=messages,
        response_format={"type": "text"},
        temperature=0.0,
    )
    sql = response.choices[0].message.content.strip()

    # Clean markdown code blocks and comments
    if "```" in sql:
        sql = sql.split("```sql")[-1].split("```")[0].strip()
    sql = re.sub(r"^--.*$", "", sql, flags=re.MULTILINE).strip()

    return SQLGenerationResult(sql_query=sql)


@workflows.activity(start_to_close_timeout=timedelta(seconds=15))
async def execute_query(sql_query: str) -> QueryExecutionResult:
    """
    Activity 3: Execute a read-only SQL SELECT on the database.
    Side-effects: reads DB.
    """
    os.environ.setdefault("DATABASE_PATH", "DPM_lite.db")
    import config  # noqa: E402
    from si_connector import SQLiteSIConnector

    connector = SQLiteSIConnector(db_path=config.DB_PATH)
    cols, rows = connector.execute_query(sql_query)

    # Convert tuples to lists for JSON serialization
    serializable_rows = [list(r) for r in rows]
    return QueryExecutionResult(
        sql_query=sql_query,
        columns=cols,
        rows=serializable_rows,
    )


@workflows.activity(start_to_close_timeout=timedelta(seconds=60))
async def evaluate_result(query: str, sql_query: str, columns: list[str], rows: list[list]) -> EvaluationResult:
    """
    Activity 3.5: Evaluate if the SQL and the returned data actually answer the user's query.
    Pure evaluation using LLM.
    """
    import config  # noqa: E402
    
    client = config.get_mistral_client()
    # Use MODEL_CHAT if available, otherwise fallback to standard chat model
    model_name = getattr(config, "MODEL_CHAT", "mistral-large-latest")

    system_prompt = (
        "Tu es un juge de données (Data Judge). Ta mission est d'évaluer si une requête SQL "
        "et les résultats qu'elle a renvoyés répondent correctement à la question initiale de l'utilisateur.\n"
        "Tu dois renvoyer UNIQUEMENT un objet JSON avec la structure exacte suivante :\n"
        "{\n"
        '  "reasoning": "Explication détaillée de pourquoi la requête et les résultats sont corrects ou incorrects",\n'
        '  "is_correct": true ou false,\n'
        '  "confidence_score": un nombre entre 0.0 et 1.0\n'
        "}\n"
    )

    data_preview = [dict(zip(columns, r)) for r in rows[:5]] if rows else []

    user_prompt = (
        f"Question originale : '{query}'\n"
        f"Requête SQL exécutée : \n{sql_query}\n"
        f"Résultats obtenus (aperçu) : {json.dumps(data_preview, ensure_ascii=False)}\n\n"
        "Évalue ces résultats selon la consigne et retourne le JSON."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = client.chat.complete(
        model=model_name,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    try:
        content = json.loads(response.choices[0].message.content)
        return EvaluationResult(
            reasoning=content.get("reasoning", "Pas de raisonnement fourni."),
            is_correct=bool(content.get("is_correct", False)),
            confidence_score=float(content.get("confidence_score", 0.0))
        )
    except Exception as e:
        return EvaluationResult(
            reasoning=f"Erreur d'évaluation : {str(e)}",
            is_correct=False,
            confidence_score=0.0
        )


@workflows.activity(start_to_close_timeout=timedelta(seconds=10))
async def synthesize_result(
    query: str,
    sql_query: str,
    columns: list[str],
    rows: list[list],
    dpm_specialist_info: Optional[dict],
    evaluation: EvaluationResult,
) -> TextToDataOutput:
    """
    Activity 4: Synthesize the final structured response.
    Pure computation, no side-effects.
    """
    audit_trail = [
        f"1. Query: '{query}'",
        f"2. SQL: {sql_query}",
        f"3. Rows returned: {len(rows)}",
    ]

    if not rows:
        qrt_t = dpm_specialist_info["qrt_table"] if dpm_specialist_info else "N/A"
        qrt_r = dpm_specialist_info["qrt_row"] if dpm_specialist_info else "N/A"
        qrt_c = dpm_specialist_info["qrt_col"] if dpm_specialist_info else "N/A"
        concept = dpm_specialist_info["table_label"] if dpm_specialist_info else "N/A"
        audit_trail.append("4. No data rows found")

        return TextToDataOutput(
            original_query=query,
            entity_name="Non trouvée",
            concept=concept,
            value=0.0,
            formatted_value="Aucune donnée correspondante",
            currency="EUR",
            period="2023-Q4",
            lei_code="N/A",
            qrt_table=qrt_t,
            qrt_row=qrt_r,
            qrt_col=qrt_c,
            sql_query=sql_query,
            reasoning=evaluation.reasoning,
            confidence=evaluation.confidence_score,
            rows_data=[],
            audit_trail=audit_trail,
        )

    first_row = dict(zip(columns, rows[0]))

    # Entity / primary name
    entity_name = "Toutes entités / Taxonomie DPM"
    for key in ["name", "entity_name", "table_label", "table_code", "label", "code"]:
        if key in first_row and first_row[key]:
            entity_name = str(first_row[key])
            break

    # LEI / Identifier
    lei_code = "N/A"
    for key in ["lei_code", "lei", "id", "code", "table_code"]:
        if key in first_row and first_row[key]:
            lei_code = str(first_row[key])
            break

    # Numeric value
    amount = 0.0
    currency = str(first_row.get("currency", "EUR"))
    period = str(first_row.get("period", "2023-Q4"))
    numeric_found = False

    for k, v in first_row.items():
        if isinstance(v, (int, float)) and k not in ["id", "entity_id"]:
            amount = float(v)
            numeric_found = True
            break

    # QRT coordinates
    if dpm_specialist_info:
        qrt_table = dpm_specialist_info["qrt_table"]
        qrt_row = dpm_specialist_info["qrt_row"]
        qrt_col = dpm_specialist_info["qrt_col"]
        concept_desc = f"{dpm_specialist_info['table_label']} - {dpm_specialist_info.get('description', '')[:60]}"
    else:
        qrt_table = str(first_row.get("table_code", first_row.get("code", "N/A")))
        qrt_row = "R0010"
        qrt_col = "C0010"
        y_x_z = str(first_row.get("y_x_z", ""))
        if y_x_z and "|" in y_x_z:
            for p in y_x_z.split("|"):
                if p.startswith("R"):
                    qrt_row = p
                elif p.startswith("C"):
                    qrt_col = p
        concept_desc = str(first_row.get("description", first_row.get("table_label", "Concept réglementaire")))

    # Format display value
    if numeric_found and amount != 0:
        if amount >= 1e9:
            fmt_val = f"{amount / 1e9:,.2f} Mds {currency}"
        elif amount >= 1e6:
            fmt_val = f"{amount / 1e6:,.2f} M€"
        else:
            fmt_val = f"{amount:,.2f} {currency}"
    else:
        fmt_val = f"{len(rows)} cellule(s) QRT identifiée(s)"

    audit_trail.append(f"4. QRT: {qrt_table} / {qrt_row} / {qrt_col}")

    return TextToDataOutput(
        original_query=query,
        entity_name=entity_name,
        concept=concept_desc,
        value=amount,
        formatted_value=fmt_val,
        currency=currency,
        period=period,
        lei_code=lei_code,
        qrt_table=qrt_table,
        qrt_row=qrt_row,
        qrt_col=qrt_col,
        sql_query=sql_query,
        reasoning=evaluation.reasoning,
        confidence=evaluation.confidence_score,
        rows_data=[dict(zip(columns, r)) for r in rows[:5]],
        audit_trail=audit_trail,
    )
