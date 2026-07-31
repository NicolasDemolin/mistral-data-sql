"""
Main Orchestrator for the ACPR Text-to-Data Workflow.
"""

import mistralai.workflows as workflows

from .models import (
    TextToDataInput,
    TextToDataOutput,
    QueryExecutionResult,
    EvaluationResult,
)
from .activities import (
    discover_schema,
    generate_sql,
    execute_query,
    evaluate_result,
    synthesize_result,
)


@workflows.workflow.define(
    name="acpr-text-to-data",
    workflow_display_name="ACPR Text-to-Data",
    workflow_description=(
        "Pipeline déterministe Text-to-Data générique. "
        "Découvre le schéma, génère le SQL, exécute la requête, "
        "évalue le résultat via un LLM juge (auto-correction), et retourne les données structurées."
    ),
)
class ACPRTextToDataWorkflow:
    """
    Durable Workflow orchestrating 4 activities:
    discover_schema → generate_sql → execute_query → synthesize_result
    """

    @workflows.workflow.entrypoint
    async def run(self, input: TextToDataInput) -> TextToDataOutput:
        # Step 1: Discover schema + semantic search
        schema_result = await discover_schema(input)

        # Step 2: Generate SQL
        schema_dict = schema_result.model_dump()
        sql_result = await generate_sql(
            query=input.query,
            schema_info=schema_dict,
        )

        # Step 3: Execute query with auto-correction (up to 2 retries)
        max_retries = 2
        query_result = None
        previous_error = None
        evaluation = None

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    # Re-generate SQL with the error context
                    sql_result = await generate_sql(
                        query=input.query,
                        schema_info=schema_dict,
                        previous_error=previous_error,
                    )
                
                query_result = await execute_query(sql_query=sql_result.sql_query)
                
                # Evaluate the result with the Judge LLM
                evaluation = await evaluate_result(
                    query=input.query,
                    sql_query=query_result.sql_query,
                    columns=query_result.columns,
                    rows=query_result.rows
                )
                
                if evaluation.is_correct:
                    break  # Success and logically correct according to the Judge
                else:
                    previous_error = f"La requête s'est exécutée, mais le résultat est jugé incorrect. Raisonnement du juge : {evaluation.reasoning}"

            except Exception as e:
                previous_error = f"Erreur d'exécution SQL : {str(e)}"
                
        # Fallbacks if all attempts fail
        if query_result is None:
            query_result = QueryExecutionResult(
                sql_query=sql_result.sql_query,
                columns=[],
                rows=[],
            )
            
        if evaluation is None:
            evaluation = EvaluationResult(
                reasoning=f"Échec total après {max_retries + 1} tentatives. Dernière erreur: {previous_error}",
                is_correct=False,
                confidence_score=0.0
            )

        # Step 4: Synthesize final structured response
        result = await synthesize_result(
            query=input.query,
            sql_query=query_result.sql_query,
            columns=query_result.columns,
            rows=query_result.rows,
            dpm_specialist_info=schema_result.dpm_specialist_info,
            evaluation=evaluation,
        )

        return result
