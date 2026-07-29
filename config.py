"""
Configuration for ACPR Text-to-Data Workflow.
Loads environment variables from .env file and sets up sys.path for the client-python SDK.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
ENV_FILE = BASE_DIR / ".env"

# Load environment variables from .env if present
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE)
else:
    load_dotenv()

# Database Path
DB_NAME = os.environ.get("DATABASE_PATH", "acpr_reporting.db")
DB_PATH = BASE_DIR / DB_NAME

# Add the cloned client-python SDK to sys.path so `from mistralai.client import Mistral` works
SDK_SRC = BASE_DIR / "client-python" / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))

from typing import Optional

# ── Mistral AI Settings ──────────────────────────────────────────────────
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "").strip()
MISTRAL_AGENT_ID = os.environ.get("MISTRAL_AGENT_ID", "").strip()

_raw_url = (
    os.environ.get("MISTRAL_SERVER_URL") or 
    os.environ.get("MISTRAL_ENDPOINT_URL") or 
    os.environ.get("MISTRAL_BASE_URL") or 
    os.environ.get("MISTRAL_URL", "")
).strip()
MISTRAL_SERVER_URL = _raw_url if _raw_url else None

def get_mistral_client(api_key: Optional[str] = None, server_url: Optional[str] = None):
    """Factory helper to instantiate a Mistral client with optional custom server URL endpoint."""
    from mistralai.client import Mistral
    key = (api_key or MISTRAL_API_KEY).strip() if (api_key or MISTRAL_API_KEY) else ""
    url = (server_url or MISTRAL_SERVER_URL or "").strip()
    
    kwargs = {"api_key": key}
    if url:
        kwargs["server_url"] = url
    return Mistral(**kwargs)

# Models available on AI Studio
MODEL_LARGE = os.environ.get("MISTRAL_MODEL_LARGE", "mistral-large-latest")
MODEL_MEDIUM = os.environ.get("MISTRAL_MODEL_MEDIUM", "mistral-medium-latest")
MODEL_CODE = os.environ.get("MISTRAL_MODEL_CODE", "codestral-latest")
MODEL_EMBED = os.environ.get("MISTRAL_MODEL_EMBED", "mistral-embed")

# ── Web Server Settings ──────────────────────────────────────────────────
SERVER_HOST = os.environ.get("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("SERVER_PORT", "8000"))

# ── Defaults ─────────────────────────────────────────────────────────────
DEFAULT_CURRENCY = os.environ.get("DEFAULT_CURRENCY", "EUR")
DEFAULT_PERIOD = os.environ.get("DEFAULT_PERIOD", "2023-Q4")
