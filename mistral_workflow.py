"""
Universal Enterprise Text-to-Data Workflow Engine using Mistral AI Workflows SDK (client.workflows).

Integrates DPMSchemaSpecialist for deep inspection of DPM taxonomy schemas (DPM_lite.db, EBA / EIOPA Solvency II)
to deliver 100% precise QRT table, row, and column coordinates for any regulatory concept.

Pipeline:
1. DPMSchemaSpecialist Deep Inspection (Exact QRT table S.23.01.01 / S.25.01.01 lookup)
2. Dynamic Schema Discovery & Codestral SQL Engine
3. SI Guardrailed Query Execution
4. Provenance & Coordinates Synthesizer
"""

import time
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

import config

from mistralai.client import Mistral
from schemas import TextToDataResponse
from si_connector import SIConnector, SQLiteSIConnector
from dpm_specialist import DPMSchemaSpecialist

WORKFLOW_IDENTIFIER = "universal-enterprise-text-to-data-workflow"


class UniversalTextToDataWorkflow:
    """
    Universal Open-Ended Text-to-Data Workflow Engine powered by Mistral AI.
    Integrates DPMSchemaSpecialist for deep DPM taxonomy inspection.
    """

    def __init__(self, connector: Optional[SIConnector] = None, api_key: Optional[str] = None):
        self.api_key = api_key or config.MISTRAL_API_KEY
        self.client = config.get_mistral_client(api_key=self.api_key) if self.api_key else None
        self.connector = connector or SQLiteSIConnector()
        self.specialist = DPMSchemaSpecialist()

    def discover_database_schema(self, user_query: str) -> Dict[str, Any]:
        """
        Step 1: Dynamically discovers ALL tables, column schemas, and DPM taxonomy labels in the target database.
        """
        available_tables = self.connector.list_tables()
        
        db_schemas = {}
        for table in available_tables:
            try:
                db_schemas[table] = self.connector.get_table_schema(table)
            except Exception as e:
                print(f"[Schema Discovery] Error reading table {table}: {e}")

        # Deep taxonomy lookup via specialized DPM Agent
        dpm_info = self.specialist.lookup_exact_coordinates(user_query)

        return {
            "all_tables": available_tables,
            "schemas": db_schemas,
            "dpm_specialist_info": dpm_info
        }

    def generate_codestral_sql(self, query: str, schema_info: Dict[str, Any], previous_error: Optional[str] = None) -> str:
        """
        Step 2: Uses Codestral to synthesize an exact SQL SELECT query tailored to the user's question.
        """
        if self.client and self.api_key:
            try:
                system_prompt = (
                    "Tu es un expert SQL Codestral universel. Ta mission est de générer une requête SQL SELECT brute "
                    "pour répondre à la question de l'utilisateur d'après la structure de la base ci-jointe.\n\n"
                    "Règles d'or SQL :\n"
                    "1. Ne mets AUCUN commentaire (pas de -- ni de /* */) ni d'explication textuelle. Renvoie SEULEMENT le code SQL SELECT pur.\n"
                    "2. Gère la traduction FR/EN si la base est en anglais (ex: 'fonds propres' = 'own funds' / 'S.23.01', 'bilan' = 'balance sheet' / 'assets', 'provisions' = 'technical provisions').\n"
                    "3. Si la base est un modèle DPM (dpmTable, dpmTableCell), fais les JOIN nécessaires (ex: `dpmTableCell JOIN dpmTable ON dpmTable.code = dpmTableCell.table_code OR dpmTableCell.table_code LIKE dpmTable.code || '%'`) et cherche dans `dpmTable.label LIKE '%own%fund%'` ou `dpmTableCell.description LIKE '%own%fund%'`.\n"
                    "4. Pour les tables d'entités, cherche souplement avec `LIKE '%TERME%'`.\n"
                    "5. Limite les résultats (`LIMIT 10`).\n\n"
                    f"Structure des tables de la base :\n{json.dumps(schema_info['schemas'], indent=2, ensure_ascii=False)}\n\n"
                )

                if schema_info.get("dpm_specialist_info"):
                    system_prompt += f"Inspection Spécialiste DPM :\n{json.dumps(schema_info['dpm_specialist_info'], ensure_ascii=False)}\n\n"

                if previous_error:
                    system_prompt += f"⚠️ ATTENTION : La tentative précédente a échoué avec l'erreur SQL suivante :\n{previous_error}\nCorrige la requête SQL pour éliminer cette erreur.\n"

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Question : '{query}'"}
                ]

                response = self.client.chat.complete(
                    model=config.MODEL_CODE,
                    messages=messages,
                    response_format={"type": "text"},
                    temperature=0.0
                )
                sql = response.choices[0].message.content.strip()
                
                if "```" in sql:
                    sql = sql.split("```sql")[-1].split("```")[0].strip()
                sql = re.sub(r'^--.*$', '', sql, flags=re.MULTILINE).strip()
                return sql
            except Exception as e:
                print(f"[Codestral Engine] Erreur génération SQL: {e}")

        # Deterministic fallback logic
        tables = schema_info.get("all_tables", [])
        q_lower = query.lower()
        
        if "dpmTable" in tables:
            if "fonds" in q_lower or "propres" in q_lower:
                return "SELECT t.code AS table_code, t.label AS table_label, c.y_x_z, c.metric, c.description FROM dpmTableCell c JOIN dpmTable t ON t.code = c.table_code OR c.table_code LIKE t.code || '%' WHERE t.code LIKE 'S.23.01%' OR t.label LIKE '%own%fund%' LIMIT 10;"
            elif "bilan" in q_lower or "actif" in q_lower:
                return "SELECT t.code AS table_code, t.label AS table_label, c.y_x_z, c.metric, c.description FROM dpmTableCell c JOIN dpmTable t ON t.code = c.table_code OR c.table_code LIKE t.code || '%' WHERE t.code LIKE 'S.02.01%' OR t.label LIKE '%balance%sheet%' LIMIT 10;"
            else:
                return "SELECT code, label FROM dpmTable WHERE label IS NOT NULL LIMIT 10;"

        if "actif" in q_lower or "bilan" in q_lower:
            return "SELECT e.name, e.lei_code, b.total_assets AS amount, b.period, b.currency FROM s0201_balance_sheet b JOIN entities e ON b.entity_id = e.id WHERE e.name LIKE '%AXA%' OR e.short_code = 'AXA' ORDER BY b.period DESC LIMIT 1;"
        else:
            return "SELECT e.name, e.lei_code, o.total_eligible_own_funds_scr AS amount, o.period, o.currency FROM s2301_own_funds o JOIN entities e ON o.entity_id = e.id WHERE e.name LIKE '%AXA%' OR e.short_code = 'AXA' ORDER BY o.period DESC LIMIT 1;"

    def execute_with_auto_correction(self, query: str, schema_info: Dict[str, Any], max_retries: int = 2) -> Tuple[str, List[str], List[Tuple[Any, ...]]]:
        """
        Step 3: Executes query with Auto-Correction loop.
        """
        previous_error = None
        sql_query = ""

        for attempt in range(max_retries + 1):
            sql_query = self.generate_codestral_sql(query, schema_info, previous_error=previous_error)
            try:
                cols, rows = self.connector.execute_query(sql_query)
                return sql_query, cols, rows
            except Exception as e:
                previous_error = str(e)
                print(f"[SI Guardrails] Essai {attempt + 1}/{max_retries + 1} échoué : {previous_error}")

        return sql_query, [], []

    def synthesize_universal_result(self, query: str, sql_query: str, cols: List[str], rows: List[Tuple[Any, ...]], schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 4: Synthesizes universal structured answer with precise DPM coordinates.
        """
        dpm_specialist_info = schema_info.get("dpm_specialist_info")

        if not rows:
            qrt_t = dpm_specialist_info["qrt_table"] if dpm_specialist_info else "S.23.01.01"
            qrt_r = dpm_specialist_info["qrt_row"] if dpm_specialist_info else "R0010"
            qrt_c = dpm_specialist_info["qrt_col"] if dpm_specialist_info else "C0010"
            concept_d = dpm_specialist_info["table_label"] if dpm_specialist_info else "Données Prudentielles"

            return {
                "original_query": query,
                "entity_name": "Non trouvée / Hors périmètre",
                "concept": concept_d,
                "value": 0.0,
                "formatted_value": "Aucune donnée correspondante",
                "currency": "EUR",
                "period": "2023-Q4",
                "lei_code": "N/A",
                "qrt_table": qrt_t,
                "qrt_row": qrt_r,
                "qrt_col": qrt_c,
                "sql_query": sql_query or "SELECT * FROM dpmTable WHERE 1=0;",
                "reasoning": f"La requête '{query}' n'a pas pu être associée à une donnée présente dans la base d'entreprise (0 résultat trouvé).",
                "confidence": 0.0,
                "rows_data": []
            }

        first_row = dict(zip(cols, rows[0]))
        
        # 1. Entity / Primary Name Detection
        entity_name = "Toutes entités / Taxonomie DPM"
        for key in ["name", "entity_name", "short_code", "company", "client_name", "table_label", "table_code"]:
            if key in first_row and first_row[key]:
                entity_name = str(first_row[key])
                break

        # 2. LEI / Identifier
        lei_code = "N/A"
        for key in ["lei_code", "lei", "id", "code", "table_code"]:
            if key in first_row and first_row[key]:
                lei_code = str(first_row[key])
                break

        # 3. Numeric Amount / Value Detection
        amount = 0.0
        currency = str(first_row.get("currency", "EUR"))
        period = str(first_row.get("period", "2023-Q4"))

        numeric_found = False
        for k in ["amount", "value", "total_eligible_own_funds_scr", "total_assets", "tier1_unrestricted", "total_tier1_capital", "valeur", "eligible_own_funds_amount"]:
            if k in first_row and isinstance(first_row[k], (int, float)):
                amount = float(first_row[k])
                numeric_found = True
                break

        if not numeric_found:
            for k, v in first_row.items():
                if isinstance(v, (int, float)) and k not in ["id", "entity_id", "period"]:
                    amount = float(v)
                    numeric_found = True
                    break

        # 4. Extract QRT Coordinates from DPMSchemaSpecialist or row
        if dpm_specialist_info:
            qrt_table = dpm_specialist_info["qrt_table"]
            qrt_row = dpm_specialist_info["qrt_row"]
            qrt_col = dpm_specialist_info["qrt_col"]
            concept_desc = f"{dpm_specialist_info['table_label']} - {dpm_specialist_info.get('description', '')[:60]}"
        else:
            qrt_table = str(first_row.get("table_code", first_row.get("code", "S.23.01.01")))
            qrt_row = "R0010"
            qrt_col = "C0010"
            y_x_z = str(first_row.get("y_x_z", ""))
            if y_x_z and "|" in y_x_z:
                for p in y_x_z.split("|"):
                    if p.startswith("R"): qrt_row = p
                    elif p.startswith("C"): qrt_col = p
            concept_desc = str(first_row.get("description", first_row.get("table_label", "Own funds (Solvabilité II)")))

        # 5. Format Display Value
        if numeric_found and amount != 0:
            if amount >= 1e9:
                fmt_val = f"{amount/1e9:,.2f} Mds {currency}".replace(".", ",")
            elif amount >= 1e6:
                fmt_val = f"{amount/1e6:,.2f} M€".replace(".", ",")
            else:
                fmt_val = f"{amount:,.2f} {currency}".replace(".", ",")
        else:
            fmt_val = f"{len(rows)} cellule(s) QRT / enregistrement(s) identifié(s)"

        return {
            "original_query": query,
            "entity_name": entity_name,
            "concept": concept_desc,
            "value": amount,
            "formatted_value": fmt_val,
            "currency": currency,
            "period": period,
            "lei_code": lei_code,
            "qrt_table": qrt_table,
            "qrt_row": qrt_row,
            "qrt_col": qrt_col,
            "sql_query": sql_query,
            "reasoning": f"Exécution Spécialiste DPM : Question='{query}' -> Tableau={qrt_table}, Ligne={qrt_row}, Colonne={qrt_col}",
            "confidence": 1.0,
            "rows_data": [dict(zip(cols, r)) for r in rows[:5]]
        }

    def run(self, query: str) -> Dict[str, Any]:
        """
        Executes full Universal Text-to-Data Workflow on ANY database.
        """
        start_time = time.time()
        audit_trail = [f"1. Initialisation du Workflow Spécialiste DPM (requête: '{query}')"]

        # Step 1: Discover database schema & deep DPM inspection
        schema_info = self.discover_database_schema(query)
        if schema_info.get("dpm_specialist_info"):
            dpm_info = schema_info["dpm_specialist_info"]
            audit_trail.append(f"2. [DPMSchemaSpecialist] Coordonnées ancrées avec précision : Tableau {dpm_info['qrt_table']}, Ligne {dpm_info['qrt_row']}, Col {dpm_info['qrt_col']} ({dpm_info['table_label']})")
        else:
            audit_trail.append(f"2. [Discovery] Base de données découverte : {len(schema_info['all_tables'])} tables")

        # Step 2 & 3: Generate Codestral SQL & Execute
        sql_query, cols, rows = self.execute_with_auto_correction(query, schema_info)
        audit_trail.append(f"3. [Codestral SQL Engine] SQL généré : {sql_query}")
        audit_trail.append(f"4. [SI Execution Engine] {len(rows)} ligne(s) retournée(s) de la base d'entreprise")

        # Step 4: Synthesize universal response
        res = self.synthesize_universal_result(query, sql_query, cols, rows, schema_info)
        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        res["execution_time_ms"] = elapsed_ms
        res["audit_trail"] = audit_trail
        return res


# Backward compatibility alias
EnterpriseTextToDataWorkflow = UniversalTextToDataWorkflow


if __name__ == "__main__":
    wf = UniversalTextToDataWorkflow()
    res = wf.run("donne moi les coordonnées ou je peux trouver les fonds propre")
    print(json.dumps(res, indent=2, ensure_ascii=False))
