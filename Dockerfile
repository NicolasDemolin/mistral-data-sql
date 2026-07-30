FROM python:3.12-slim

LABEL maintainer="NicolasDemolin"
LABEL description="ACPR DPM MCP Server — Solvency II Text-to-Data"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY config.py .
COPY tools.py .
COPY si_connector.py .
COPY mcp_server_remote.py .
COPY schemas.py .
COPY dpm_specialist.py .
COPY db_indexer.py .
COPY agents.py .
COPY agent_executor.py .
COPY mistral_workflow.py .
COPY workflow.py .
COPY server.py .
COPY main.py .
COPY studio_register.py .
COPY vibe_agent_setup.py .

# Copy the DPM database
COPY DPM_lite.db .

# Copy schema index if available
COPY .schema_index.json* ./

# Environment defaults
ENV DATABASE_PATH=DPM_lite.db
ENV MCP_PORT=8080
ENV MCP_TRANSPORT=sse
ENV SERVER_PORT=8000

# Expose MCP SSE port and API port
EXPOSE 8080
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import httpx; httpx.get('http://localhost:8080/sse', timeout=3)" || exit 1

# Default: run the MCP SSE server
CMD ["python", "mcp_server_remote.py"]
